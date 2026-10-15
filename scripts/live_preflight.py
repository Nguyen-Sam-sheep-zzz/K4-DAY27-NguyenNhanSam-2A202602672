"""Read-only GitHub + synthetic structured-output smoke; never posts comments.

Run from the repo root: python -m scripts.live_preflight
Only credential presence and sanitized error types are recorded.
"""
import json
import os
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from exercises.runtime import load_runtime_env

from common.github import fetch_pr
from common.llm import get_llm
from common.schemas import PRAnalysis
from exercises.review_helpers import REVIEW_PROMPT


def main():
    load_runtime_env()
    # This smoke does not opt into any external trace collection.
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "read-only GitHub; synthetic LLM smoke; no posting",
        "python": platform.python_version(),
        "packages": {p: version(p) for p in ["langgraph", "langgraph-checkpoint-sqlite", "streamlit", "langchain-openai"]},
        "configuration": {k: "set" if os.environ.get(k) else "missing" for k in
                          ["OPENROUTER_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "GITHUB_TOKEN", "GITHUB_USER"]},
        "provider_host": urlsplit(os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")).hostname,
        "model": os.environ.get("LLM_MODEL", "openai/gpt-4o-mini"),
        "github": {}, "llm": {},
    }
    try:
        headers = {"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "Accept": "application/vnd.github+json"}
        response = httpx.get("https://api.github.com/user", headers=headers, timeout=20)
        response.raise_for_status()
        login = response.json()["login"]
        result["github"] = {"status": "passed", "authenticated_user": login,
                            "reviewer_identity_matches": login.lower() == os.environ.get("GITHUB_USER", "").lower(), "prs": []}
        for number in (1, 2):
            url = f"https://github.com/VinUni-AI20k/PR-Demo/pull/{number}"
            pr = fetch_pr(url)
            result["github"]["prs"].append({"url": url, "head_sha": pr.head_sha, "files": len(pr.files_changed), "diff_chars": len(pr.diff)})
    except Exception as exc:
        result["github"]["status"] = "failed"
        result["github"]["error_type"] = type(exc).__name__
        if isinstance(exc, httpx.HTTPStatusError):
            result["github"]["http_status"] = exc.response.status_code
    try:
        model = get_llm().with_structured_output(PRAnalysis)
        output = model.invoke([
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": "Title: Correct spelling in README\nDiff:\n--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-Instal the app\n+Install the app\n"},
        ], config={"callbacks": []})
        output = PRAnalysis.model_validate(output)
        result["llm"] = {"status": "passed", "input": "synthetic spelling-only diff", "analysis": output.model_dump()}
    except Exception as exc:
        result["llm"] = {"status": "failed", "error_type": type(exc).__name__}
    folder = Path("evidence")
    folder.mkdir(exist_ok=True)
    (folder / "live_preflight.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["github"].get("status") == result["llm"].get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
