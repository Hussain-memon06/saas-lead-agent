"""Tests for owner-aware persistence helpers before route enforcement."""

from saas_lead_agent.persistence import (
    LeadRunSnapshot,
    artifacts_owner_id,
    build_lead_artifacts,
    can_read_artifacts,
    can_read_snapshot,
    filter_artifacts_for_auth,
    filter_snapshots_for_auth,
    snapshot_owner_id,
)
from saas_lead_agent.schemas.auth import AuthContext


def _snapshot(thread_id: str, user_id: str | None) -> LeadRunSnapshot:
    result: dict[str, object] = {}
    if user_id is not None:
        result["user_id"] = user_id
    return LeadRunSnapshot(
        run_id=f"run:{thread_id}",
        thread_id=thread_id,
        domain="acme.example.com",
        company_url="https://acme.example.com",
        status="completed",
        result=result,
    )


def test_snapshot_owner_id_reads_normalized_result_owner() -> None:
    assert snapshot_owner_id(_snapshot("lead:owned", " user-1 ")) == "user-1"
    assert snapshot_owner_id(_snapshot("lead:legacy", None)) is None


def test_authenticated_user_can_read_only_owned_snapshot() -> None:
    auth = AuthContext(mode="authenticated", user_id="user-1", roles=["user"])

    assert can_read_snapshot(auth, _snapshot("lead:owned", "user-1")).allowed is True
    assert can_read_snapshot(auth, _snapshot("lead:other", "user-2")).allowed is False


def test_anonymous_demo_can_read_only_legacy_unowned_snapshot() -> None:
    auth = AuthContext()

    assert can_read_snapshot(auth, _snapshot("lead:legacy", None)).allowed is True
    assert can_read_snapshot(auth, _snapshot("lead:owned", "user-1")).allowed is False


def test_filter_snapshots_for_auth_keeps_only_visible_records() -> None:
    auth = AuthContext(mode="authenticated", user_id="user-1", roles=["user"])
    snapshots = [
        _snapshot("lead:mine", "user-1"),
        _snapshot("lead:other", "user-2"),
        _snapshot("lead:legacy", None),
    ]

    visible = filter_snapshots_for_auth(auth, snapshots)

    assert [snapshot.thread_id for snapshot in visible] == ["lead:mine"]


def test_artifact_aggregate_access_uses_normalized_lead_owner() -> None:
    mine = build_lead_artifacts(_snapshot("lead:mine", "user-1"))
    other = build_lead_artifacts(_snapshot("lead:other", "user-2"))
    auth = AuthContext(mode="authenticated", user_id="user-1", roles=["user"])

    assert artifacts_owner_id(mine) == "user-1"
    assert can_read_artifacts(auth, mine).allowed is True
    assert can_read_artifacts(auth, other).allowed is False
    assert [item.lead.thread_id for item in filter_artifacts_for_auth(auth, [mine, other])] == [
        "lead:mine"
    ]
