"""Validated domain schemas for Outbound Lead Agent.

These models establish the production contract layer while the existing
LangGraph state remains dict-based during Phase 1 migration.
"""

from saas_lead_agent.schemas.api_envelope import APIError, APIResponse
from saas_lead_agent.schemas.company_profile import CompanyProfile, FundingStage
from saas_lead_agent.schemas.contact import Contact
from saas_lead_agent.schemas.evidence import Evidence, EvidenceCollection
from saas_lead_agent.schemas.icp import IcpContext
from saas_lead_agent.schemas.lead_report import LeadReport
from saas_lead_agent.schemas.metadata import ProcessingMetadata
from saas_lead_agent.schemas.outreach import DossierOutput, OutreachDraft, SendResult
from saas_lead_agent.schemas.signals import CompanySignal, SignalType
from saas_lead_agent.schemas.url import normalize_public_http_url

__all__ = [
    "CompanyProfile",
    "CompanySignal",
    "Contact",
    "DossierOutput",
    "APIError",
    "APIResponse",
    "Evidence",
    "EvidenceCollection",
    "FundingStage",
    "IcpContext",
    "LeadReport",
    "OutreachDraft",
    "ProcessingMetadata",
    "SendResult",
    "SignalType",
    "normalize_public_http_url",
]
