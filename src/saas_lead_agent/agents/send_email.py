"""Email send node — Phase 2 stub.

Marks the outcome of the HITL approval decision without actually delivering
an email.  Phase 3 will replace this with real SMTP or provider API delivery
(SES, SendGrid, etc.) per ADR-006.

Default-deny: if ``email_approved`` is missing or false, the outcome is
``"rejected"``.  Only explicit ``True`` produces ``"sent"``.
"""

from typing import Any

from saas_lead_agent.state import LeadState


async def send_email(state: LeadState) -> dict[str, Any]:
    """LangGraph node: record the send outcome based on the approval decision.

    Args:
        state: Current ``LeadState``; ``email_approved`` is set by
            ``await_approval``.

    Returns:
        ``{"send_result": "sent"}`` if approved; ``{"send_result": "rejected"}``
        otherwise.
    """
    if state.get("email_approved") is True:
        return {"send_result": "sent"}
    return {"send_result": "rejected"}
