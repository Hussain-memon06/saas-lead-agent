"""Validated domain schemas for Outbound Lead Agent.

These models establish the production contract layer while the existing
LangGraph state remains dict-based during Phase 1 migration.
"""

from saas_lead_agent.schemas.api_envelope import APIError, APIResponse
from saas_lead_agent.schemas.auth import (
    AccessDecision,
    AuthContext,
    ProtectedRoutePolicy,
    ResourceOwnershipPolicy,
    can_access_resource,
    get_resource_policy,
    get_route_policy,
)
from saas_lead_agent.schemas.company_profile import CompanyProfile, FundingStage
from saas_lead_agent.schemas.compliance import (
    COMPLIANCE_CONFIGURATION_PLAN,
    AuditEventPolicy,
    ComplianceConfigurationPlan,
    CorsPolicy,
    CriticalSecretPolicy,
    RedactionPolicy,
    RequestLimitPolicy,
)
from saas_lead_agent.schemas.contact import Contact
from saas_lead_agent.schemas.evidence import Evidence, EvidenceCollection
from saas_lead_agent.schemas.icp import IcpContext
from saas_lead_agent.schemas.lead_report import LeadReport
from saas_lead_agent.schemas.metadata import ProcessingMetadata
from saas_lead_agent.schemas.outreach import DossierOutput, OutreachDraft, SendResult
from saas_lead_agent.schemas.retrieval import (
    ContextBundle,
    DocumentStatus,
    DocumentType,
    EmbeddingRecord,
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievalEvent,
    RetrievedChunk,
    TrustLabel,
)
from saas_lead_agent.schemas.signals import CompanySignal, SignalType
from saas_lead_agent.schemas.ssrf import SSRF_FETCH_POLICY, SsrfCheckPolicy, SsrfFetchPolicy
from saas_lead_agent.schemas.url import (
    normalize_public_http_url,
    resolve_public_http_target,
    validate_public_http_target,
)

__all__ = [
    "CompanyProfile",
    "CompanySignal",
    "Contact",
    "DossierOutput",
    "APIError",
    "APIResponse",
    "AccessDecision",
    "AuditEventPolicy",
    "AuthContext",
    "COMPLIANCE_CONFIGURATION_PLAN",
    "ComplianceConfigurationPlan",
    "Evidence",
    "EvidenceCollection",
    "CorsPolicy",
    "CriticalSecretPolicy",
    "FundingStage",
    "IcpContext",
    "LeadReport",
    "ContextBundle",
    "DocumentStatus",
    "DocumentType",
    "EmbeddingRecord",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "OutreachDraft",
    "ProcessingMetadata",
    "ProtectedRoutePolicy",
    "RedactionPolicy",
    "ResourceOwnershipPolicy",
    "RequestLimitPolicy",
    "RetrievalEvent",
    "RetrievedChunk",
    "SendResult",
    "SignalType",
    "SSRF_FETCH_POLICY",
    "SsrfCheckPolicy",
    "SsrfFetchPolicy",
    "TrustLabel",
    "can_access_resource",
    "get_resource_policy",
    "get_route_policy",
    "normalize_public_http_url",
    "resolve_public_http_target",
    "validate_public_http_target",
]
