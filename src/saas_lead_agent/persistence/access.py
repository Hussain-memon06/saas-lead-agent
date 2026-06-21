"""Owner-aware persistence helpers before route enforcement.

These functions centralize snapshot ownership decisions but are intentionally
not wired into repository methods or API routes yet.
"""

from saas_lead_agent.persistence.lead_artifacts import LeadArtifacts
from saas_lead_agent.persistence.lead_runs import LeadRunSnapshot
from saas_lead_agent.schemas.auth import AccessDecision, AuthContext, can_access_resource


def snapshot_owner_id(snapshot: LeadRunSnapshot) -> str | None:
    """Return the normalized owner ID stored in a run snapshot result."""

    value = snapshot.result.get("user_id")
    if not isinstance(value, str):
        return None
    clean = value.strip()
    return clean or None


def can_read_snapshot(auth: AuthContext, snapshot: LeadRunSnapshot) -> AccessDecision:
    """Return the planned read decision for one run snapshot."""

    return can_access_resource(
        auth=auth,
        resource_type="lead_run",
        resource_owner_id=snapshot_owner_id(snapshot),
        action="read",
    )


def filter_snapshots_for_auth(
    auth: AuthContext,
    snapshots: list[LeadRunSnapshot],
) -> list[LeadRunSnapshot]:
    """Return only snapshots visible under the planned ownership policy."""

    return [snapshot for snapshot in snapshots if can_read_snapshot(auth, snapshot).allowed]


def artifacts_owner_id(artifacts: LeadArtifacts) -> str | None:
    """Return the normalized owner ID for a lead artifact aggregate."""

    value = artifacts.lead.user_id
    if value is None:
        return None
    clean = value.strip()
    return clean or None


def can_read_artifacts(auth: AuthContext, artifacts: LeadArtifacts) -> AccessDecision:
    """Return the planned read decision for normalized lead artifacts."""

    return can_access_resource(
        auth=auth,
        resource_type="lead_run",
        resource_owner_id=artifacts_owner_id(artifacts),
        action="read",
    )


def filter_artifacts_for_auth(
    auth: AuthContext,
    artifacts: list[LeadArtifacts],
) -> list[LeadArtifacts]:
    """Return only artifact aggregates visible under the ownership policy."""

    return [item for item in artifacts if can_read_artifacts(auth, item).allowed]
