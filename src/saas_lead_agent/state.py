import operator
from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class LeadState(TypedDict):
    run_id: str | None
    company_url: str
    domain: str
    # User-supplied Ideal Customer Profile from the frontend Settings page.
    # Read by dossier_writer to score against the user's actual targets.
    # ``None`` = no ICP configured → dossier_writer falls back to generic mode.
    icp_context: dict[str, Any] | None
    messages: Annotated[list[AnyMessage], add_messages]
    company_profile: dict[str, Any] | None
    contact: dict[str, Any] | None
    signals: list[dict[str, Any]] | None
    fit_score: int | None
    fit_level: str | None
    score_breakdown: dict[str, Any] | None
    score_confidence: str | None
    score_explanation: str | None
    needs_human_review: bool | None
    score_reasons: list[str] | None
    score_uncertainty: list[str] | None
    grounding_report: dict[str, Any] | None
    outreach_quality: dict[str, Any] | None
    retrieval_context: dict[str, Any] | None
    retrieval_events: Annotated[list[dict[str, Any]], operator.add]
    provider_usage: Annotated[list[dict[str, Any]], operator.add]
    processing_metadata: dict[str, Any] | None
    email_subject: str | None
    email_body: str | None
    email_approved: bool | None
    send_result: str | None
    message_id: str | None
    sent_at: str | None
    errors: Annotated[list[str], operator.add]
