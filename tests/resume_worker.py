"""Subprocess harness: verifies SQLite recovery across real Python processes."""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

from exercises.sessions import invoke_review
from tests.fixtures import PR_URL, analysis, pull_request


async def main():
    db, thread_id, stage = sys.argv[1:]
    os.environ["HITL_DB_PATH"] = db
    os.environ["GITHUB_USER"] = "fixture-reviewer"
    llm = Mock()
    llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=analysis())
    with patch("exercises.exercise_4_audit.fetch_pr", return_value=pull_request()) as fetch, patch("exercises.exercise_4_audit.get_llm", return_value=llm), patch("exercises.exercise_4_audit.post_review_comment") as post:
        if stage != "start":
            fetch.side_effect = AssertionError("Must not fetch again after restart")
            llm.with_structured_output.return_value.ainvoke.side_effect = AssertionError("Must not analyze again after restart")
        result = await invoke_review(PR_URL, thread_id, {"choice": "approve"} if stage == "approve" else None)
        print(json.dumps({"stage": stage, "interrupted": bool(result.get("__interrupt__")),
                          "final_action": result.get("final_action"), "fetches": fetch.call_count,
                          "analyses": llm.with_structured_output.return_value.ainvoke.call_count,
                          "post_attempts": post.call_count}))


if __name__ == "__main__":
    asyncio.run(main())
