"""Signal detector agent node for the LeadState graph (Phase 1 stub).

Phase 1: returns an empty signals list so the orchestrator can dispatch all
three subagents in parallel without missing nodes. Phase 2 will add real
buying-signal detection (job postings, funding news, tech-stack signals).
"""

from typing import Any

from saas_lead_agent.state import LeadState


async def signal_detector(state: LeadState) -> dict[str, Any]:
    """LangGraph node: detect buying signals for the company.

    Phase 1 returns an empty list. Phase 2 will use web_search + an LLM
    to surface recent funding announcements, hiring surges, tech-stack
    changes, and other triggers.

    Args:
        state: Current ``LeadState``; ``company_url`` and ``domain`` should
            be populated.

    Returns:
        ``{"signals": list[dict[str, Any]]}`` — empty list in Phase 1.
    """
    return {"signals": []}
