"""Tests for Phase 5 typed tool contracts."""

import pytest
from pydantic import ValidationError

from saas_lead_agent.tools import (
    ToolCallContext,
    ToolExecutionMetadata,
    ToolResult,
    ToolSpec,
    ToolTimeoutPolicy,
    completed_tool_result,
    failed_tool_result,
)


def _search_spec() -> ToolSpec:
    return ToolSpec(
        name="web_search",
        category="search",
        provider="tavily",
        description="Search the web for company information.",
        timeout_policy=ToolTimeoutPolicy(timeout_ms=15_000, max_attempts=2, backoff_ms=500),
    )


def test_completed_tool_result_contains_safe_metadata_and_output() -> None:
    result = completed_tool_result(
        spec=_search_spec(),
        context=ToolCallContext(
            request_id="req-1",
            run_id="run-1",
            thread_id="lead:acme.example.com",
            input_hash="a" * 64,
        ),
        output=[{"title": "Acme", "url": "https://acme.example.com"}],
        duration_ms=42.5,
    )

    assert result.metadata.tool_name == "web_search"
    assert result.metadata.status == "completed"
    assert result.metadata.timeout_ms == 15_000
    assert result.metadata.max_attempts == 2
    assert result.context.request_id == "req-1"
    assert result.output == [{"title": "Acme", "url": "https://acme.example.com"}]
    assert result.error is None


def test_failed_tool_result_requires_sanitized_error() -> None:
    result = failed_tool_result(
        spec=_search_spec(),
        context=ToolCallContext(request_id="req-1"),
        status="rate_limited",
        error_kind="rate_limit",
        error_message="Provider rate limit exceeded",
        retryable=True,
        provider_status_code=429,
    )

    assert result.metadata.status == "rate_limited"
    assert result.error is not None
    assert result.error.kind == "rate_limit"
    assert result.error.retryable is True
    assert result.error.provider_status_code == 429
    assert result.output is None


def test_tool_result_rejects_raw_extra_fields() -> None:
    metadata = ToolExecutionMetadata(
        tool_name="web_search",
        category="search",
        provider="tavily",
        status="completed",
        timeout_ms=15_000,
    )

    with pytest.raises(ValidationError):
        ToolResult(
            metadata=metadata,
            output={"ok": True},
            raw_provider_payload={"api_key": "secret"},
        )


def test_completed_tool_result_must_include_output() -> None:
    metadata = ToolExecutionMetadata(
        tool_name="web_search",
        category="search",
        status="completed",
    )

    with pytest.raises(ValidationError, match="completed tool results"):
        ToolResult(metadata=metadata)


def test_failed_tool_result_cannot_use_completed_status() -> None:
    with pytest.raises(ValueError, match="status='completed'"):
        failed_tool_result(
            spec=_search_spec(),
            status="completed",
            error_kind="unknown",
            error_message="This should use completed_tool_result",
        )


def test_non_completed_tool_result_must_include_error() -> None:
    metadata = ToolExecutionMetadata(
        tool_name="scrape",
        category="scrape",
        status="timeout",
    )

    with pytest.raises(ValidationError, match="non-completed tool results"):
        ToolResult(metadata=metadata)


def test_attempt_cannot_exceed_max_attempts() -> None:
    with pytest.raises(ValidationError, match="attempt cannot exceed"):
        ToolExecutionMetadata(
            tool_name="hunt_contact",
            category="contact_finding",
            status="failed",
            attempt=3,
            max_attempts=2,
        )


def test_external_action_tools_require_human_approval() -> None:
    with pytest.raises(ValidationError, match="external-action tools"):
        ToolSpec(
            name="send_email",
            category="email_delivery",
            provider="sendgrid",
            description="Send an approved outreach email.",
            timeout_policy=ToolTimeoutPolicy(timeout_ms=10_000),
            external_action=True,
            requires_human_approval=False,
        )

    spec = ToolSpec(
        name="send_email",
        category="email_delivery",
        provider="sendgrid",
        description="Send an approved outreach email.",
        timeout_policy=ToolTimeoutPolicy(timeout_ms=10_000),
        external_action=True,
        requires_human_approval=True,
    )
    assert spec.external_action is True
