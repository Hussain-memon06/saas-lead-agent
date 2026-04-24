"""Dossier writer agent node for the LeadState graph.

Uses GPT-4o-mini via direct model.ainvoke() — no tools, no ReAct loop.
Reads company_profile, contact, and signals from state; returns fit_score,
email_subject, and email_body.
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from saas_lead_agent.state import LeadState
from saas_lead_agent.utils import _extract_json

_GPT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are an expert B2B SaaS sales development representative.

Given a company research dossier, do two things:
1. Score the company as a sales prospect on a scale of 1-10 (fit_score),
   where 10 = ideal customer profile match and 1 = poor fit.
2. Write a concise, personalised cold outreach email (3-4 sentences) to the
   primary contact, referencing specific signals from the dossier.

Return a single JSON object — no markdown, no explanation, only the JSON:

{
  "fit_score":     integer (1-10),
  "fit_rationale": string,
  "email_subject": string,
  "email_body":    string
}

Return ONLY the JSON object."""

_model: ChatOpenAI | None = None


def _get_model() -> ChatOpenAI:
    """Return the module-level GPT-4o-mini model, initialising it on first call."""
    global _model
    if _model is None:
        _model = ChatOpenAI(model=_GPT_MODEL)
    return _model


def _clamp(value: Any) -> int:
    """Cast value to int and clamp to [1, 10]."""
    return max(1, min(10, int(value)))


async def dossier_writer(state: LeadState) -> dict[str, Any]:
    """LangGraph node: score fit and write outreach email from the research dossier.

    Calls GPT-4o-mini directly (no ReAct loop — no tools needed). Reads
    ``company_profile``, ``contact``, and ``signals`` from state; any or all
    may be ``None`` if upstream nodes failed. Serialises them to JSON strings
    in the prompt so the model always receives a well-formed request.

    ``fit_score`` is clamped to [1, 10] to guard against out-of-range model
    output.

    On any failure (JSON parse error, unexpected exception) the node appends a
    descriptive string to ``errors`` and returns without raising, so the graph
    can continue gracefully.

    Args:
        state: Current ``LeadState``; ``company_profile``, ``contact``, and
            ``signals`` should be populated by upstream nodes.

    Returns:
        Partial state update dict — one of:
        - ``{"fit_score": int, "email_subject": str, "email_body": str}`` on success.
        - ``{"errors": [str]}`` on failure.
    """
    model = _get_model()

    context = (
        f"Company profile: {json.dumps(state.get('company_profile'))}\n"
        f"Contact: {json.dumps(state.get('contact'))}\n"
        f"Signals: {json.dumps(state.get('signals'))}"
    )

    try:
        response = await model.ainvoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=context)]
        )
    except Exception as exc:
        return {"errors": [f"dossier_writer: model invocation failed: {exc}"]}

    raw: str = response.content if isinstance(response.content, str) else str(response.content)

    try:
        result = _extract_json(raw)
    except json.JSONDecodeError as exc:
        return {"errors": [f"dossier_writer: JSON parse error — {exc}. Raw: {raw[:200]}"]}
    except ValueError as exc:
        return {"errors": [f"dossier_writer: unexpected response shape — {exc}"]}

    try:
        fit_score = _clamp(result["fit_score"])
    except (KeyError, TypeError, ValueError) as exc:
        return {"errors": [f"dossier_writer: invalid fit_score — {exc}"]}

    return {
        "fit_score": fit_score,
        "email_subject": str(result.get("email_subject", "")),
        "email_body": str(result.get("email_body", "")),
    }
