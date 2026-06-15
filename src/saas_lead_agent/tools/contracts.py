"""Typed tool contracts for Phase 5 tool abstraction work."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from saas_lead_agent.schemas.base import StrictBaseModel

ToolCategory = Literal[
    "search",
    "scrape",
    "contact_finding",
    "email_drafting",
    "email_delivery",
    "crm_export",
    "internal",
]
ToolStatus = Literal["completed", "failed", "skipped", "timeout", "rate_limited"]
ToolErrorKind = Literal[
    "configuration",
    "validation",
    "network",
    "http_status",
    "provider",
    "timeout",
    "rate_limit",
    "idempotency_conflict",
    "unknown",
]


class ToolTimeoutPolicy(StrictBaseModel):
    """Timeout and retry budget for one logical tool boundary."""

    timeout_ms: int = Field(ge=1)
    max_attempts: int = Field(default=1, ge=1, le=5)
    backoff_ms: int = Field(default=0, ge=0)
    circuit_breaker_failures: int | None = Field(default=None, ge=1)


class ToolSpec(StrictBaseModel):
    """Stable description of a tool before runtime execution."""

    name: str = Field(min_length=1, max_length=100)
    category: ToolCategory
    provider: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    timeout_policy: ToolTimeoutPolicy
    supports_idempotency: bool = False
    external_action: bool = False
    requires_human_approval: bool = False

    @model_validator(mode="after")
    def validate_external_action_approval(self) -> "ToolSpec":
        if self.external_action and not self.requires_human_approval:
            raise ValueError("external-action tools must require human approval")
        return self


class ToolCallContext(StrictBaseModel):
    """Correlation and idempotency context attached to a tool call."""

    request_id: str | None = Field(default=None, max_length=200)
    run_id: str | None = Field(default=None, max_length=200)
    thread_id: str | None = Field(default=None, max_length=500)
    user_id: str | None = Field(default=None, max_length=200)
    tool_call_id: str | None = Field(default=None, max_length=200)
    idempotency_key: str | None = Field(default=None, max_length=300)
    input_hash: str | None = Field(default=None, min_length=16, max_length=128)


class ToolError(StrictBaseModel):
    """Sanitized provider/tool failure details."""

    kind: ToolErrorKind
    message: str = Field(min_length=1, max_length=500)
    retryable: bool = False
    provider_status_code: int | None = Field(default=None, ge=100, le=599)
    provider_error_code: str | None = Field(default=None, max_length=100)


class ToolExecutionMetadata(StrictBaseModel):
    """Runtime metadata safe to persist in run events."""

    tool_name: str = Field(min_length=1, max_length=100)
    category: ToolCategory
    provider: str | None = Field(default=None, max_length=100)
    status: ToolStatus
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: float = Field(default=0.0, ge=0)
    attempt: int = Field(default=1, ge=1, le=5)
    max_attempts: int = Field(default=1, ge=1, le=5)
    timeout_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_attempt_budget(self) -> "ToolExecutionMetadata":
        if self.attempt > self.max_attempts:
            raise ValueError("attempt cannot exceed max_attempts")
        return self


class ToolResult(StrictBaseModel):
    """Common envelope for tool outputs and failures."""

    metadata: ToolExecutionMetadata
    context: ToolCallContext = Field(default_factory=ToolCallContext)
    output: dict[str, Any] | list[dict[str, Any]] | str | None = None
    error: ToolError | None = None
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_result_shape(self) -> "ToolResult":
        if self.metadata.status == "completed":
            if self.output is None:
                raise ValueError("completed tool results must include output")
            if self.error is not None:
                raise ValueError("completed tool results cannot include error")
        elif self.error is None:
            raise ValueError("non-completed tool results must include error")
        return self


def completed_tool_result(
    *,
    spec: ToolSpec,
    context: ToolCallContext | None = None,
    output: dict[str, Any] | list[dict[str, Any]] | str,
    duration_ms: float = 0.0,
    attempt: int = 1,
    completed_at: datetime | None = None,
) -> ToolResult:
    """Build a successful sanitized tool-result envelope."""

    metadata = ToolExecutionMetadata(
        tool_name=spec.name,
        category=spec.category,
        provider=spec.provider,
        status="completed",
        completed_at=completed_at,
        duration_ms=duration_ms,
        attempt=attempt,
        max_attempts=spec.timeout_policy.max_attempts,
        timeout_ms=spec.timeout_policy.timeout_ms,
    )
    return ToolResult(
        metadata=metadata,
        context=context or ToolCallContext(),
        output=output,
    )


def failed_tool_result(
    *,
    spec: ToolSpec,
    error_kind: ToolErrorKind,
    error_message: str,
    context: ToolCallContext | None = None,
    status: ToolStatus = "failed",
    retryable: bool = False,
    duration_ms: float = 0.0,
    attempt: int = 1,
    completed_at: datetime | None = None,
    provider_status_code: int | None = None,
    provider_error_code: str | None = None,
) -> ToolResult:
    """Build a failed sanitized tool-result envelope."""

    if status == "completed":
        raise ValueError("failed_tool_result cannot use status='completed'")

    metadata = ToolExecutionMetadata(
        tool_name=spec.name,
        category=spec.category,
        provider=spec.provider,
        status=status,
        completed_at=completed_at,
        duration_ms=duration_ms,
        attempt=attempt,
        max_attempts=spec.timeout_policy.max_attempts,
        timeout_ms=spec.timeout_policy.timeout_ms,
    )
    return ToolResult(
        metadata=metadata,
        context=context or ToolCallContext(),
        error=ToolError(
            kind=error_kind,
            message=error_message,
            retryable=retryable,
            provider_status_code=provider_status_code,
            provider_error_code=provider_error_code,
        ),
    )
