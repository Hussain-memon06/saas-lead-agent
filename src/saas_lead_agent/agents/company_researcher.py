"""Company researcher agent node for the LeadState graph.

Verified API (langchain 1.2.15 / langgraph-prebuilt 1.0.10):
  from langchain.agents import create_agent
  create_agent(model, tools, *, system_prompt, name) -> CompiledStateGraph

Note: langgraph.prebuilt.create_react_agent is a deprecated shim that
delegates to langchain.agents.create_agent. We import directly from langchain.
"""

import json
from time import perf_counter
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from saas_lead_agent.agents.provider_metadata import provider_usage_record
from saas_lead_agent.schemas import CompanyProfile
from saas_lead_agent.state import LeadState
from saas_lead_agent.tools import capture_tool_results
from saas_lead_agent.tools.scraper import scrape
from saas_lead_agent.tools.web_search import web_search
from saas_lead_agent.utils import _extract_json

_GPT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are a B2B SaaS research analyst.

Given a company URL, use the web_search and scrape tools to research the company,
then return a single JSON object — no markdown, no explanation, only the JSON — with
these exact fields:

{
  "name":               string,
  "tagline":            string | null,
  "hq":                 string | null,
  "employees_estimate": string | null,
  "funding_stage":      "Seed"|"Series A"|"Series B"|"Series C+"|"Public"|"Bootstrapped"|"Unknown",
  "products":           [string, ...],
  "notable_customers":  [string, ...],
  "sources":            [string, ...]
}

CRITICAL — precision over recall:
  - Scrape the given company URL first. Only use information found directly
    on the company's own website, OR on sources (news articles, press releases,
    directories) that explicitly reference the exact URL you were given.
  - Do NOT include information about different companies with similar names.
    Many startups share names across industries; name collision is common.
  - If a field cannot be verified from a source that references the given URL,
    use null. An empty/null field is correct when information is unverifiable.

The `sources` array MUST list every URL you pulled information from. At least
one URL in `sources` MUST contain the company's domain. If you cannot find
sources that reference the given URL, return an empty `sources` array and set
all other fields to null.

Use null for unknown fields. Return ONLY the JSON object."""

# Lazy singleton — avoids requiring OPENAI_API_KEY at import time.
_researcher_agent: Any = None


def build_researcher_agent() -> Any:
    """Build the company researcher agent graph.

    Creates a ``create_agent`` ReAct graph with ``web_search`` and ``scrape``
    tools bound to GPT-4o-mini.

    Returns:
        A compiled LangGraph ``CompiledStateGraph`` ready for ``.ainvoke()``.
    """
    model = ChatOpenAI(model=_GPT_MODEL)
    return create_agent(
        model=model,
        tools=[web_search, scrape],
        system_prompt=_SYSTEM_PROMPT,
        name="company_researcher",
    )


def _get_researcher_agent() -> Any:
    """Return the module-level researcher agent, initialising it on first call."""
    global _researcher_agent
    if _researcher_agent is None:
        _researcher_agent = build_researcher_agent()
    return _researcher_agent


def _verify_sources(profile: dict[str, Any], domain: str) -> dict[str, Any]:
    """Reset unverifiable profile fields to null if no source URL covers the domain.

    Precision guard: a profile is only trusted if at least one URL in
    ``profile["sources"]`` contains the company domain (case-insensitive
    substring).  Otherwise the model likely pulled info from a different
    company with a similar name — wipe everything except ``name`` (which
    the caller supplied via the URL) and ``sources`` (kept for debugging).
    """
    sources_val = profile.get("sources")
    sources: list[str] = [s for s in (sources_val or []) if isinstance(s, str)]

    domain_lower = (domain or "").lower()
    has_domain_source = any(domain_lower in s.lower() for s in sources) if domain_lower else False

    if has_domain_source:
        return profile

    return {
        "name": profile.get("name"),
        "tagline": None,
        "hq": None,
        "employees_estimate": None,
        "funding_stage": None,
        "products": [],
        "notable_customers": [],
        "sources": sources,
    }


async def company_researcher(state: LeadState) -> dict[str, Any]:
    """LangGraph node: research a company URL and populate ``company_profile``.

    Invokes a ReAct agent that loops over ``web_search`` + ``scrape`` tool calls
    until the model produces a final JSON profile. The last ``AIMessage`` in the
    returned message list is parsed and written to ``company_profile``.

    On any failure (network error, JSON parse error, unexpected exception) the
    node appends a descriptive string to ``errors`` and returns without raising,
    so the graph can continue gracefully.

    Args:
        state: Current ``LeadState``; ``company_url`` must be populated.

    Returns:
        Partial state update dict — one of:
        - ``{"company_profile": dict[str, Any]}`` on success.
        - ``{"errors": [str]}`` on failure (appended via the ``operator.add`` reducer).
    """
    url = state["company_url"]
    agent = _get_researcher_agent()
    prompt = f"Research this company and return the JSON profile: {url}"
    invoke_started_at = perf_counter()
    captured_tool_usage: list[dict[str, Any]] = []

    try:
        with capture_tool_results(
            node="company_researcher",
            run_id=state.get("run_id"),
            thread_id=f"lead:{state['domain']}",
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
                    node="company_researcher",
                    provider="openai",
                    model=_GPT_MODEL,
                    started_at=invoke_started_at,
                    status="failed",
                    error_type=type(exc).__name__,
                )
            ],
            "tool_usage": captured_tool_usage,
            "errors": [f"company_researcher: agent invocation failed: {exc}"],
        }
    captured_tool_usage.extend(tool_usage)

    messages: list[Any] = result.get("messages", [])
    usage_record = provider_usage_record(
        node="company_researcher",
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
            "errors": ["company_researcher: agent returned no messages"],
        }

    last = messages[-1]
    raw: str = last.content if isinstance(last.content, str) else str(last.content)

    try:
        profile = _extract_json(raw)
    except json.JSONDecodeError as exc:
        usage_record["status"] = "invalid_response"
        return {
            "provider_usage": [usage_record],
            "tool_usage": captured_tool_usage,
            "errors": [f"company_researcher: JSON parse error — {exc}. Raw: {raw[:200]}"],
        }
    except ValueError as exc:
        usage_record["status"] = "invalid_response"
        return {
            "provider_usage": [usage_record],
            "tool_usage": captured_tool_usage,
            "errors": [f"company_researcher: unexpected response shape — {exc}"],
        }

    # Precision over recall: if no source URL contains the company domain,
    # the model likely pulled info from a different company. Wipe fields.
    verified = _verify_sources(profile, state["domain"])
    try:
        validated = CompanyProfile.model_validate(verified)
    except ValidationError as exc:
        usage_record["status"] = "schema_validation_failed"
        return {
            "provider_usage": [usage_record],
            "tool_usage": captured_tool_usage,
            "errors": [f"company_researcher: schema validation error — {exc}"],
        }
    return {
        "company_profile": validated.model_dump(),
        "provider_usage": [usage_record],
        "tool_usage": captured_tool_usage,
    }
