"""Reproducible fixture evidence. All GitHub/LLM calls are replaced locally.

This exercises the real graph, SQLite audit and session recovery. It does not
establish live LLM/GitHub integration and must never be labelled as such.
"""
import argparse
import asyncio
import csv
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from common.db import replay_events
from exercises.sessions import invoke_review, load_session
from tests.fixtures import PR_URL, analysis, pull_request


async def capture(db):
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    evidence = Path("evidence")
    (evidence / "logs").mkdir(parents=True, exist_ok=True)
    results = []
    previews = {}
    with patch.dict(os.environ, {"HITL_DB_PATH": db, "GITHUB_USER": "fixture-reviewer"}):
        for case in ["auto", "approve", "reject", "edit", "escalate_approve", "escalate_reject", "post_failure", "resume"]:
            thread = f"fixture-{case}-{uuid.uuid4().hex[:8]}"
            llm = Mock()
            structured = llm.with_structured_output.return_value
            initial = analysis(0.9 if case in {"auto", "post_failure"} else 0.4 if case.startswith("escalate") else 0.65)
            structured.ainvoke = AsyncMock(return_value=initial)
            if case.startswith("escalate"):
                structured.ainvoke.side_effect = [initial, analysis(0.68, summary="Fixture: refined review after migration Q&A.")]
            with patch("exercises.exercise_4_audit.fetch_pr", return_value=pull_request()) as fetch, patch("exercises.exercise_4_audit.get_llm", return_value=llm), patch("exercises.exercise_4_audit.post_review_comment") as post:
                if case == "post_failure":
                    post.side_effect = TimeoutError("fixture timeout")
                result = await invoke_review(PR_URL, thread)
                if case not in {"auto", "post_failure"}:
                    # Fresh graph/connection loaded each call, just like another process.
                    restored = await load_session(thread)
                    assert restored["__interrupt__"][0].value["kind"] == result["__interrupt__"][0].value["kind"]
                    if case == "edit":
                        result = await invoke_review(PR_URL, thread, {"choice": "edit", "edited_body": "Fixture manual review: add migration regression coverage."})
                        assert post.call_count == 0
                    if case.startswith("escalate"):
                        q = result["__interrupt__"][0].value["questions"][0]
                        result = await invoke_review(PR_URL, thread, {q: "Fixture answer: migration will ship in a separate change."})
                        assert result["__interrupt__"][0].value["kind"] == "approval_request"
                        assert post.call_count == 0
                    choice = "reject" if case in {"reject", "escalate_reject"} else "approve"
                    result = await invoke_review(PR_URL, thread, {"choice": choice, "feedback": "Fixture verification."})
                expected = "auto_commit_failed" if case == "post_failure" else "auto_committed" if case == "auto" else "rejected" if case in {"reject", "escalate_reject"} else "committed"
                assert result["final_action"] == expected
                assert fetch.call_count == 1
                assert post.call_count == (0 if expected == "rejected" else 1)
                events = await replay_events(thread)
                (evidence / "logs" / f"fixture-{case}-audit.json").write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                results.append({"scenario": case, "input_type": "fixture", "thread_id": thread,
                                "confidence": initial.confidence, "branch": result["decision"],
                                "final_action": result["final_action"], "post_attempts": post.call_count,
                                "events": len(events), "result": "passed"})
        # Saved pending states for read-only browser screenshots.
        for kind, confidence in [("approval", 0.65), ("escalation", 0.4)]:
            thread = f"fixture-preview-{kind}-{uuid.uuid4().hex[:8]}"
            llm = Mock()
            llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=analysis(confidence))
            with patch("exercises.exercise_4_audit.fetch_pr", return_value=pull_request()), patch("exercises.exercise_4_audit.get_llm", return_value=llm), patch("exercises.exercise_4_audit.post_review_comment") as post:
                await invoke_review(PR_URL, thread)
                post.assert_not_called()
            previews[kind] = thread
    payload = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "mode": "fixture only; zero external calls", "scenarios": results, "preview_threads": previews}
    (evidence / "offline_demo.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (evidence / "scenario_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=".cache/demo.db")
    args = parser.parse_args()
    asyncio.run(capture(args.db))


if __name__ == "__main__":
    main()
