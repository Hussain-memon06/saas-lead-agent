"""Dossier writer agent node for the LeadState graph.

Uses GPT-4o-mini via direct model.ainvoke() — no tools, no ReAct loop.
Reads ``company_profile``, ``contact``, ``signals``, and ``icp_context``
from state; returns ``fit_score``, ``score_explanation``,
``email_subject``, and ``email_body``.

Two scoring modes:

- **ICP provided**: score strictly against the user's rubric — start at
  5/10, +1 per industry/stage/geography match, +1 per must-have signal
  found in evidence, -2 per red flag.  ``score_explanation`` follows a
  fixed pipe-separated format the dossier UI can pretty-print.  The
  email body must reference the user's value proposition, at least one
  verified signal, and the contact's actual name/title.
- **No ICP**: generic B2B-fit prompt.  ``score_explanation`` lists what
  data was found vs missing and nudges the user toward Settings.
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from saas_lead_agent.schemas import DossierOutput
from saas_lead_agent.state import LeadState
from saas_lead_agent.utils import _extract_json

_GPT_MODEL = "gpt-4o-mini"


def _format_icp(icp: dict[str, Any]) -> str:
    """Render the user-supplied ICP as a bullet list for the system prompt.

    Empty fields are dropped so the model isn't distracted by empty
    arrays.  The keys here mirror ``frontend/lib/icp.ts`` so the JSON
    we receive over the wire goes straight into the prompt.
    """
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
        lines.append(f"- Value proposition (use verbatim themes in email): {vp}")
    return "\n".join(lines) if lines else "(no ICP fields populated)"


_ICP_SYSTEM_PROMPT_TEMPLATE = """You are an expert B2B SaaS sales development representative.

Score the company STRICTLY against this Ideal Customer Profile (ICP):
{icp_block}

Scoring rules:
- Start at 5/10 (neutral baseline).
- +1 for each must-have signal present (with evidence in the dossier).
- +1 for industry match.
- +1 for stage match.
- +1 for geography match.
- -2 for each red flag present.
- Maximum 10, minimum 1.
- NEVER give 10/10 unless ALL criteria match with strong evidence.

The score_explanation MUST follow this exact format (pipe-separated, all on one line):
"{{N}}/10 — Industry: X ✅ | Stage: X ✅ | Geography: X ✅ | Signals: a ✅, b ❌ not found | Red flags: none ✅"

Use ✅ when an attribute matches the ICP and ❌ when it doesn't (or
"not found" when the dossier lacks evidence).  Keep it under 220
characters.

Email rules — the email_body MUST:
1. Reference the seller's value proposition (the dossier's "Value
   proposition" line above), grounded in real wording — never paste
   it verbatim, but the angle must come through.
2. Reference at least one verified buying signal from the dossier by
   name and detail.
3. Address the contact by their actual name and title from the dossier.
4. Never include placeholder text like [your product], [company name],
   {{name}}, or TODO — the email must be ready to send.

Return a single JSON object — no markdown, no explanation, only the JSON:

{{
  "fit_score":         integer (1-10),
  "score_explanation": string (in the exact format above),
  "email_subject":     string,
  "email_body":        string
}}

Return ONLY the JSON object."""


_GENERIC_SYSTEM_PROMPT = """You are an expert B2B SaaS sales development representative.

The user has not configured their Ideal Customer Profile yet.  Score the
company on general B2B sales viability:

- Is this a real, established company (not a personal blog or shell)?
- Does it have any recent buying signals (funding, hiring, product)?
- Was a decision-maker contact found?

Scoring guidance:
- 8-10: established company, multiple recent signals, contact found.
- 5-7: established company, partial signals or contact missing.
- 1-4: thin profile, no signals, or no contact.

The score_explanation MUST follow this format:
"{N}/10 — Company: {found/missing} | Signals: {count} | Contact: {found/missing} | Set your ICP in Settings for a personalised score."

Use the words "found" / "missing" verbatim and end the line with the
"Set your ICP in Settings" call to action so the UI can detect it.
Keep it under 220 characters.

Email rules — the email_body MUST:
1. Reference at least one verified buying signal if any exist; if none,
   reference the company's stated focus or product.
2. Address the contact by their actual name and title if available;
   otherwise open with a neutral salutation tied to the company.
3. Never include placeholder text like [your product], [company name],
   {name}, or TODO — the email must be ready to send.

Return a single JSON object — no markdown, no explanation, only the JSON:

{
  "fit_score":         integer (1-10),
  "score_explanation": string (in the exact format above),
  "email_subject":     string,
  "email_body":        string
}

Return ONLY the JSON object."""


def _build_system_prompt(icp_context: dict[str, Any] | None) -> str:
    """Pick MODE A (ICP-aware) or MODE B (generic) and render the prompt."""
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


def _clamp(value: Any) -> int:
    """Cast value to int and clamp to [1, 10]."""
    return max(1, min(10, int(value)))


async def dossier_writer(state: LeadState) -> dict[str, Any]:
    """LangGraph node: score fit and write outreach email from the research dossier.

    Calls GPT-4o-mini directly (no ReAct loop — no tools needed). Reads
    ``company_profile``, ``contact``, ``signals``, and ``icp_context``
    from state; any may be ``None``. Serialises the dossier to JSON in
    the prompt so the model always receives a well-formed request.

    The system prompt branches on whether ``icp_context`` is provided
    (see module docstring).  ``fit_score`` is clamped to [1, 10] to
    guard against out-of-range model output.

    On any failure (JSON parse error, unexpected exception) the node
    appends a descriptive string to ``errors`` and returns without
    raising, so the graph can continue gracefully.

    Returns:
        Partial state update dict — one of:
        - ``{"fit_score", "score_explanation", "email_subject",
             "email_body"}`` on success.
        - ``{"errors": [str]}`` on failure.
    """
    model = _get_model()
    icp_context = state.get("icp_context")

    context = (
        f"Company profile: {json.dumps(state.get('company_profile'))}\n"
        f"Contact: {json.dumps(state.get('contact'))}\n"
        f"Signals: {json.dumps(state.get('signals'))}"
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
        return {"errors": [f"dossier_writer: JSON parse error — {exc}. Raw: {raw[:200]}"]}
    except ValueError as exc:
        return {"errors": [f"dossier_writer: unexpected response shape — {exc}"]}

    try:
        fit_score = _clamp(result["fit_score"])
    except (KeyError, TypeError, ValueError) as exc:
        return {"errors": [f"dossier_writer: invalid fit_score — {exc}"]}

    try:
        validated = DossierOutput.model_validate(
            {
                "fit_score": fit_score,
                "score_explanation": str(result.get("score_explanation", "")),
                "email_subject": str(result.get("email_subject", "")),
                "email_body": str(result.get("email_body", "")),
            }
        )
    except ValidationError as exc:
        return {"errors": [f"dossier_writer: schema validation error — {exc}"]}

    return validated.model_dump()
