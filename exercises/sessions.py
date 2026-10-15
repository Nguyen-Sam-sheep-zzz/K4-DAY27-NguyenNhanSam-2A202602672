"""Durable session access shared by CLI and Streamlit.

Every operation owns its SQLite connection/event loop. Loading is read-only
with respect to graph execution: it cannot fetch, analyze or post a review.
"""
from contextlib import asynccontextmanager

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from common.db import db_conn, db_path
from exercises.exercise_4_audit import build_graph
from exercises.review_helpers import checkpoint_serializer


@asynccontextmanager
async def open_graph(*, confirm_after_escalation=True):
    async with aiosqlite.connect(db_path()) as conn:
        cp = AsyncSqliteSaver(conn, serde=checkpoint_serializer())
        await cp.setup()
        yield build_graph(cp, confirm_after_escalation=confirm_after_escalation)


def snapshot_result(snapshot):
    result = dict(snapshot.values)
    interrupts = tuple(item for task in snapshot.tasks for item in task.interrupts)
    if interrupts:
        result["__interrupt__"] = interrupts
    elif snapshot.next:
        result["retryable"] = True
    return result


async def load_session(thread_id):
    async with open_graph() as graph:
        snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        if not snapshot.values:
            raise ValueError("No checkpoint exists for this session.")
        return snapshot_result(snapshot)


async def invoke_review(pr_url, thread_id, resume_value=None, *, confirm_after_escalation=True):
    cfg = {"configurable": {"thread_id": thread_id}}
    async with open_graph(confirm_after_escalation=confirm_after_escalation) as graph:
        snapshot = await graph.aget_state(cfg)
        if snapshot.values:
            if snapshot.values.get("pr_url") != pr_url:
                raise ValueError("This thread belongs to a different PR. Start a new session.")
            if not snapshot.next:
                if resume_value is not None:
                    raise ValueError("This session is already complete.")
                return snapshot_result(snapshot)
            if resume_value is None:
                if any(task.interrupts for task in snapshot.tasks):
                    return snapshot_result(snapshot)
                # Retry a failed non-terminal operation from its checkpoint.
                return await graph.ainvoke(None, cfg)
            if not isinstance(resume_value, dict) or not resume_value:
                raise ValueError("A non-empty reviewer response is required.")
            return await graph.ainvoke(Command(resume=resume_value), cfg)
        if resume_value is not None:
            raise ValueError("Cannot resume a session without a checkpoint.")
        return await graph.ainvoke({"pr_url": pr_url, "thread_id": thread_id}, cfg)


async def list_recent_sessions():
    async with db_conn() as conn:
        async with conn.execute("""
            SELECT thread_id, pr_url, MIN(timestamp) AS started,
                   MAX(timestamp) AS last_event, COUNT(*) AS events,
                   CASE MAX(CASE risk_level WHEN 'high' THEN 3 WHEN 'med' THEN 2 ELSE 1 END)
                        WHEN 3 THEN 'high' WHEN 2 THEN 'med' ELSE 'low' END AS worst_risk
              FROM audit_events GROUP BY thread_id, pr_url
             ORDER BY MAX(timestamp) DESC LIMIT 25
        """) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


