"""Composite lead report contract used by dossier/API layers."""

from pydantic import Field

from saas_lead_agent.schemas.base import StrictBaseModel
from saas_lead_agent.schemas.company_profile import CompanyProfile
from saas_lead_agent.schemas.contact import Contact
from saas_lead_agent.schemas.outreach import OutreachDraft, SendResult
from saas_lead_agent.schemas.signals import CompanySignal


class LeadReport(StrictBaseModel):
    company_profile: CompanyProfile | None = None
    contact: Contact | None = None
    signals: list[CompanySignal] = Field(default_factory=list)
    fit_score: int | None = Field(default=None, ge=1, le=10)
    fit_level: str | None = None
    score_breakdown: dict[str, float] | None = None
    score_confidence: str | None = None
    score_explanation: str | None = Field(default=None, max_length=2_000)
    needs_human_review: bool | None = None
    score_reasons: list[str] = Field(default_factory=list)
    score_uncertainty: list[str] = Field(default_factory=list)
    outreach: OutreachDraft | None = None
    send_result: SendResult | None = None
    errors: list[str] = Field(default_factory=list)
