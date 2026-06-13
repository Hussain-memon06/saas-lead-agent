"""Pydantic v2 request/response models for the lead-research API."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from saas_lead_agent.schemas import IcpContext, SendResult, normalize_public_http_url


class QualifyRequest(BaseModel):
    url: str
    # User-supplied ICP from the frontend Settings page.  Free-form dict
    # (snake_case fields matching `frontend/lib/icp.ts`) so the dossier
    # prompt can read it directly without a backend-side schema rewrite
    # every time the frontend adds a field.  ``None`` means the user has
    # not configured an ICP — dossier_writer falls back to generic mode.
    icp_context: dict[str, Any] | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return normalize_public_http_url(v)

    @field_validator("icp_context")
    @classmethod
    def validate_icp_context(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return None
        return IcpContext.model_validate(v).model_dump(exclude_unset=True)


class QualifyResponse(BaseModel):
    request_id: str | None = None
    run_id: str | None = None
    thread_id: str
    company_profile: dict[str, Any] | None = None
    contact: dict[str, Any] | None = None
    signals: list[dict[str, Any]] | None = None
    fit_score: int | None = None
    fit_level: str | None = None
    score_breakdown: dict[str, Any] | None = None
    score_confidence: str | None = None
    score_explanation: str | None = None
    needs_human_review: bool | None = None
    score_reasons: list[str] | None = None
    score_uncertainty: list[str] | None = None
    grounding_report: dict[str, Any] | None = None
    outreach_quality: dict[str, Any] | None = None
    processing_metadata: dict[str, Any] | None = None
    email_subject: str | None = None
    email_body: str | None = None
    email_approved: bool | None = None
    send_result: SendResult | None = None
    message_id: str | None = None
    sent_at: str | None = None
    interrupted: bool = False
    errors: list[str] = Field(default_factory=list)


class ApproveResponse(BaseModel):
    request_id: str | None = None
    run_id: str | None = None
    thread_id: str
    email_approved: bool | None = None
    send_result: SendResult | None = None
    message_id: str | None = None
    sent_at: str | None = None
    processing_metadata: dict[str, Any] | None = None
    interrupted: bool = False
    errors: list[str] = Field(default_factory=list)


class LeadSummary(BaseModel):
    request_id: str | None = None
    run_id: str
    thread_id: str
    domain: str
    company_url: str
    company_name: str | None = None
    status: str
    fit_score: int | None = None
    fit_level: str | None = None
    score_confidence: str | None = None
    needs_human_review: bool | None = None
    interrupted: bool = False
    send_result: SendResult | None = None
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    created_at: str
    updated_at: str


class LeadListResponse(BaseModel):
    request_id: str | None = None
    leads: list[LeadSummary] = Field(default_factory=list)


class RunEventResponse(BaseModel):
    run_id: str
    thread_id: str
    event_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    created_at: str


class RunEventsResponse(BaseModel):
    request_id: str | None = None
    thread_id: str
    events: list[RunEventResponse] = Field(default_factory=list)
