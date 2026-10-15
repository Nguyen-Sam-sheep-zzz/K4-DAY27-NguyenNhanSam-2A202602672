"""Deterministic test data; never used as live integration evidence."""
from common.github import PullRequest
from common.schemas import PRAnalysis, ReviewComment

PR_URL = "https://github.com/example/lab/pull/1"
DIFF = "diff --git a/tasks.py b/tasks.py\n--- a/tasks.py\n+++ b/tasks.py\n@@ -1 +1 @@\n-priority = 0\n+priority = 1\n"


def analysis(confidence=0.65, **overrides):
    data = dict(
        summary="Adds task priority.", confidence=confidence,
        confidence_reasoning="Migration behavior needs clarification.",
        risk_factors=["Existing rows may need a migration."],
        comments=[ReviewComment(file="tasks.py", line=1, severity="issue", body="Specify the migration for existing rows.")],
        escalation_questions=["How are existing task rows migrated?"],
    )
    data.update(overrides)
    return PRAnalysis(**data)


def pull_request():
    return PullRequest(
        url=PR_URL, owner="example", repo="lab", number=1,
        title="Add priority", author="student", base_ref="main", head_ref="priority",
        head_sha="a" * 40, diff=DIFF, files_changed=["tasks.py"],
    )
