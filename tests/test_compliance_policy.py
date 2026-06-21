"""Tests for Phase 6 compliance configuration contracts."""

import pytest
from pydantic import ValidationError

from saas_lead_agent.schemas.compliance import (
    COMPLIANCE_CONFIGURATION_PLAN,
    CorsPolicy,
    CriticalSecretPolicy,
)


def test_compliance_plan_keeps_wildcard_cors_out_of_production() -> None:
    policies = {policy.environment: policy for policy in COMPLIANCE_CONFIGURATION_PLAN.cors}

    assert policies["development"].allow_wildcard is True
    assert policies["production"].allow_wildcard is False
    assert "*" not in policies["production"].allowed_origins
    assert "https://agent.hussainflow.com" in policies["production"].allowed_origins


def test_production_cors_rejects_wildcard() -> None:
    with pytest.raises(ValidationError, match="production CORS"):
        CorsPolicy(
            environment="production",
            allowed_origins=["*"],
            allow_wildcard=True,
        )


def test_production_secret_policy_requires_openai_key() -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        CriticalSecretPolicy(environment="production", required_env_vars=[])


def test_compliance_plan_documents_redaction_and_audit_events() -> None:
    redaction = COMPLIANCE_CONFIGURATION_PLAN.redaction
    audit_events = {event.event_name: event for event in COMPLIANCE_CONFIGURATION_PLAN.audit_events}

    assert redaction.redact_contact_email is True
    assert redaction.redact_outreach_body is True
    assert "email_body" in redaction.blocked_field_names
    assert audit_events["lead_approved"].category == "approval"
    assert audit_events["email_delivery_attempted"].category == "email_delivery"


def test_request_limit_plan_has_explicit_bounds() -> None:
    limits = COMPLIANCE_CONFIGURATION_PLAN.request_limits

    assert limits.max_body_bytes == 128_000
    assert limits.max_icp_json_bytes == 32_000
    assert limits.max_url_chars == 2_048
