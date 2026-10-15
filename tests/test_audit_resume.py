import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from common.db import replay_events
from exercises import exercise_4_audit as ex
from tests.fixtures import PR_URL, analysis, pull_request


class AuditResumeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "audit.db")
        self.env = patch.dict(os.environ, {"HITL_DB_PATH": self.path, "GITHUB_USER": "student"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.llm = Mock()
        self.llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=analysis())
        for name, options in [("fetch_pr", {"return_value": pull_request()}),
                              ("get_llm", {"return_value": self.llm}), ("post_review_comment", {})]:
            context = patch.object(ex, name, **options)
            setattr(self, name, context.start())
            self.addCleanup(context.stop)
        self.cfg = {"configurable": {"thread_id": self.id()}}
        self.input = {"pr_url": PR_URL, "thread_id": self.id()}

    async def invoke(self, value, *, confirm=True):
        async with AsyncSqliteSaver.from_conn_string(self.path) as cp:
            await cp.setup()
            return await ex.build_graph(cp, confirm_after_escalation=confirm).ainvoke(value, self.cfg)

    async def test_new_connection_resumes_without_refetch_or_duplicate_request(self):
        pending = await self.invoke(self.input)
        self.assertEqual(pending["__interrupt__"][0].value["kind"], "approval_request")
        self.post_review_comment.assert_not_called()
        final = await self.invoke(Command(resume={"choice": "approve", "feedback": "Checked migration"}))
        self.assertEqual(final["final_action"], "committed")
        self.assertEqual(self.fetch_pr.call_count, 1)
        self.assertEqual(self.llm.with_structured_output.return_value.ainvoke.call_count, 1)
        self.assertEqual(self.post_review_comment.call_count, 1)
        events = await replay_events(self.id())
        actions = [e["action"] for e in events]
        self.assertEqual(actions, ["fetch_pr", "analyze", "route", "human_approval_requested", "human_approval", "commit"])
        self.assertEqual(events[-2]["reviewer_id"], "student")
        self.assertEqual(events[-2]["decision"], "approve")
        self.assertTrue(all(e["execution_time_ms"] >= 0 for e in events))

    async def test_final_confirmation_reject_wins_over_escalation_answers(self):
        self.llm.with_structured_output.return_value.ainvoke.side_effect = [analysis(0.4), analysis(0.5, summary="Still needs changes.")]
        pending = await self.invoke(self.input)
        question = pending["__interrupt__"][0].value["questions"][0]
        confirm = await self.invoke(Command(resume={question: "No migration exists yet."}))
        self.assertEqual(confirm["__interrupt__"][0].value["phase"], "after_escalation")
        self.assertEqual(confirm["analysis"].confidence, 0.5)
        self.post_review_comment.assert_not_called()
        final = await self.invoke(Command(resume={"choice": "reject", "feedback": "Wait for migration."}))
        self.assertEqual(final["final_action"], "rejected")
        self.post_review_comment.assert_not_called()
        events = await replay_events(self.id())
        self.assertEqual([e["action"] for e in events].count("escalation_requested"), 1)
        self.assertEqual(next(e for e in events if e["action"] == "synthesize")["confidence"], 0.5)

    async def test_auto_post_failure_is_not_success(self):
        self.llm.with_structured_output.return_value.ainvoke.return_value = analysis(0.9)
        self.post_review_comment.side_effect = TimeoutError("private transport detail")
        result = await self.invoke(self.input)
        self.assertEqual(result["final_action"], "auto_commit_failed")
        events = await replay_events(self.id())
        self.assertEqual(events[-1]["decision"], "failed")
        self.assertNotIn("private transport detail", events[-1]["reason"])

    async def test_edit_is_persisted_then_requires_approval(self):
        await self.invoke(self.input)
        pending = await self.invoke(Command(resume={"choice": "edit", "edited_body": "Manual review: add regression coverage."}))
        self.assertEqual(pending["__interrupt__"][0].value["review_body"], "Manual review: add regression coverage.")
        self.post_review_comment.assert_not_called()
        final = await self.invoke(Command(resume={"choice": "approve"}))
        self.assertEqual(final["final_action"], "committed")
        self.assertEqual(self.post_review_comment.call_args.args[1], "Manual review: add regression coverage.")

    async def test_provider_failure_is_audited_without_post(self):
        self.llm.with_structured_output.return_value.ainvoke.side_effect = RuntimeError("secret-provider-detail")
        with self.assertRaises(RuntimeError):
            await self.invoke(self.input)
        self.post_review_comment.assert_not_called()
        events = await replay_events(self.id())
        self.assertEqual(events[-1]["action"], "analyze")
        self.assertEqual(events[-1]["decision"], "failed")
        self.assertNotIn("secret-provider-detail", events[-1]["reason"])

    async def test_cli_escalation_still_posts_refined_review_without_extra_confirm(self):
        self.llm.with_structured_output.return_value.ainvoke.side_effect = [analysis(0.4), analysis(0.6, summary="Refined migration review.")]
        pending = await self.invoke(self.input, confirm=False)
        question = pending["__interrupt__"][0].value["questions"][0]
        final = await self.invoke(Command(resume={question: "Migration is in a separate PR."}), confirm=False)
        self.assertEqual(final["final_action"], "committed")
        self.assertIn("Refined migration review.", self.post_review_comment.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
