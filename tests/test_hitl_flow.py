import unittest
from unittest.mock import Mock, patch

from langgraph.types import Command
from exercises import exercise_2_hitl as hitl
from exercises import exercise_3_escalation as escalation
from tests.fixtures import PR_URL, DIFF, analysis, pull_request


class HumanApprovalTests(unittest.TestCase):
    def start(self, module, confidence=0.65):
        llm = Mock()
        llm.with_structured_output.return_value.invoke.return_value = analysis(confidence)
        for name, value in [("fetch_pr", pull_request()), ("get_llm", llm)]:
            context = patch.object(module, name, return_value=value)
            context.start()
            self.addCleanup(context.stop)
        post_context = patch.object(module, "post_review_comment")
        post = post_context.start()
        self.addCleanup(post_context.stop)
        graph = module.build_graph()
        config = {"configurable": {"thread_id": self.id()}}
        result = graph.invoke({"pr_url": PR_URL, "thread_id": self.id()}, config)
        return graph, config, result, post, llm

    def test_approval_waits_then_posts_once(self):
        graph, config, result, post, _ = self.start(hitl)
        payload = result["__interrupt__"][0].value
        self.assertEqual(payload["kind"], "approval_request")
        self.assertIn("priority = 1", payload["diff_preview"])
        self.assertTrue(payload["confidence_reasoning"])
        post.assert_not_called()
        final = graph.invoke(Command(resume={"choice": "approve", "feedback": ""}), config)
        self.assertEqual(final["final_action"], "committed")
        self.assertEqual(post.call_count, 1)
        self.assertIn("Specify the migration", post.call_args.args[1])

    def test_reject_does_not_publish(self):
        graph, config, _, post, _ = self.start(hitl)
        final = graph.invoke(Command(resume={"choice": "reject", "feedback": "Needs tests"}), config)
        self.assertEqual(final["final_action"], "rejected")
        post.assert_not_called()

    def test_edit_requires_second_approval_and_publishes_edited_body(self):
        graph, config, _, post, _ = self.start(hitl)
        edited = graph.invoke(Command(resume={"choice": "edit", "edited_body": "Reviewed manually: add migration tests."}), config)
        self.assertIn("__interrupt__", edited)
        self.assertEqual(edited["__interrupt__"][0].value["review_body"], "Reviewed manually: add migration tests.")
        post.assert_not_called()
        final = graph.invoke(Command(resume={"choice": "approve"}), config)
        self.assertEqual(final["final_action"], "committed")
        self.assertEqual(post.call_args.args[1], "Reviewed manually: add migration tests.")

    def test_invalid_choice_never_publishes(self):
        graph, config, _, post, _ = self.start(hitl)
        with self.assertRaises(ValueError):
            graph.invoke(Command(resume={"choice": "anything"}), config)
        post.assert_not_called()

    def test_escalation_uses_initial_analysis_diff_and_answers(self):
        graph, config, result, post, llm = self.start(escalation, confidence=0.4)
        payload = result["__interrupt__"][0].value
        self.assertEqual(payload["kind"], "escalation")
        post.assert_not_called()
        llm.with_structured_output.return_value.invoke.return_value = analysis(0.7, summary="Migration reviewed with context.")
        final = graph.invoke(Command(resume={"How are existing task rows migrated?": "A separate migration backfills all rows."}), config)
        self.assertEqual(final["analysis"].summary, "Migration reviewed with context.")
        prompt = llm.with_structured_output.return_value.invoke.call_args.args[0][-1]["content"]
        for expected in [DIFF, "Adds task priority", "A separate migration backfills all rows."]:
            self.assertIn(expected, prompt)
        self.assertIn("Migration reviewed with context.", post.call_args.args[1])

    def test_escalation_rejects_missing_answers_before_synthesis(self):
        graph, config, _, post, llm = self.start(escalation, confidence=0.4)
        with self.assertRaises(ValueError):
            graph.invoke(Command(resume={"How are existing task rows migrated?": ""}), config)
        self.assertEqual(llm.with_structured_output.return_value.invoke.call_count, 1)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
