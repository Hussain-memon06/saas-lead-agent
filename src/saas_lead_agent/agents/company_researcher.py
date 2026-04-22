"""Company researcher agent node for the LeadState graph.

Verified API (langchain 1.2.15 / langgraph-prebuilt 1.0.10):
  from langchain.agents import create_agent
  create_agent(model, tools, *, system_prompt, name) -> CompiledStateGraph

Note: langgraph.prebuilt.create_react_agent is a deprecated shim that
delegates to langchain.agents.create_agent. We import directly from langchain.
"""

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from saas_lead_agent.state import LeadState
from saas_lead_agent.tools.scraper import scrape
from saas_lead_agent.tools.web_search import web_search

_GEMINI_MODEL = "gemini-2.5-flash-lite"

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
  "notable_customers":  [string, ...]
}

Use null for unknown fields. Return ONLY the JSON object."""

# Lazy singleton — avoids requiring GOOGLE_API_KEY at import time.
_researcher_agent: Any = None


def build_researcher_agent() -> Any:
    """Build the company researcher agent graph.

    Creates a ``create_agent`` ReAct graph with ``web_search`` and ``scrape``
    tools bound to Gemini 2.5 Flash-Lite. Reads ``GOOGLE_API_KEY`` from the
    environment via ``ChatGoogleGenerativeAI``.

    Returns:
        A compiled LangGraph ``CompiledStateGraph`` ready for ``.ainvoke()``.
    """
    model = ChatGoogleGenerativeAI(model=_GEMINI_MODEL)
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


def _extract_json(content: str) -> dict[str, Any]:
    """Extract a JSON dict from an LLM response string.

    Handles two common formats:
    - Plain JSON: ``{"name": "Acme", ...}``
    - Markdown-fenced JSON: `` ```json\\n{...}\\n``` ``

    Args:
        content: Raw text from the final ``AIMessage``.

    Returns:
        Parsed dict.

    Raises:
        json.JSONDecodeError: If the text cannot be parsed as JSON.
        ValueError: If the parsed value is not a ``dict``.
    """
    text = content.strip()

    if "```" in text:
        # Split on fences; the block content is between the first and second fence.
        parts = text.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            # Drop optional language tag ("json\n{...}" → "{...}")
            if "\n" in inner:
                inner = inner[inner.index("\n"):].strip()
            text = inner.strip()

    parsed: Any = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
    return parsed


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

    try:
        result: dict[str, Any] = await agent.ainvoke(
            {"messages": [HumanMessage(content=prompt)]}
        )
    except Exception as exc:
        return {"errors": [f"company_researcher: agent invocation failed: {exc}"]}

    messages: list[Any] = result.get("messages", [])
    if not messages:
        return {"errors": ["company_researcher: agent returned no messages"]}

    last = messages[-1]
    raw: str = last.content if isinstance(last.content, str) else str(last.content)

    try:
        profile = _extract_json(raw)
    except json.JSONDecodeError as exc:
        return {"errors": [f"company_researcher: JSON parse error — {exc}. Raw: {raw[:200]}"]}
    except ValueError as exc:
        return {"errors": [f"company_researcher: unexpected response shape — {exc}"]}

    return {"company_profile": profile}
