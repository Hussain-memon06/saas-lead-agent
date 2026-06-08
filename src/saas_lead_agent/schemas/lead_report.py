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
    score_explanation: str | None = Field(default=None, max_length=2_000)
    outreach: OutreachDraft | None = None
    send_result: SendResult | None = None
    errors: list[str] = Field(default_factory=list)
