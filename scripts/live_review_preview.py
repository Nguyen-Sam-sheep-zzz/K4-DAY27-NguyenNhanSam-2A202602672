"""Exercise 1 on public PRs: real fetch/LLM/routing, no publishing nodes."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from exercises.runtime import load_runtime_env
from exercises.exercise_1_confidence import build_graph
from exercises.review_helpers import render_comment_body


def main():
    load_runtime_env()
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    folder = Path("evidence")
    (folder / "previews").mkdir(parents=True, exist_ok=True)
    results = []
    for number in (1, 2):
        url = f"https://github.com/VinUni-AI20k/PR-Demo/pull/{number}"
        started = time.monotonic()
        row = {"pr_url": url}
        try:
            state = build_graph().invoke({"pr_url": url})
            row.update(status="passed", head_sha=state["pr_head_sha"],
                       files=state["pr_files"], decision=state["decision"],
                       analysis=state["analysis"].model_dump(),
                       elapsed_ms=round((time.monotonic() - started) * 1000))
            (folder / "previews" / f"pr-{number}-review.md").write_text(
                f"<!-- Preview only; never posted. PR head: {state['pr_head_sha']} -->\n\n"
                + render_comment_body(state) + "\n", encoding="utf-8")
        except Exception as exc:
            row.update(status="failed", error_type=type(exc).__name__)
        results.append(row)
        payload = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                   "mode": "real GitHub fetch + real LLM; exercise 1 terminal nodes only; no publishing",
                   "model": os.environ.get("LLM_MODEL"),
                   "provider_host": urlsplit(os.environ.get("LLM_BASE_URL", "")).hostname,
                   "results": results, "github_post_requests": 0}
        (folder / "live_review_preview.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if all(row["status"] == "passed" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
