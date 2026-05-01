"""Dossier writer agent node for the LeadState graph.

Uses GPT-4o-mini via direct model.ainvoke() — no tools, no ReAct loop.
Reads company_profile, contact, and signals from state; returns
fit_score, score_explanation, email_subject, and email_body.

The system prompt embeds the project's default ICP rubric (see
``config/icp_defaults.py``) so the model scores against an explicit
target instead of an implicit one.  ``score_explanation`` carries a
short attribute-by-attribute readout (e.g. "9/10 — B2B SaaS ✅,
Series C ✅, US ✅, hiring SDRs ✅") so the UI can show *why* the
score landed where it did.
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from saas_lead_agent.config.icp_defaults import DEFAULT_ICP, format_icp_for_prompt
from saas_lead_agent.state import LeadState
from saas_lead_agent.utils import _extract_json

_GPT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = f"""You are an expert B2B SaaS sales development representative.

Score every prospect against this Ideal Customer Profile (ICP):
{format_icp_for_prompt(DEFAULT_ICP)}

Given a company research dossier, do three things:
1. Score the company on a scale of 1-10 (fit_score), where 10 = ideal
   ICP match and 1 = poor fit.  Reward target industries / stages /
   geographies and ideal signals; penalise red flags.
2. Produce a one-line score_explanation that lists the attributes that
   moved the score, with a ✅ for matches and a ❌ for misses.
   Format: "{{score}}/10 — {{attr1}} ✅, {{attr2}} ✅, {{attr3}} ❌, ..."
   Example: "9/10 — B2B SaaS ✅, Series C ✅, US ✅, hiring SDRs ✅"
   Keep it under 140 characters and use 3-5 attributes.
3. Write a concise, personalised cold outreach email (3-4 sentences)
   to the primary contact, referencing specific signals from the dossier.

Return a single JSON object — no markdown, no explanation, only the JSON:

{{
  "fit_score":         integer (1-10),
  "score_explanation": string,
  "email_subject":     string,
  "email_body":        string
}}

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
    output.  ``score_explanation`` is passed through as-is (the prompt
    constrains its shape but we don't enforce that here).

    On any failure (JSON parse error, unexpected exception) the node appends a
    descriptive string to ``errors`` and returns without raising, so the graph
    can continue gracefully.

    Args:
        state: Current ``LeadState``; ``company_profile``, ``contact``, and
            ``signals`` should be populated by upstream nodes.

    Returns:
        Partial state update dict — one of:
        - ``{"fit_score": int, "score_explanation": str, "email_subject": str,
             "email_body": str}`` on success.
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
        "score_explanation": str(result.get("score_explanation", "")),
        "email_subject": str(result.get("email_subject", "")),
        "email_body": str(result.get("email_body", "")),
    }
