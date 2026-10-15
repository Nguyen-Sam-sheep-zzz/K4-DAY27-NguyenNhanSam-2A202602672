import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from common.db import write_audit_event
from common.schemas import AuditEntry
from exercises import sessions
from tests.fixtures import PR_URL, analysis, pull_request


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"HITL_DB_PATH": os.path.join(self.temp.name, "sessions.db")})
        env.start()
        self.addCleanup(env.stop)

    async def test_recent_sessions_use_risk_order_instead_of_alphabetical_max(self):
        for risk in ["high", "low", "med"]:
            await write_audit_event(thread_id="risky-thread", pr_url=PR_URL, entry=AuditEntry(
                agent_id="test", action="route", confidence=0.5, risk_level=risk,
                decision="pending", execution_time_ms=1,
            ))
        rows = await sessions.list_recent_sessions()
        self.assertEqual(rows[0]["worst_risk"], "high")
        self.assertEqual(rows[0]["events"], 3)

    async def test_load_and_reopen_completed_thread_never_reposts(self):
        llm = Mock()
        llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=analysis())
        with patch("exercises.exercise_4_audit.fetch_pr", return_value=pull_request()) as fetch, patch("exercises.exercise_4_audit.get_llm", return_value=llm), patch("exercises.exercise_4_audit.post_review_comment") as post:
            pending = await sessions.invoke_review(PR_URL, "session-1")
            loaded = await sessions.load_session("session-1")
            self.assertEqual(loaded["__interrupt__"][0].value["kind"], "approval_request")
            self.assertEqual(pending["analysis"].confidence, loaded["analysis"].confidence)
            final = await sessions.invoke_review(PR_URL, "session-1", {"choice": "approve"})
            restored = await sessions.invoke_review(PR_URL, "session-1")
            self.assertEqual(restored["final_action"], final["final_action"])
            self.assertEqual(post.call_count, 1)
            self.assertEqual(fetch.call_count, 1)
            with self.assertRaises(ValueError):
                await sessions.invoke_review("https://github.com/example/lab/pull/2", "session-1")

    async def test_unknown_session_and_resume_without_checkpoint_are_rejected(self):
        with self.assertRaises(ValueError):
            await sessions.load_session("missing")
        with self.assertRaises(ValueError):
            await sessions.invoke_review(PR_URL, "missing", {"choice": "approve"})


if __name__ == "__main__":
    unittest.main()
