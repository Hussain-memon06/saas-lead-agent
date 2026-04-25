"""Email send node — real delivery via SendGrid with stub fallback.

Behavior matrix:
- ``email_approved`` is not True → ``send_result = "rejected"`` (default-deny)
- approved + no contact email   → ``send_result = "no_contact"``
- approved + no SENDGRID_API_KEY → ``send_result = "sent"`` (stub mode for
  dev/test without provider credentials — preserves Phase 2 behavior)
- approved + SendGrid call fails → ``send_result = "failed"`` + error appended
- approved + SendGrid 2xx        → ``send_result = "sent"`` + message_id + sent_at
"""

import os
from typing import Any

from saas_lead_agent.email.sendgrid_client import send_email_via_sendgrid
from saas_lead_agent.state import LeadState


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

    # Stub fallback: no SendGrid credentials → record success without delivery.
    # Keeps the Phase 2 contract intact for tests and pre-prod environments.
    if not os.environ.get("SENDGRID_API_KEY"):
        return {"send_result": "sent"}

    try:
        result = await send_email_via_sendgrid(
            to=to_email,
            subject=state.get("email_subject") or "",
            body=state.get("email_body") or "",
        )
    except Exception as exc:
        return {
            "send_result": "failed",
            "errors": [f"send_email: {exc}"],
        }

    return {
        "send_result": "sent",
        "message_id": result.get("message_id"),
        "sent_at": result.get("sent_at"),
    }
