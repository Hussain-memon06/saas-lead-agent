"""Tests for operational log redaction boundaries."""

import logging

from saas_lead_agent.api.logging_redaction import (
    SecretRedactionFilter,
    redact_sensitive_urls,
)


def test_redact_sensitive_query_params_preserves_safe_params() -> None:
    redacted = redact_sensitive_urls(
        "https://api.hunter.io/v2/domain-search?domain=stripe.com&api_key=secret&limit=10"
    )

    assert "secret" not in redacted
    assert "api_key=REDACTED" in redacted
    assert "domain=stripe.com" in redacted
    assert "limit=10" in redacted


def test_httpx_log_record_args_are_redacted_before_formatting() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='HTTP Request: %s %s "%s %d %s"',
        args=(
            "GET",
            "https://api.hunter.io/v2/domain-search?domain=stripe.com&api_key=secret",
            "HTTP/1.1",
            200,
            "OK",
        ),
        exc_info=None,
    )

    SecretRedactionFilter().filter(record)

    message = record.getMessage()
    assert "secret" not in message
    assert "api_key=REDACTED" in message
    assert "domain=stripe.com" in message
