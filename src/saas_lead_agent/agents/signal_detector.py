"""Signal detector agent node for the LeadState graph."""

import json
from time import perf_counter
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from saas_lead_agent.agents.provider_metadata import provider_usage_record
from saas_lead_agent.schemas import CompanySignal
from saas_lead_agent.state import LeadState
from saas_lead_agent.tools import capture_tool_results
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
    "source":      string,
    "details":     string
  },
  ...
]

CRITICAL — precision over recall:
  - The `source` field MUST be a URL whose host contains the exact company
    domain you were given. Signals from other companies with similar names
    MUST NOT be included, even if they appear in search results.
  - If you cannot find a signal whose source URL contains the company domain,
    do not include it. Guessing or substituting a similar company is wrong.
  - If no domain-verified signals are found at all, return an empty array [].
    An empty array is the correct answer when nothing qualifies.

Include only signals that are clearly relevant and recent (prefer last 12 months).
If no signals are found for a type, omit it — do not include placeholder entries.
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


def _filter_by_domain(signals: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
    """Drop signals whose ``source`` URL does not contain the company domain.

    The LLM may hallucinate signals from different companies with similar names
    despite the system prompt.  This post-parse filter enforces the same rule
    mechanically: if the domain substring is not in ``source``, drop the entry.
    A missing/empty ``source`` is treated as unverifiable and dropped.
    """
    if not domain:
        return signals
    filtered: list[dict[str, Any]] = []
    for s in signals:
        source = s.get("source") or ""
        if not isinstance(source, str):
            continue
        if domain.lower() in source.lower():
            filtered.append(s)
    return filtered


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
    invoke_started_at = perf_counter()
    captured_tool_usage: list[dict[str, Any]] = []

    try:
        with capture_tool_results(
            node="signal_detector",
            run_id=state.get("run_id"),
            thread_id=f"lead:{domain}",
        ) as tool_usage:
            result: dict[str, Any] = await agent.ainvoke(
                {"messages": [HumanMessage(content=prompt)]}
            )
    except Exception as exc:
        if "tool_usage" in locals():
            captured_tool_usage.extend(tool_usage)
        return {
            "provider_usage": [
                provider_usage_record(
                    node="signal_detector",
                    provider="openai",
                    model=_GPT_MODEL,
                    started_at=invoke_started_at,
                    status="failed",
                    error_type=type(exc).__name__,
                )
            ],
            "tool_usage": captured_tool_usage,
            "errors": [f"signal_detector: agent invocation failed: {exc}"],
        }
    captured_tool_usage.extend(tool_usage)

    messages: list[Any] = result.get("messages", [])
    usage_record = provider_usage_record(
        node="signal_detector",
        provider="openai",
        model=_GPT_MODEL,
        started_at=invoke_started_at,
        status="completed",
        messages=messages,
    )
    if not messages:
        usage_record["status"] = "empty_response"
        return {
            "provider_usage": [usage_record],
            "tool_usage": captured_tool_usage,
            "errors": ["signal_detector: agent returned no messages"],
        }

    last = messages[-1]
    raw: str = last.content if isinstance(last.content, str) else str(last.content)

    try:
        signals = _extract_json_list(raw)
    except json.JSONDecodeError as exc:
        usage_record["status"] = "invalid_response"
        return {
            "provider_usage": [usage_record],
            "tool_usage": captured_tool_usage,
            "errors": [f"signal_detector: JSON parse error — {exc}. Raw: {raw[:200]}"],
        }
    except ValueError as exc:
        usage_record["status"] = "invalid_response"
        return {
            "provider_usage": [usage_record],
            "tool_usage": captured_tool_usage,
            "errors": [f"signal_detector: unexpected response shape — {exc}"],
        }

    # Precision over recall: drop signals whose source URL does not contain the
    # company domain. LLM may hallucinate entries from similarly-named companies.
    filtered = _filter_by_domain(signals, domain)
    try:
        validated = [CompanySignal.model_validate(signal) for signal in filtered]
    except ValidationError as exc:
        usage_record["status"] = "schema_validation_failed"
        return {
            "provider_usage": [usage_record],
            "tool_usage": captured_tool_usage,
            "errors": [f"signal_detector: schema validation error — {exc}"],
        }
    return {
        "signals": [signal.model_dump() for signal in validated],
        "provider_usage": [usage_record],
        "tool_usage": captured_tool_usage,
    }
