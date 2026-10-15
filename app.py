"""Exercise 5 — browser approval UI backed by durable LangGraph sessions.

Run: uv run streamlit run app.py
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from urllib.parse import urlsplit

import streamlit as st
from exercises.runtime import load_runtime_env

from common.db import replay_events
from exercises.sessions import invoke_review, list_recent_sessions, load_session

load_runtime_env()
st.set_page_config(page_title="HITL PR Review", page_icon="🔎", layout="wide")
for key, default in {"thread_id": None, "pr_url": "", "interrupt_payload": None,
                     "final": None, "error": None, "retryable": False}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def normalize_pr_url(value):
    parts = urlsplit(value.strip())
    if parts.scheme != "https" or parts.netloc != "github.com" or not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*/?", parts.path):
        raise ValueError("Enter a GitHub PR URL: https://github.com/owner/repository/pull/123")
    return "https://github.com" + parts.path.rstrip("/")


def accept_result(result):
    st.session_state.error = None
    st.session_state.pr_url = result.get("pr_url", st.session_state.pr_url)
    st.session_state.retryable = result.get("retryable", False)
    if result.get("__interrupt__"):
        st.session_state.interrupt_payload = result["__interrupt__"][0].value
        st.session_state.final = None
    else:
        st.session_state.interrupt_payload = None
        st.session_state.final = result if result.get("final_action") else None


async def run_graph(pr_url, thread_id, resume_value=None):
    return await invoke_review(pr_url, thread_id, resume_value, confirm_after_escalation=True)


def restore_thread(thread_id):
    result = asyncio.run(load_session(thread_id))
    st.session_state.thread_id = thread_id
    st.query_params["thread"] = thread_id
    accept_result(result)


def recover_after_error(message):
    # Resume may have advanced past the visible interrupt before failing.
    # The checkpoint, rather than the old browser form, is authoritative.
    try:
        accept_result(asyncio.run(load_session(st.session_state.thread_id)))
    except Exception:
        st.session_state.interrupt_payload = None
        st.session_state.final = None
        st.session_state.retryable = False
    st.session_state.error = message


def perform_review(resume_value=None):
    try:
        result = asyncio.run(run_graph(st.session_state.pr_url, st.session_state.thread_id, resume_value))
        accept_result(result)
    except (ValueError, RuntimeError) as exc:
        recover_after_error(str(exc))
    except Exception:
        recover_after_error("Operation failed. Inspect this session's audit trail and configuration.")


def render_approval_card(payload):
    phase = payload.get("phase", "review")
    heading = "Confirm refined review" if phase == "after_escalation" else "Confirm edited review" if phase == "edited_review" else "Approval requested"
    st.subheader(heading)
    st.metric("Review confidence", f"{payload['confidence']:.1%}")
    st.caption(payload["confidence_reasoning"])
    st.markdown(payload["review_body"])
    with st.expander("Diff"):
        st.code(payload.get("diff_preview", ""), language="diff")
        st.caption("Preview shows up to 2,000 characters. Open the PR for the full diff.")
    # Phase and review text make edits receive a fresh widget after resume.
    revision = hashlib.sha256(payload["review_body"].encode()).hexdigest()[:12]
    suffix = f"{st.session_state.thread_id}_{phase}_{revision}"
    body = st.text_area("Review text", value=payload["review_body"], height=180, key=f"body_{suffix}",
                        help="Change the text and select Edit to preview it before approving.")
    feedback = st.text_input("Feedback (optional)", key=f"feedback_{suffix}")
    approve, reject, edit = st.columns(3)
    if approve.button("Approve", type="primary"):
        return {"choice": "approve", "feedback": feedback}
    if reject.button("Reject"):
        return {"choice": "reject", "feedback": feedback}
    if edit.button("Edit"):
        if not body.strip():
            st.warning("The replacement review cannot be empty.")
        else:
            return {"choice": "edit", "feedback": feedback, "edited_body": body}
    return None


def render_escalation_card(payload):
    st.subheader("Strong escalation — reviewer context needed")
    st.metric("Review confidence", f"{payload['confidence']:.1%}")
    st.caption(payload["confidence_reasoning"])
    st.markdown(payload["summary"])
    if payload.get("risk_factors"):
        st.error("Risks: " + "; ".join(payload["risk_factors"]))
    with st.form(f"escalation_{st.session_state.thread_id}"):
        answers = {q: st.text_area(q, key=f"question_{st.session_state.thread_id}_{i}")
                   for i, q in enumerate(payload["questions"])}
        if st.form_submit_button("Submit answers"):
            if any(not value.strip() for value in answers.values()):
                st.warning("Answer every question; say unknown where context is unavailable.")
            else:
                return {q: value.strip() for q, value in answers.items()}
    return None


st.title("HITL PR Review Agent")
st.caption("Review a pull request, resolve uncertainty, and keep a traceable decision history.")

# A browser refresh creates a new Streamlit session; recover using the URL.
if st.session_state.thread_id is None and st.query_params.get("thread"):
    try:
        restore_thread(st.query_params["thread"])
    except Exception:
        st.session_state.error = "This saved session could not be loaded. Choose a recent session or start a new review."

with st.sidebar:
    st.header("Recent sessions")
    try:
        rows = asyncio.run(list_recent_sessions())
        by_id = {row["thread_id"]: row for row in rows}
        selected = st.selectbox("Saved session", [""] + list(by_id),
                                format_func=lambda value: "Choose a session" if not value else
                                f"{by_id[value]['worst_risk'].upper()} · {value[:8]} · {by_id[value]['pr_url'].split('/')[-1]}")
        if st.button("Open session", disabled=not selected):
            try:
                restore_thread(selected)
                st.rerun()
            except (ValueError, RuntimeError):
                st.error("No saved graph state is available for this session.")
        if selected:
            row = by_id[selected]
            st.caption(f"Last event: {row['last_event']} · {row['events']} events")
            st.write(row["pr_url"])
    except Exception:
        st.warning("Recent sessions are temporarily unavailable.")
    st.divider()
    st.caption("≥73%: automatic · 58–<73%: approval · <58%: questions")

with st.form("start"):
    pr_url = st.text_input("PR URL", value=st.session_state.pr_url,
                           placeholder="https://github.com/VinUni-AI20k/PR-Demo/pull/1")
    submitted = st.form_submit_button("Run review")

if submitted:
    try:
        normalized = normalize_pr_url(pr_url)
    except ValueError as exc:
        st.error(str(exc))
    else:
        st.session_state.pr_url = normalized
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.interrupt_payload = None
        st.session_state.final = None
        st.session_state.error = None
        st.query_params["thread"] = st.session_state.thread_id
        with st.spinner("Fetching PR and analyzing changes..."):
            perform_review()

if st.session_state.error:
    st.error(st.session_state.error)
if st.session_state.retryable and st.session_state.thread_id:
    st.info("A previous operation did not finish. Retry continues from its checkpoint.")
    if st.button("Retry operation"):
        perform_review()
        st.rerun()

payload = st.session_state.interrupt_payload
if st.session_state.thread_id and st.session_state.thread_id.startswith("fixture-"):
    st.info("Fixture demo session: analysis and prior posting outcomes are simulated.")
if payload is not None:
    with st.container(border=True):
        answer = render_approval_card(payload) if payload["kind"] == "approval_request" else render_escalation_card(payload)
    if answer is not None:
        with st.spinner("Applying reviewer response..."):
            perform_review(answer)
        st.rerun()

if st.session_state.final is not None:
    final = st.session_state.final
    action = final.get("final_action")
    if action in {"committed", "auto_committed"}:
        st.success("Review comment posted." + (" Automatically routed by confidence." if action == "auto_committed" else ""))
    elif action == "rejected":
        st.warning("Rejected — no comment posted.")
    elif action in {"commit_failed", "auto_commit_failed"}:
        st.error("Posting failed or delivery could not be confirmed. Inspect the PR before retrying to avoid a duplicate.")
    else:
        st.info(f"Review status: {action}")
    if final.get("analysis"):
        st.metric("Final review confidence", f"{final['analysis'].confidence:.1%}")
        st.markdown(final.get("posted_comment_body") or final["analysis"].summary)
    st.link_button("View PR on GitHub", st.session_state.pr_url)

if st.session_state.thread_id:
    st.caption(f"Session: {st.session_state.thread_id}")
    with st.expander("Audit trail"):
        try:
            events = asyncio.run(replay_events(st.session_state.thread_id))
            if events:
                st.dataframe(events, hide_index=True, width="stretch")
            else:
                st.caption("No audit events recorded yet.")
        except Exception:
            st.warning("Audit events could not be loaded.")
