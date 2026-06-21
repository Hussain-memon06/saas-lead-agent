"""App-owned persistence repositories."""

from saas_lead_agent.persistence.access import (
    artifacts_owner_id,
    can_read_artifacts,
    can_read_snapshot,
    filter_artifacts_for_auth,
    filter_snapshots_for_auth,
    snapshot_owner_id,
)
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
    "artifacts_owner_id",
    "can_read_artifacts",
    "can_read_snapshot",
    "create_lead_run_repository",
    "filter_artifacts_for_auth",
    "filter_snapshots_for_auth",
    "snapshot_owner_id",
]
