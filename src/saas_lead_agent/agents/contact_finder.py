"""Contact finder agent node for the LeadState graph."""

import json
from time import perf_counter
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from saas_lead_agent.agents.provider_metadata import provider_usage_record
from saas_lead_agent.schemas import Contact
from saas_lead_agent.state import LeadState
from saas_lead_agent.tools.hunter import hunt_contact
from saas_lead_agent.utils import _extract_json

_GPT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are a B2B sales intelligence assistant.

Given a company domain, call hunt_contact to find the primary decision-maker,
then return a single JSON object — no markdown, no explanation, only the JSON —
with these exact fields:

{
  "name":       string | null,
  "title":      string | null,
  "email":      string | null,
  "linkedin":   string | null,
  "confidence": number | null,
  "source":     "hunter"
}

If hunt_contact returns an empty result, return the JSON with all fields null
except source. Use null for unknown fields. Return ONLY the JSON object."""

_contact_finder_agent: Any = None


def build_contact_finder_agent() -> Any:
    """Build the contact finder agent graph.

    Creates a ``create_agent`` ReAct graph with ``hunt_contact`` bound to
    GPT-4o-mini.

    Returns:
        A compiled LangGraph ``CompiledStateGraph`` ready for ``.ainvoke()``.
    """
    model = ChatOpenAI(model=_GPT_MODEL)
    return create_agent(
        model=model,
        tools=[hunt_contact],
        system_prompt=_SYSTEM_PROMPT,
        name="contact_finder",
    )


def _get_contact_finder_agent() -> Any:
    """Return the module-level contact finder agent, initialising it on first call."""
    global _contact_finder_agent
    if _contact_finder_agent is None:
        _contact_finder_agent = build_contact_finder_agent()
    return _contact_finder_agent


async def contact_finder(state: LeadState) -> dict[str, Any]:
    """LangGraph node: find the primary decision-maker contact for a domain.

    Invokes a ReAct agent that calls ``hunt_contact`` then normalises the
    result into a canonical contact dict. The last ``AIMessage`` in the
    returned message list is parsed and written to ``contact``.

    On any failure (API error, JSON parse error, unexpected exception) the
    node appends a descriptive string to ``errors`` and returns without
    raising, so the graph can continue gracefully.

    Args:
        state: Current ``LeadState``; ``domain`` must be populated.

    Returns:
        Partial state update dict — one of:
        - ``{"contact": dict[str, Any]}`` on success.
        - ``{"errors": [str]}`` on failure.
    """
    domain = state["domain"]
    agent = _get_contact_finder_agent()
    prompt = f"Find the primary decision-maker contact for domain: {domain}"
    invoke_started_at = perf_counter()

    try:
        result: dict[str, Any] = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
    except Exception as exc:
        return {
            "provider_usage": [
                provider_usage_record(
                    node="contact_finder",
                    provider="openai",
                    model=_GPT_MODEL,
                    started_at=invoke_started_at,
                    status="failed",
                    error_type=type(exc).__name__,
                )
            ],
            "errors": [f"contact_finder: agent invocation failed: {exc}"],
        }

    messages: list[Any] = result.get("messages", [])
    usage_record = provider_usage_record(
        node="contact_finder",
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
            "errors": ["contact_finder: agent returned no messages"],
        }

    last = messages[-1]
    raw: str = last.content if isinstance(last.content, str) else str(last.content)

    try:
        contact = _extract_json(raw)
    except json.JSONDecodeError as exc:
        usage_record["status"] = "invalid_response"
        return {
            "provider_usage": [usage_record],
            "errors": [f"contact_finder: JSON parse error — {exc}. Raw: {raw[:200]}"],
        }
    except ValueError as exc:
        usage_record["status"] = "invalid_response"
        return {
            "provider_usage": [usage_record],
            "errors": [f"contact_finder: unexpected response shape — {exc}"],
        }

    try:
        validated = Contact.model_validate(contact)
    except ValidationError as exc:
        usage_record["status"] = "schema_validation_failed"
        return {
            "provider_usage": [usage_record],
            "errors": [f"contact_finder: schema validation error — {exc}"],
        }
    return {"contact": validated.model_dump(), "provider_usage": [usage_record]}
