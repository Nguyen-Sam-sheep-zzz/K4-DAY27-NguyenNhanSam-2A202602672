"""Exercise 4: structured audit, durable HITL and resumable CLI.

Request events live in upstream nodes so ordinary interrupt/resume does not
repeat them. Audit events and checkpoints have different purposes. Neither
alone guarantees exactly-once GitHub delivery across a crash during POST.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import time
import uuid

from exercises.runtime import load_runtime_env
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from rich.console import Console

from common.db import write_audit_event
from common.github import fetch_pr, post_review_comment
from common.llm import get_llm
from common.schemas import AUTO_APPROVE_THRESHOLD, ESCALATE_THRESHOLD, AuditEntry, PRAnalysis, ReviewState, risk_level_for
from exercises.exercise_2_hitl import prompt_human
from exercises.review_helpers import (
    REVIEW_PROMPT, approval_payload, checkpoint_serializer, escalation_questions,
    render_comment_body, synthesis_messages, validate_answers, validate_approval,
)

console = Console()
AGENT_ID = "pr-review-agent@v0.1"


async def audit(state, entry: AuditEntry) -> None:
    await write_audit_event(thread_id=state["thread_id"], pr_url=state["pr_url"], entry=entry)


async def _event(state, action, decision, reason, started, *, analysis=None, human=False):
    a = analysis or state.get("analysis")
    await audit(state, AuditEntry(
        agent_id=AGENT_ID, action=action,
        confidence=a.confidence if a else 0.0,
        risk_level=risk_level_for(a.confidence) if a else "med",
        reviewer_id=os.environ.get("GITHUB_USER") if human else None,
        decision=decision, reason=reason,
        execution_time_ms=max(0, int((time.monotonic() - started) * 1000)),
    ))


async def node_fetch_pr(state):
    started = time.monotonic()
    try:
        pr = await asyncio.to_thread(fetch_pr, state["pr_url"])
    except Exception as exc:
        await _event(state, "fetch_pr", "failed", f"GitHub fetch failed ({type(exc).__name__})", started)
        raise RuntimeError("Unable to fetch PR. Check URL, token and network.") from None
    await _event(state, "fetch_pr", "pending", f"Fetched {len(pr.files_changed)} files, head={pr.head_sha}", started)
    return {"pr_title": pr.title, "pr_author": pr.author, "pr_diff": pr.diff,
            "pr_files": pr.files_changed, "pr_head_sha": pr.head_sha}


async def node_analyze(state):
    started = time.monotonic()
    try:
        a = await get_llm().with_structured_output(PRAnalysis).ainvoke([
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": f"Title: {state['pr_title']}\nDiff:\n{state['pr_diff']}"},
        ])
        a = PRAnalysis.model_validate(a)
    except Exception as exc:
        await _event(state, "analyze", "failed", f"LLM analysis failed ({type(exc).__name__})", started)
        raise RuntimeError("LLM analysis failed. Check provider/model and structured-output support.") from None
    await _event(state, "analyze", "pending", a.confidence_reasoning, started, analysis=a)
    return {"analysis": a}


async def node_route(state):
    started = time.monotonic()
    c = state["analysis"].confidence
    decision = "auto_approve" if c >= AUTO_APPROVE_THRESHOLD else "escalate" if c < ESCALATE_THRESHOLD else "human_approval"
    audit_decision = {"auto_approve": "auto", "human_approval": "pending", "escalate": "escalate"}[decision]
    await _event(state, "route", audit_decision, f"confidence={c:.4f}; branch={decision}", started)
    return {"decision": decision}


async def node_approval_requested(state):
    phase = "escalation_confirmation_requested" if state.get("escalation_answers") else "human_approval_requested"
    await _event(state, phase, "pending", "Waiting for approve/reject/edit", time.monotonic())
    return {}


async def node_human_approval(state):
    phase = "after_escalation" if state.get("escalation_answers") else "review"
    if state.get("human_choice") == "edit":
        phase = "edited_review"
    # No external side effect before interrupt in this node.
    response = validate_approval(interrupt(approval_payload(state, phase=phase)))
    await _event(state, "human_approval", response["choice"], response["feedback"] or response["choice"], time.monotonic(), human=True)
    updates = {"human_choice": response["choice"], "human_feedback": response["feedback"]}
    if response["choice"] == "edit":
        updates["posted_comment_body"] = response["edited_body"]
    return updates


def _render_comment_body(state):
    return render_comment_body(state)


def _post(state):
    # Do not retry a timeout automatically: delivery can be ambiguous.
    try:
        post_review_comment(state["pr_url"], _render_comment_body(state))
        return "committed"
    except Exception:
        return "commit_failed"


async def node_commit(state):
    started = time.monotonic()
    if state.get("human_choice") == "approve" or (state.get("escalation_answers") and not state.get("human_choice")):
        action = await asyncio.to_thread(_post, state)
    else:
        action = "rejected"
    decision = "failed" if action == "commit_failed" else "reject" if action == "rejected" else "approve"
    await _event(state, "commit", decision, action, started, human=bool(state.get("human_choice")))
    return {"final_action": action, "posted_comment_body": _render_comment_body(state) if action == "committed" else state.get("posted_comment_body")}


async def node_auto_approve(state):
    started = time.monotonic()
    action = await asyncio.to_thread(_post, state)
    await _event(state, "auto_approve", "auto" if action == "committed" else "failed", action, started)
    return {"final_action": f"auto_{action}", "posted_comment_body": _render_comment_body(state) if action == "committed" else None}


async def node_escalation_requested(state):
    await _event(state, "escalation_requested", "pending", "Questions: " + " | ".join(escalation_questions(state)), time.monotonic())
    return {}


async def node_escalate(state):
    a = state["analysis"]
    questions = escalation_questions(state)
    answers = interrupt({
        "kind": "escalation", "pr_url": state["pr_url"], "confidence": a.confidence,
        "confidence_reasoning": a.confidence_reasoning, "summary": a.summary,
        "risk_factors": a.risk_factors, "questions": questions,
    })
    answers = validate_answers(questions, answers)
    reason = " | ".join(f"Q: {q} A: {answer}" for q, answer in answers.items())
    await _event(state, "escalate", "escalate", reason, time.monotonic(), human=True)
    return {"escalation_answers": answers}


async def node_synthesize(state):
    started = time.monotonic()
    try:
        refined = await get_llm().with_structured_output(PRAnalysis).ainvoke(synthesis_messages(state))
        refined = PRAnalysis.model_validate(refined)
    except Exception as exc:
        await _event(state, "synthesize", "failed", f"LLM synthesis failed ({type(exc).__name__})", started)
        raise RuntimeError("LLM synthesis failed; nothing has been posted.") from None
    await _event(state, "synthesize", "pending", refined.confidence_reasoning, started, analysis=refined)
    return {"analysis": refined, "posted_comment_body": None}


def build_graph(checkpointer, *, confirm_after_escalation=False):
    g = StateGraph(ReviewState)
    for name, fn in [
        ("fetch_pr", node_fetch_pr), ("analyze", node_analyze), ("route", node_route),
        ("auto_approve", node_auto_approve), ("approval_requested", node_approval_requested),
        ("human_approval", node_human_approval), ("commit", node_commit),
        ("escalation_requested", node_escalation_requested), ("escalate", node_escalate),
        ("synthesize", node_synthesize),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "fetch_pr")
    g.add_edge("fetch_pr", "analyze")
    g.add_edge("analyze", "route")
    g.add_conditional_edges("route", lambda s: s["decision"], {
        "auto_approve": "auto_approve", "human_approval": "approval_requested", "escalate": "escalation_requested",
    })
    g.add_edge("approval_requested", "human_approval")
    g.add_conditional_edges("human_approval", lambda s: "edit" if s["human_choice"] == "edit" else "done",
                            {"edit": "approval_requested", "done": "commit"})
    g.add_edge("escalation_requested", "escalate")
    g.add_edge("escalate", "synthesize")
    g.add_edge("synthesize", "approval_requested" if confirm_after_escalation else "commit")
    g.add_edge("auto_approve", END)
    g.add_edge("commit", END)
    checkpointer.serde = checkpoint_serializer()
    return g.compile(checkpointer=checkpointer)


def handle_interrupt(payload):
    if payload["kind"] == "approval_request":
        return prompt_human(payload)
    console.print(payload["summary"], markup=False)
    console.print("Risks: " + ", ".join(payload["risk_factors"]), markup=False)
    return {q: console.input(f"Q: {q}\nA: ").strip() for q in payload["questions"]}


async def run(pr_url, thread_id=None):
    from exercises.sessions import invoke_review
    thread_id = thread_id or str(uuid.uuid4())
    console.print(f"thread_id = {thread_id}")
    result = await invoke_review(pr_url, thread_id, confirm_after_escalation=False)
    while "__interrupt__" in result:
        response = handle_interrupt(result["__interrupt__"][0].value)
        result = await invoke_review(pr_url, thread_id, response, confirm_after_escalation=False)
    console.print(f"final_action = {result.get('final_action')}")
    console.print(f"Replay: uv run python -m audit.replay --thread {thread_id}")
    return result


def main():
    load_runtime_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", required=True)
    parser.add_argument("--thread", help="Restore an existing thread instead of starting over")
    args = parser.parse_args()
    asyncio.run(run(args.pr, args.thread))


if __name__ == "__main__":
    main()
