"""Tests for Phase 6 SSRF hardening policy contracts."""

import pytest
from pydantic import ValidationError

from saas_lead_agent.schemas.ssrf import SSRF_FETCH_POLICY, SsrfFetchPolicy


def test_ssrf_policy_documents_required_deeper_checks() -> None:
    check_names = {check.name for check in SSRF_FETCH_POLICY.checks}

    assert {"redirect", "dns_rebinding", "post_resolution"}.issubset(check_names)
    assert SSRF_FETCH_POLICY.revalidate_each_redirect is True
    assert SSRF_FETCH_POLICY.require_post_resolution_check is True


def test_ssrf_policy_covers_known_blocked_targets() -> None:
    assert "localhost" in SSRF_FETCH_POLICY.blocked_hostnames
    assert "127.0.0.0/8" in SSRF_FETCH_POLICY.blocked_ip_ranges
    assert "169.254.0.0/16" in SSRF_FETCH_POLICY.blocked_ip_ranges
    assert 5432 in SSRF_FETCH_POLICY.dangerous_ports


def test_ssrf_policy_requires_redirect_dns_and_resolution_checks() -> None:
    with pytest.raises(ValidationError, match="redirect, DNS rebinding"):
        SsrfFetchPolicy(checks=())


def test_ssrf_policy_rejects_missing_http_or_https_scheme() -> None:
    with pytest.raises(ValidationError, match="HTTP/HTTPS"):
        SsrfFetchPolicy(
            allowed_schemes=["https"],
            checks=SSRF_FETCH_POLICY.checks,
        )
