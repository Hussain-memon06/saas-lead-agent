"""Contact finder agent node for the LeadState graph (Phase 1 stub).

Phase 1: returns a placeholder contact dict so the orchestrator can dispatch
all three subagents in parallel without missing nodes. Phase 2 will replace
this with a real Hunter.io lookup + LLM enrichment.
"""

from typing import Any

from saas_lead_agent.state import LeadState

_PLACEHOLDER_CONTACT: dict[str, Any] = {
    "name": None,
    "title": None,
    "email": None,
    "linkedin": None,
    "source": "stub",
}


async def contact_finder(state: LeadState) -> dict[str, Any]:
    """LangGraph node: find the primary decision-maker contact for the company.

    Phase 1 returns a placeholder dict. Phase 2 will call Hunter.io and an
    LLM enrichment step to populate name, title, and email.

    Args:
        state: Current ``LeadState``; ``domain`` should be populated.

    Returns:
        ``{"contact": dict[str, Any]}`` — placeholder in Phase 1.
    """
    return {"contact": {**_PLACEHOLDER_CONTACT, "domain": state.get("domain")}}
