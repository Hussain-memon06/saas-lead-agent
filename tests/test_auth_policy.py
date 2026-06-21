"""Tests for Phase 6 auth context and route-policy contracts."""

import pytest
from pydantic import ValidationError

from saas_lead_agent.schemas.auth import (
    RESOURCE_OWNERSHIP_POLICIES,
    ROUTE_POLICIES,
    AuthContext,
    ProtectedRoutePolicy,
    can_access_resource,
    get_resource_policy,
    get_route_policy,
)


def test_anonymous_demo_context_is_default_runtime_mode() -> None:
    context = AuthContext()

    assert context.mode == "anonymous_demo"
    assert context.user_id is None
    assert context.roles == ["anonymous"]
    assert context.is_authenticated is False


def test_authenticated_context_requires_user_id_and_non_anonymous_role() -> None:
    context = AuthContext(mode="authenticated", user_id="user-1", roles=["user"])

    assert context.is_authenticated is True
    assert context.user_id == "user-1"

    with pytest.raises(ValidationError, match="requires user_id"):
        AuthContext(mode="authenticated", roles=["user"])

    with pytest.raises(ValidationError, match="cannot include anonymous"):
        AuthContext(mode="authenticated", user_id="user-1", roles=["anonymous"])


def test_route_policy_matrix_matches_current_api_surface() -> None:
    policies = {policy.route_name: policy for policy in ROUTE_POLICIES}

    assert set(policies) == {
        "qualify",
        "list_leads",
        "get_lead",
        "get_lead_events",
        "approve_lead",
        "reject_lead",
    }
    assert policies["qualify"].path_template == "/api/qualify"
    assert policies["approve_lead"].sensitivity == "external_action"
    assert policies["approve_lead"].requires_human_approval is True
    assert all(policy.allow_anonymous_demo for policy in policies.values())
    assert all(policy.requires_auth is False for policy in policies.values())


def test_get_route_policy_returns_policy_by_name() -> None:
    assert get_route_policy("get_lead_events") is not None
    assert get_route_policy("missing") is None


def test_external_action_policy_requires_human_approval() -> None:
    with pytest.raises(ValidationError, match="external-action routes"):
        ProtectedRoutePolicy(
            route_name="dangerous_action",
            path_template="/api/dangerous",
            methods=["post"],
            sensitivity="external_action",
            requires_auth=False,
            allow_anonymous_demo=True,
            requires_human_approval=False,
        )


def test_resource_ownership_policy_matrix_covers_phase_6_entities() -> None:
    policies = {policy.resource_type: policy for policy in RESOURCE_OWNERSHIP_POLICIES}

    assert set(policies) == {
        "lead_run",
        "source",
        "contact",
        "company_signal",
        "score_breakdown",
        "outreach_draft",
        "decision",
        "delivery_event",
        "retrieval_context",
    }
    assert policies["lead_run"].owner_field == "user_id"
    assert "thread_id" in policies["lead_run"].identifier_fields
    assert "approve" in policies["lead_run"].allowed_actions
    assert get_resource_policy("contact") == policies["contact"]


def test_access_decision_allows_legacy_unowned_anonymous_demo_resource() -> None:
    decision = can_access_resource(
        auth=AuthContext(),
        resource_type="lead_run",
        resource_owner_id=None,
        action="read",
    )

    assert decision.allowed is True
    assert decision.reason == "legacy anonymous demo resource"


def test_access_decision_requires_owner_match_for_authenticated_user() -> None:
    auth = AuthContext(mode="authenticated", user_id="user-1", roles=["user"])

    allowed = can_access_resource(
        auth=auth,
        resource_type="lead_run",
        resource_owner_id="user-1",
        action="read",
    )
    denied = can_access_resource(
        auth=auth,
        resource_type="lead_run",
        resource_owner_id="user-2",
        action="read",
    )

    assert allowed.allowed is True
    assert allowed.reason == "resource owner match"
    assert denied.allowed is False
    assert denied.reason == "resource owner mismatch"


def test_access_decision_denies_unsupported_action() -> None:
    decision = can_access_resource(
        auth=AuthContext(mode="authenticated", user_id="user-1", roles=["user"]),
        resource_type="source",
        resource_owner_id="user-1",
        action="approve",
    )

    assert decision.allowed is False
    assert decision.reason == "action is not allowed for resource type"
