"""Dossier writer agent node for the LeadState graph.

The LLM drafts outreach copy. Deterministic Python calculates the final fit
score so the score is inspectable, reproducible, and independent of generation
text.
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from saas_lead_agent.engine import GroundingEngine, OutreachQualityEngine, ScoringEngine
from saas_lead_agent.schemas import (
    CompanyProfile,
    CompanySignal,
    Contact,
    DossierOutput,
    IcpContext,
    OutreachDraft,
)
from saas_lead_agent.state import LeadState
from saas_lead_agent.utils import _extract_json

_GPT_MODEL = "gpt-4o-mini"


def _format_icp(icp: dict[str, Any]) -> str:
    """Render the user-supplied ICP as a bullet list for the system prompt."""
    lines: list[str] = []
    seller = (icp.get("seller_name") or "").strip()
    offering = (icp.get("offering") or "").strip()
    vp = (icp.get("value_proposition") or "").strip()
    if seller:
        lines.append(f"- Seller: {seller}")
    if offering:
        lines.append(f"- What they sell: {offering}")
    for key, label in (
        ("target_industries", "Target industries"),
        ("target_stages", "Target stages"),
        ("target_geographies", "Target geographies"),
        ("must_have_signals", "Must-have signals"),
        ("red_flags", "Red flags"),
    ):
        vals = icp.get(key) or []
        if isinstance(vals, list) and vals:
            lines.append(f"- {label}: {', '.join(str(v) for v in vals)}")
    target_employees = (icp.get("target_employees") or "").strip()
    if target_employees and target_employees != "Any":
        lines.append(f"- Target employee count: {target_employees}")
    if vp:
        lines.append(f"- Value proposition (use themes in email): {vp}")
    return "\n".join(lines) if lines else "(no ICP fields populated)"


_ICP_SYSTEM_PROMPT_TEMPLATE = """You are an expert B2B SaaS sales development representative.

The final fit score is calculated deterministically by Python. Do not create,
change, or explain a score. Your only job is to draft outreach copy.

Use this Ideal Customer Profile (ICP) as context:
{icp_block}

Email rules:
1. Reference the seller's value proposition without copying it verbatim.
2. Reference at least one verified buying signal if one exists.
3. Address the contact by their actual name/title when available.
4. Never include placeholder text like [your product], [company name],
   {{name}}, or TODO.

Return a single JSON object - no markdown, no explanation, only the JSON:

{{
  "email_subject": string,
  "email_body": string
}}

Return ONLY the JSON object."""


_GENERIC_SYSTEM_PROMPT = """You are an expert B2B SaaS sales development representative.

The final fit score is calculated deterministically by Python. Do not create,
change, or explain a score. Your only job is to draft outreach copy.

The user has not configured their Ideal Customer Profile yet. Draft a generic
B2B outreach email from the extracted company, signal, and contact facts.

Email rules:
1. Reference at least one verified buying signal if any exist; if none,
   reference the company's stated focus or product.
2. Address the contact by their actual name/title when available.
3. Never include placeholder text like [your product], [company name],
   {name}, or TODO.

Return a single JSON object - no markdown, no explanation, only the JSON:

{
  "email_subject": string,
  "email_body": string
}

Return ONLY the JSON object."""


def _build_system_prompt(icp_context: dict[str, Any] | None) -> str:
    """Pick ICP-aware or generic email drafting mode."""
    if icp_context:
        return _ICP_SYSTEM_PROMPT_TEMPLATE.format(icp_block=_format_icp(icp_context))
    return _GENERIC_SYSTEM_PROMPT


_model: ChatOpenAI | None = None


def _get_model() -> ChatOpenAI:
    """Return the module-level GPT-4o-mini model, initialising it on first call."""
    global _model
    if _model is None:
        _model = ChatOpenAI(model=_GPT_MODEL)
    return _model


def _scoring_inputs(
    state: LeadState,
) -> tuple[CompanyProfile | None, Contact | None, list[CompanySignal], IcpContext | None]:
    """Validate serialized state fragments before deterministic scoring."""
    profile_raw = state.get("company_profile")
    contact_raw = state.get("contact")
    signals_raw = state.get("signals") or []
    icp_raw = state.get("icp_context")

    profile = CompanyProfile.model_validate(profile_raw) if profile_raw else None
    contact = Contact.model_validate(contact_raw) if contact_raw else None
    signals = [CompanySignal.model_validate(signal) for signal in signals_raw]
    icp = IcpContext.model_validate(icp_raw) if icp_raw else None
    return profile, contact, signals, icp


async def dossier_writer(state: LeadState) -> dict[str, Any]:
    """Score fit deterministically and draft outreach email from the dossier.

    The model is allowed to produce only email draft fields. Any model-provided
    score fields are ignored.
    """
    model = _get_model()
    icp_context = state.get("icp_context")

    try:
        profile, contact, signals, icp = _scoring_inputs(state)
        score = ScoringEngine().calculate_score(
            profile=profile,
            contact=contact,
            signals=signals,
            icp=icp,
        )
    except ValidationError as exc:
        return {"errors": [f"dossier_writer: scoring input validation error - {exc}"]}

    context = (
        f"Company profile: {json.dumps(state.get('company_profile'))}\n"
        f"Contact: {json.dumps(state.get('contact'))}\n"
        f"Signals: {json.dumps(state.get('signals'))}\n"
        f"Deterministic score: {score.fit_score}/10\n"
        f"Deterministic score explanation: {score.score_explanation}"
    )

    try:
        response = await model.ainvoke(
            [
                SystemMessage(content=_build_system_prompt(icp_context)),
                HumanMessage(content=context),
            ]
        )
    except Exception as exc:
        return {"errors": [f"dossier_writer: model invocation failed: {exc}"]}

    raw: str = response.content if isinstance(response.content, str) else str(response.content)

    try:
        result = _extract_json(raw)
    except json.JSONDecodeError as exc:
        return {"errors": [f"dossier_writer: JSON parse error - {exc}. Raw: {raw[:200]}"]}
    except ValueError as exc:
        return {"errors": [f"dossier_writer: unexpected response shape - {exc}"]}

    try:
        draft = OutreachDraft.model_validate(
            {
                "email_subject": str(result.get("email_subject", "")),
                "email_body": str(result.get("email_body", "")),
            }
        )
        validated = DossierOutput.model_validate(
            {
                "fit_score": score.fit_score,
                "score_explanation": score.score_explanation,
                "email_subject": draft.email_subject,
                "email_body": draft.email_body,
            }
        )
    except ValidationError as exc:
        return {"errors": [f"dossier_writer: schema validation error - {exc}"]}

    grounding = GroundingEngine().validate(
        profile=profile,
        contact=contact,
        signals=signals,
        draft=draft,
        score=score,
    )
    outreach_quality = OutreachQualityEngine().evaluate(
        profile=profile,
        contact=contact,
        signals=signals,
        draft=draft,
    )

    review_reasons: list[str] = []
    if not grounding.is_sufficient:
        review_reasons.extend(f"grounding: {claim}" for claim in grounding.unsupported_claims[:3])
    if not outreach_quality.passed:
        review_reasons.extend(f"outreach quality: {issue}" for issue in outreach_quality.issues[:3])

    output: dict[str, Any] = {
        **validated.model_dump(),
        "fit_level": score.fit_level,
        "score_breakdown": score.score_breakdown.model_dump(),
        "score_confidence": score.confidence,
        "needs_human_review": score.needs_human_review or bool(review_reasons),
        "score_reasons": score.reasons,
        "score_uncertainty": score.uncertainty_reasons,
        "grounding_report": grounding.model_dump(),
        "outreach_quality": outreach_quality.model_dump(),
    }
    if review_reasons:
        output["errors"] = review_reasons
    return output
