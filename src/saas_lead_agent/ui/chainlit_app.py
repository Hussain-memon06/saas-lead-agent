"""Chainlit v2 UI for the lead-research agent.

Mounted on the FastAPI app at ``/chainlit`` (last, after all ``/api`` routes —
mounting before the router would 404 every API endpoint, per CLAUDE.md).

Flow:
  1. user pastes a company URL in the chat
  2. graph runs to ``await_approval``; dossier + draft email shown
  3. AskActionMessage offers Approve / Reject actions
  4. action handler resumes the graph with ``Command(resume=<bool>)``
  5. final ``send_result`` (sent / stubbed / rejected / failed / no_contact) reported

Shares the module-level ``_graph`` from ``api.routes`` so HITL state is the
same regardless of whether the user came in via REST or via the chat UI.
"""

from typing import Any

import chainlit as cl
from langgraph.types import Command

from saas_lead_agent.api import routes as _routes
from saas_lead_agent.api.routes import _config, _domain_from_url, _is_interrupted
from saas_lead_agent.schemas import normalize_public_http_url
from saas_lead_agent.state import LeadState

# ---------------------------------------------------------------------------
# Pure helpers (unit-tested in tests/test_chainlit.py)
# ---------------------------------------------------------------------------


def validate_url(raw: str) -> tuple[bool, str]:
    """Return (is_valid, message_or_url).

    On success the second tuple element is the cleaned URL; on failure it
    is a user-facing error string.
    """
    try:
        return True, normalize_public_http_url(raw)
    except ValueError as exc:
        message = str(exc)
        if message == "url is required":
            return False, "Please paste a company URL."
        if "HTTP/HTTPS" in message:
            return False, "URL must start with http:// or https:// (e.g. https://stripe.com)."
        return False, message


def format_dossier(result: dict[str, Any]) -> str:
    """Render the research result as a Markdown summary for Chainlit."""
    profile = result.get("company_profile") or {}
    contact = result.get("contact") or {}
    signals = result.get("signals") or []
    fit_score = result.get("fit_score")

    lines: list[str] = []
    if profile:
        lines.append(f"### {profile.get('name', 'Unknown company')}")
        if profile.get("tagline"):
            lines.append(f"_{profile['tagline']}_")
        if profile.get("hq"):
            lines.append(f"**HQ:** {profile['hq']}")
        if profile.get("funding_stage"):
            lines.append(f"**Stage:** {profile['funding_stage']}")
        if profile.get("employees_estimate"):
            lines.append(f"**Employees:** {profile['employees_estimate']}")

    if contact and contact.get("email"):
        contact_line = contact.get("name") or contact["email"]
        if contact.get("title"):
            contact_line += f" ({contact['title']})"
        lines.append(f"\n**Contact:** {contact_line} — {contact['email']}")
    elif contact:
        lines.append("\n**Contact:** (no email found)")

    if signals:
        lines.append(f"\n**Buying signals ({len(signals)}):**")
        for sig in signals[:5]:
            title = sig.get("title") or sig.get("type", "signal")
            lines.append(f"- {title}")

    if fit_score is not None:
        lines.append(f"\n**Fit score:** {fit_score}/10")

    return "\n".join(lines) if lines else "(no dossier data)"


def format_email_preview(result: dict[str, Any]) -> str:
    """Render the drafted email as a Markdown preview."""
    subject = result.get("email_subject") or "(no subject)"
    body = result.get("email_body") or "(no body)"
    return f"**Subject:** {subject}\n\n---\n\n{body}"


def format_send_result(result: dict[str, Any]) -> str:
    """Render the post-resume outcome as a one-line status."""
    outcome = result.get("send_result")
    icons = {
        "sent": "✅ Sent",
        "stubbed": "🧪 Stubbed (not delivered)",
        "rejected": "🚫 Rejected (not delivered)",
        "no_contact": "⚠️  No contact email — nothing sent",
        "failed": "❌ Delivery failed",
    }
    base = icons.get(outcome or "", f"Outcome: {outcome}")
    if outcome == "sent" and result.get("message_id"):
        base += f" · message_id={result['message_id']}"
    if outcome == "failed" and result.get("errors"):
        base += f" · {result['errors'][-1]}"
    return base


def _initial_state(url: str, domain: str) -> LeadState:
    return {
        "company_url": url,
        "domain": domain,
        "icp_context": None,
        "messages": [],
        "company_profile": None,
        "contact": None,
        "signals": None,
        "fit_score": None,
        "fit_level": None,
        "score_breakdown": None,
        "score_confidence": None,
        "score_explanation": None,
        "needs_human_review": None,
        "score_reasons": None,
        "score_uncertainty": None,
        "grounding_report": None,
        "outreach_quality": None,
        "email_subject": None,
        "email_body": None,
        "email_approved": None,
        "send_result": None,
        "message_id": None,
        "sent_at": None,
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Chainlit handlers
# ---------------------------------------------------------------------------


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(
        content=(
            "👋 **AI SDR — Lead Research**\n\n"
            "Paste a B2B SaaS company URL "
            "(e.g. `https://stripe.com`) and I'll research it, draft an "
            "outreach email, and ask you to approve before sending."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    is_valid, payload = validate_url(message.content)
    if not is_valid:
        await cl.Message(content=f"❌ {payload}").send()
        return

    url = payload
    domain = _domain_from_url(url)
    thread_id = f"lead:{domain}"
    cl.user_session.set("thread_id", thread_id)

    async with cl.Step(name=f"Researching {domain}", type="run"):
        try:
            result = await _routes._graph.ainvoke(
                _initial_state(url, domain),
                config=_config(thread_id),
                durability="sync",
            )
        except Exception as exc:
            await cl.Message(content=f"❌ Graph execution failed: {exc}").send()
            return

    await cl.Message(content=format_dossier(result)).send()

    if not await _is_interrupted(thread_id):
        # Graph ran straight through (no draft to approve — usually an error path).
        await cl.Message(
            content=(
                "_Graph completed without pausing for approval — "
                f"errors: {result.get('errors') or 'none'}_"
            )
        ).send()
        return

    res = await cl.AskActionMessage(
        content=format_email_preview(result),
        actions=[
            cl.Action(
                name="approve",
                payload={"thread_id": thread_id},
                label="✅ Approve & send",
            ),
            cl.Action(
                name="reject",
                payload={"thread_id": thread_id},
                label="🚫 Reject",
            ),
        ],
        timeout=600,
    ).send()

    if res is None:
        # Timed out — auto-reject so the graph doesn't hang.
        await _resume_graph(thread_id, decision=False)
        await cl.Message(content="⏱️  Timed out — auto-rejected.").send()


async def _resume_graph(thread_id: str, *, decision: bool) -> dict[str, Any]:
    """Resume the paused graph; return the post-resume state dict."""
    result: dict[str, Any] = await _routes._graph.ainvoke(
        Command(resume=decision),
        config=_config(thread_id),
        durability="sync",
    )
    return result


@cl.action_callback("approve")
async def on_approve(action: cl.Action) -> None:
    thread_id = action.payload.get("thread_id") or cl.user_session.get("thread_id")
    if not thread_id:
        await cl.Message(content="❌ No active thread to approve.").send()
        return
    try:
        result = await _resume_graph(thread_id, decision=True)
    except Exception as exc:
        await cl.Message(content=f"❌ Resume failed: {exc}").send()
        return
    await cl.Message(content=format_send_result(result)).send()


@cl.action_callback("reject")
async def on_reject(action: cl.Action) -> None:
    thread_id = action.payload.get("thread_id") or cl.user_session.get("thread_id")
    if not thread_id:
        await cl.Message(content="❌ No active thread to reject.").send()
        return
    try:
        result = await _resume_graph(thread_id, decision=False)
    except Exception as exc:
        await cl.Message(content=f"❌ Resume failed: {exc}").send()
        return
    await cl.Message(content=format_send_result(result)).send()
