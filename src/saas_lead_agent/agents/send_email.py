"""Email send node — real delivery via SendGrid with explicit stub fallback.

Behavior matrix:
- ``email_approved`` is not True → ``send_result = "rejected"`` (default-deny)
- approved + no contact email   → ``send_result = "no_contact"``
- approved + no SENDGRID_API_KEY and explicit stub enabled → ``send_result = "stubbed"``
- approved + no SENDGRID_API_KEY and no explicit stub → ``send_result = "failed"``
- approved + SendGrid call fails → ``send_result = "failed"`` + error appended
- approved + SendGrid 2xx        → ``send_result = "sent"`` + message_id + sent_at
"""

import os
from typing import Any

from saas_lead_agent.email.idempotency import delivery_idempotency_key
from saas_lead_agent.email.sendgrid_client import run_sendgrid_delivery
from saas_lead_agent.state import LeadState
from saas_lead_agent.tools.recording import capture_tool_results, record_tool_result

_STUB_FLAG = "SENDGRID_STUB_ENABLED"


def _sendgrid_stub_enabled() -> bool:
    return os.environ.get(_STUB_FLAG, "").lower() in {"1", "true", "yes"}


async def send_email(state: LeadState) -> dict[str, Any]:
    """LangGraph node: deliver the approved email and record the outcome.

    Args:
        state: Current ``LeadState``; ``email_approved`` is set by
            ``await_approval``, contact + email_subject + email_body by
            upstream nodes.

    Returns:
        Partial state update with ``send_result`` plus, on success,
        ``message_id`` and ``sent_at``.  On failure, appends to ``errors``.
    """
    if state.get("email_approved") is not True:
        return {"send_result": "rejected"}

    contact = state.get("contact") or {}
    to_email = contact.get("email")
    if not to_email:
        return {"send_result": "no_contact"}

    subject = state.get("email_subject") or ""
    body = state.get("email_body") or ""
    idempotency_key = delivery_idempotency_key(
        run_id=state.get("run_id") or "",
        recipient_email=to_email,
        subject=subject,
        body=body,
    )

    if not os.environ.get("SENDGRID_API_KEY"):
        if _sendgrid_stub_enabled():
            return {
                "send_result": "stubbed",
                "delivery_idempotency_key": idempotency_key,
            }
        return {
            "send_result": "failed",
            "delivery_idempotency_key": idempotency_key,
            "errors": [
                "send_email: SENDGRID_API_KEY is not set; set "
                "SENDGRID_STUB_ENABLED=true for explicit dev stub mode or "
                "configure SendGrid delivery credentials."
            ],
        }

    with capture_tool_results(
        node="send_email",
        run_id=state.get("run_id"),
        thread_id=f"lead:{state.get('domain')}" if state.get("domain") else None,
    ) as tool_usage:
        result = await run_sendgrid_delivery(
            to=to_email,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
        )
        record_tool_result(result)

    if result.metadata.status != "completed" or not isinstance(result.output, dict):
        message = result.error.message if result.error is not None else "SendGrid delivery failed"
        return {
            "send_result": "failed",
            "delivery_idempotency_key": idempotency_key,
            "tool_usage": tool_usage,
            "errors": [f"send_email: {message}"],
        }

    return {
        "send_result": "sent",
        "delivery_idempotency_key": idempotency_key,
        "message_id": result.output.get("message_id"),
        "sent_at": result.output.get("sent_at"),
        "tool_usage": tool_usage,
    }
