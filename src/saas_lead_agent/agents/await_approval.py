"""Human-in-the-loop approval gate for the outreach email.

Pauses the graph AFTER dossier_writer has produced a draft, BEFORE send_email
runs.  The client resumes via ``graph.ainvoke(Command(resume=<bool>), config)``:

  - ``True``  → email_approved=True; send_email proceeds
  - ``False`` → email_approved=False; send_email marks as rejected

The node is intentionally cheap: it calls ``interrupt()`` and nothing else.
LangGraph re-executes a node from its start on resume, so any expensive work
here would run twice — keeping the LLM call in dossier_writer avoids that.
"""

from typing import Any

from langgraph.types import interrupt

from saas_lead_agent.state import LeadState


async def await_approval(state: LeadState) -> dict[str, Any]:
    """LangGraph node: pause until a human approves or rejects the email draft.

    Surfaces the drafted subject/body plus fit_score to the client so a UI
    can display the decision context at the pause point.

    Args:
        state: Current ``LeadState``; ``email_subject``, ``email_body``, and
            ``fit_score`` should be populated by ``dossier_writer``.

    Returns:
        ``{"email_approved": bool}`` — the resume value coerced to bool.
    """
    decision = interrupt(
        {
            "type": "email_approval",
            "email_subject": state.get("email_subject"),
            "email_body": state.get("email_body"),
            "fit_score": state.get("fit_score"),
            "fit_level": state.get("fit_level"),
            "score_confidence": state.get("score_confidence"),
            "needs_human_review": state.get("needs_human_review"),
        }
    )
    return {"email_approved": bool(decision)}
