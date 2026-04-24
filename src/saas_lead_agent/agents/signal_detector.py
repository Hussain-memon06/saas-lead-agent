"""Signal detector agent node for the LeadState graph."""

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from saas_lead_agent.state import LeadState
from saas_lead_agent.tools.web_search import web_search
from saas_lead_agent.utils import _extract_json_list

_GPT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are a B2B sales intelligence analyst.

Given a company name and domain, use web_search to find recent buying signals.
Run targeted searches for each of these signal types:
  - funding: recent funding rounds, investment announcements, valuations
  - hiring: hiring spikes, surge in job postings, new role categories opening
  - product: product launches, major feature releases, new integrations
  - leadership: new CTO, VP, CEO, or other executive hires or departures
  - partnership: partnerships, acquisitions, mergers, joint ventures

Run up to 5 searches, one per signal type. Then return a JSON array —
no markdown, no explanation, only the JSON array — where each element has
these exact fields:

[
  {
    "signal_type": "funding"|"hiring"|"product"|"leadership"|"partnership"|"other",
    "date":        string | null,
    "source":      string | null,
    "details":     string
  },
  ...
]

Include only signals that are clearly relevant and recent (prefer last 12 months).
If no signals are found for a type, omit it — do not include placeholder entries.
If no signals are found at all, return an empty array [].
Return ONLY the JSON array."""

_signal_detector_agent: Any = None


def build_signal_detector_agent() -> Any:
    """Build the signal detector agent graph.

    Creates a ``create_agent`` ReAct graph with ``web_search`` bound to
    GPT-4o-mini.

    Returns:
        A compiled LangGraph ``CompiledStateGraph`` ready for ``.ainvoke()``.
    """
    model = ChatOpenAI(model=_GPT_MODEL)
    return create_agent(
        model=model,
        tools=[web_search],
        system_prompt=_SYSTEM_PROMPT,
        name="signal_detector",
    )


def _get_signal_detector_agent() -> Any:
    """Return the module-level signal detector agent, initialising it on first call."""
    global _signal_detector_agent
    if _signal_detector_agent is None:
        _signal_detector_agent = build_signal_detector_agent()
    return _signal_detector_agent


async def signal_detector(state: LeadState) -> dict[str, Any]:
    """LangGraph node: detect buying signals for a company.

    Invokes a ReAct agent that runs targeted ``web_search`` calls for each
    signal type, then parses the resulting JSON array into ``signals``.

    Falls back to domain-only search when ``company_profile`` is not yet
    populated (this node runs in parallel with ``company_researcher``).

    On any failure (network error, JSON parse error, unexpected exception) the
    node appends a descriptive string to ``errors`` and returns without raising,
    so the graph can continue gracefully.  An empty list ``[]`` is a valid
    success — it means no signals were found.

    Args:
        state: Current ``LeadState``; ``domain`` must be populated.

    Returns:
        Partial state update dict — one of:
        - ``{"signals": list[dict[str, Any]]}`` on success (may be empty).
        - ``{"errors": [str]}`` on failure.
    """
    domain = state["domain"]
    profile = state.get("company_profile")
    company_name = (profile or {}).get("name") or domain

    agent = _get_signal_detector_agent()
    prompt = f"Find buying signals for company '{company_name}' (domain: {domain})"

    try:
        result: dict[str, Any] = await agent.ainvoke(
            {"messages": [HumanMessage(content=prompt)]}
        )
    except Exception as exc:
        return {"errors": [f"signal_detector: agent invocation failed: {exc}"]}

    messages: list[Any] = result.get("messages", [])
    if not messages:
        return {"errors": ["signal_detector: agent returned no messages"]}

    last = messages[-1]
    raw: str = last.content if isinstance(last.content, str) else str(last.content)

    try:
        signals = _extract_json_list(raw)
    except json.JSONDecodeError as exc:
        return {"errors": [f"signal_detector: JSON parse error — {exc}. Raw: {raw[:200]}"]}
    except ValueError as exc:
        return {"errors": [f"signal_detector: unexpected response shape — {exc}"]}

    return {"signals": signals}
