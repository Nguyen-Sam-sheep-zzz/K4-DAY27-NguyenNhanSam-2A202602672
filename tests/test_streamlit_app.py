import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from streamlit.testing.v1 import AppTest
from tests.fixtures import PR_URL, analysis, pull_request

APP_FILE = str(Path(__file__).resolve().parents[1] / "app.py")


class StreamlitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env = patch.dict(os.environ, {"HITL_DB_PATH": os.path.join(temp.name, "ui.db"), "GITHUB_USER": "student"})
        env.start()
        self.addCleanup(env.stop)
        self.llm = Mock()
        self.llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=analysis())
        for name, options in [("fetch_pr", {"return_value": pull_request()}),
                              ("get_llm", {"return_value": self.llm}), ("post_review_comment", {})]:
            context = patch("exercises.exercise_4_audit." + name, **options)
            setattr(self, name, context.start())
            self.addCleanup(context.stop)
        self.app = AppTest.from_file(APP_FILE, default_timeout=30).run()

    def button(self, label):
        return next(b for b in self.app.button if b.label == label)

    def start(self):
        next(t for t in self.app.text_input if t.label == "PR URL").set_value(PR_URL)
        self.button("Run review").click().run()
        self.assertEqual(len(self.app.exception), 0)

    def test_approve_posts_and_rerun_does_not_repeat(self):
        self.start()
        self.post_review_comment.assert_not_called()
        self.button("Approve").click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertTrue(any("posted" in x.value.lower() for x in self.app.success))
        self.app.run()
        self.assertEqual(self.post_review_comment.call_count, 1)

    def test_reject_has_no_external_post(self):
        self.start()
        self.button("Reject").click().run()
        self.assertTrue(any("Rejected" in x.value for x in self.app.warning))
        self.post_review_comment.assert_not_called()

    def test_failed_auto_post_is_error_not_success(self):
        self.llm.with_structured_output.return_value.ainvoke.return_value = analysis(0.9)
        self.post_review_comment.side_effect = TimeoutError("private")
        self.start()
        self.assertEqual(len(self.app.success), 0)
        self.assertTrue(any("failed" in x.value.lower() for x in self.app.error))

    def test_escalation_requires_answers_and_final_confirmation(self):
        self.llm.with_structured_output.return_value.ainvoke.side_effect = [analysis(0.4), analysis(0.6, summary="Refined review with migration context.")]
        self.start()
        self.button("Submit answers").click().run()
        self.post_review_comment.assert_not_called()
        self.assertTrue(any("every" in x.value.lower() for x in self.app.warning))
        question = next(t for t in self.app.text_area if t.label == "How are existing task rows migrated?")
        question.set_value("A separate migration backfills existing rows.")
        self.button("Submit answers").click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertIn("Refined review with migration context.", self.app.session_state.interrupt_payload["review_body"])
        self.post_review_comment.assert_not_called()
        self.button("Reject").click().run()
        self.post_review_comment.assert_not_called()

    def test_manual_edit_is_previewed_and_requires_second_approval(self):
        self.start()
        next(t for t in self.app.text_area if t.label == "Review text").set_value("Manual review: add a backfill regression test.")
        self.button("Edit").click().run()
        self.assertEqual(self.app.session_state.interrupt_payload["review_body"], "Manual review: add a backfill regression test.")
        self.post_review_comment.assert_not_called()
        self.button("Approve").click().run()
        self.assertEqual(self.post_review_comment.call_args.args[1], "Manual review: add a backfill regression test.")

    def test_synthesis_failure_recovers_from_checkpoint_instead_of_stale_question_form(self):
        self.llm.with_structured_output.return_value.ainvoke.side_effect = [
            analysis(0.4), RuntimeError("transient provider failure"),
            analysis(0.6, summary="Recovered refined review."),
        ]
        self.start()
        next(t for t in self.app.text_area if t.label == "How are existing task rows migrated?").set_value("Saved original migration answer.")
        self.button("Submit answers").click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertIsNone(self.app.session_state.interrupt_payload)
        self.assertTrue(self.app.session_state.retryable)
        self.assertFalse(any(t.label == "How are existing task rows migrated?" for t in self.app.text_area))
        self.assertTrue(any("synthesis failed" in item.value.lower() for item in self.app.error))
        self.button("Retry operation").click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.session_state.interrupt_payload["phase"], "after_escalation")
        self.assertEqual(self.fetch_pr.call_count, 1)
        prompt = self.llm.with_structured_output.return_value.ainvoke.call_args.args[0][-1]["content"]
        self.assertIn("Saved original migration answer.", prompt)
        self.post_review_comment.assert_not_called()

    def test_new_browser_session_restores_from_thread_query_parameter(self):
        self.start()
        thread_id = self.app.session_state.thread_id
        restored = AppTest.from_file(APP_FILE, default_timeout=30)
        restored.query_params["thread"] = thread_id
        restored.run()
        self.assertEqual(len(restored.exception), 0)
        self.assertEqual(restored.session_state.thread_id, thread_id)
        self.assertEqual(restored.session_state.interrupt_payload["kind"], "approval_request")
        self.assertEqual(self.fetch_pr.call_count, 1)
        self.post_review_comment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
