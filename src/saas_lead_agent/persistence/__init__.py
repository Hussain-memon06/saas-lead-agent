"""App-owned persistence repositories."""

from saas_lead_agent.persistence.lead_artifacts import (
    CompanySignalRecord,
    ContactRecord,
    DecisionRecord,
    DeliveryEventRecord,
    LeadArtifacts,
    LeadRecord,
    OutreachDraftRecord,
    ScoreBreakdownRecord,
    SourceRecord,
    UserRecord,
    build_lead_artifacts,
)
from saas_lead_agent.persistence.lead_runs import (
    InMemoryLeadRunRepository,
    LeadRunRepository,
    LeadRunSnapshot,
    PostgresLeadRunRepository,
    RunEvent,
    RunStatus,
    create_lead_run_repository,
)

__all__ = [
    "CompanySignalRecord",
    "ContactRecord",
    "DecisionRecord",
    "DeliveryEventRecord",
    "InMemoryLeadRunRepository",
    "LeadArtifacts",
    "LeadRecord",
    "LeadRunRepository",
    "LeadRunSnapshot",
    "OutreachDraftRecord",
    "PostgresLeadRunRepository",
    "RunEvent",
    "RunStatus",
    "ScoreBreakdownRecord",
    "SourceRecord",
    "UserRecord",
    "build_lead_artifacts",
    "create_lead_run_repository",
]
