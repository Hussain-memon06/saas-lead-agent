"""Orchestrator supervisor agent node for the LeadState graph.

Dispatches company_researcher, contact_finder, and signal_detector in a
single super-step by binding each as a tool and letting the model emit
parallel tool calls.  The orchestrator itself is a LangGraph node — it
receives LeadState, runs the create_agent ReAct loop, then merges all
sub-results back into the state.

Architecture:
  - Each subagent is wrapped as a @tool so the LLM can call them.
  - The model naturally emits multiple tool calls in one generation step
    when instructed to run them all at once (parallel dispatch).
  - Results from each tool are merged into the state dict returned by
    this node.
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from saas_lead_agent.agents.company_researcher import company_researcher
from saas_lead_agent.agents.contact_finder import contact_finder
from saas_lead_agent.agents.signal_detector import signal_detector
from saas_lead_agent.state import LeadState
from saas_lead_agent.utils import _extract_json

_GEMINI_MODEL = "gemini-2.5-flash-lite"

_SYSTEM_PROMPT = """You are a lead-research orchestrator.

Given a company URL and domain, call all three research tools simultaneously:
  - run_company_researcher: gathers company profile (name, funding, products, …)
  - run_contact_finder: finds the primary decision-maker contact
  - run_signal_detector: detects buying signals (funding, hiring, tech stack)

Call all three tools in a single response. After all three return, output a
single JSON object with keys "company_profile", "contact", and "signals"
containing the raw JSON strings returned by each tool. No explanation — only
the JSON object."""

_orchestrator_agent: Any = None


@tool
async def run_company_researcher(state_json: str) -> str:
    """Run the company_researcher subagent on the provided LeadState JSON.

    Args:
        state_json: JSON-serialised LeadState dict.

    Returns:
        JSON string of the partial state update (``company_profile`` key).
    """
    state: LeadState = json.loads(state_json)
    result = await company_researcher(state)
    return json.dumps(result)


@tool
async def run_contact_finder(state_json: str) -> str:
    """Run the contact_finder subagent on the provided LeadState JSON.

    Args:
        state_json: JSON-serialised LeadState dict.

    Returns:
        JSON string of the partial state update (``contact`` key).
    """
    state: LeadState = json.loads(state_json)
    result = await contact_finder(state)
    return json.dumps(result)


@tool
async def run_signal_detector(state_json: str) -> str:
    """Run the signal_detector subagent on the provided LeadState JSON.

    Args:
        state_json: JSON-serialised LeadState dict.

    Returns:
        JSON string of the partial state update (``signals`` key).
    """
    state: LeadState = json.loads(state_json)
    result = await signal_detector(state)
    return json.dumps(result)


def build_orchestrator_agent() -> Any:
    """Build the orchestrator agent graph.

    Creates a ``create_agent`` ReAct graph with the three subagent tools
    bound to Gemini 2.5 Flash-Lite.

    Returns:
        A compiled LangGraph ``CompiledStateGraph`` ready for ``.ainvoke()``.
    """
    from langchain.agents import create_agent

    model = ChatGoogleGenerativeAI(model=_GEMINI_MODEL)
    return create_agent(
        model=model,
        tools=[run_company_researcher, run_contact_finder, run_signal_detector],
        system_prompt=_SYSTEM_PROMPT,
        name="orchestrator",
    )


def _get_orchestrator_agent() -> Any:
    """Return the module-level orchestrator agent, initialising it on first call."""
    global _orchestrator_agent
    if _orchestrator_agent is None:
        _orchestrator_agent = build_orchestrator_agent()
    return _orchestrator_agent


def _parse_orchestrator_output(raw: str) -> dict[str, Any]:
    """Parse the orchestrator's final JSON output into a partial state dict.

    The orchestrator is prompted to return a JSON object with keys
    ``company_profile``, ``contact``, and ``signals``.  Each value may be
    a nested dict/list or a JSON-encoded string (if the subagent returned
    a string).

    Args:
        raw: Final AIMessage content from the orchestrator agent.

    Returns:
        Partial state dict with any of the three keys present.

    Raises:
        json.JSONDecodeError: If ``raw`` cannot be parsed.
        ValueError: If the parsed value is not a dict.
    """
    parsed = _extract_json(raw)

    update: dict[str, Any] = {}
    for key in ("company_profile", "contact", "signals"):
        if key not in parsed:
            continue
        val = parsed[key]
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except json.JSONDecodeError:
                pass
        # Unwrap one level if the subagent wrapped its result in the key name.
        if isinstance(val, dict) and key in val:
            val = val[key]
        update[key] = val

    return update


async def orchestrator(state: LeadState) -> dict[str, Any]:
    """LangGraph node: orchestrate parallel research on a company URL.

    Dispatches ``company_researcher``, ``contact_finder``, and
    ``signal_detector`` in a single super-step via parallel tool calls.
    Merges the three partial state updates and returns them as one dict.

    On any failure the node appends to ``errors`` and returns whatever
    partial results were collected, so the graph continues gracefully.

    Args:
        state: Current ``LeadState``; ``company_url`` and ``domain`` must
            be populated.

    Returns:
        Partial state update with any subset of ``company_profile``,
        ``contact``, ``signals``, and ``errors``.
    """
    agent = _get_orchestrator_agent()

    state_json = json.dumps(
        {
            "company_url": state["company_url"],
            "domain": state["domain"],
            "messages": [],
            "company_profile": None,
            "contact": None,
            "signals": None,
            "errors": [],
        }
    )
    prompt = (
        f"Research the company at {state['company_url']} (domain: {state['domain']}).\n"
        f"Pass this state to each tool: {state_json}"
    )

    try:
        result: dict[str, Any] = await agent.ainvoke(
            {"messages": [HumanMessage(content=prompt)]}
        )
    except Exception as exc:
        return {"errors": [f"orchestrator: agent invocation failed: {exc}"]}

    messages: list[Any] = result.get("messages", [])
    if not messages:
        return {"errors": ["orchestrator: agent returned no messages"]}

    last = messages[-1]
    raw: str = last.content if isinstance(last.content, str) else str(last.content)

    try:
        update = _parse_orchestrator_output(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return {"errors": [f"orchestrator: output parse error — {exc}. Raw: {raw[:200]}"]}

    return update
