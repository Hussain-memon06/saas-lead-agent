"""Scoped tool-result recording for graph node execution."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from saas_lead_agent.tools.contracts import ToolResult


@dataclass
class _ToolCapture:
    node: str | None = None
    run_id: str | None = None
    thread_id: str | None = None
    request_id: str | None = None
    records: list[dict[str, Any]] = field(default_factory=list)


_CURRENT_CAPTURE: ContextVar[_ToolCapture | None] = ContextVar(
    "saas_lead_agent_tool_capture",
    default=None,
)


@contextmanager
def capture_tool_results(
    *,
    node: str | None = None,
    run_id: str | None = None,
    thread_id: str | None = None,
    request_id: str | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Collect sanitized tool-result records within a graph node call."""

    capture = _ToolCapture(
        node=node,
        run_id=run_id,
        thread_id=thread_id,
        request_id=request_id,
    )
    token = _CURRENT_CAPTURE.set(capture)
    try:
        yield capture.records
    finally:
        _CURRENT_CAPTURE.reset(token)


def record_tool_result(result: ToolResult) -> None:
    """Append a sanitized tool record when a capture scope is active."""

    capture = _CURRENT_CAPTURE.get()
    if capture is None:
        return
    capture.records.append(_sanitize_tool_result(result, capture))


def _sanitize_tool_result(
    result: ToolResult,
    capture: _ToolCapture,
) -> dict[str, Any]:
    metadata = result.metadata
    record: dict[str, Any] = {
        "tool_name": metadata.tool_name,
        "category": metadata.category,
        "provider": metadata.provider,
        "status": metadata.status,
        "duration_ms": metadata.duration_ms,
        "attempt": metadata.attempt,
        "max_attempts": metadata.max_attempts,
        "timeout_ms": metadata.timeout_ms,
    }
    if capture.node:
        record["node"] = capture.node
    if capture.run_id:
        record["run_id"] = capture.run_id
    if capture.thread_id:
        record["thread_id"] = capture.thread_id
    if capture.request_id:
        record["request_id"] = capture.request_id
    if result.context.input_hash:
        record["input_hash"] = result.context.input_hash
    if result.context.idempotency_key:
        record["has_idempotency_key"] = True
    output_count = _output_count(result.output)
    if output_count is not None:
        record["output_count"] = output_count
    if result.error is not None:
        record["error_kind"] = result.error.kind
        record["retryable"] = result.error.retryable
        if result.error.provider_status_code is not None:
            record["provider_status_code"] = result.error.provider_status_code
        if result.error.provider_error_code:
            record["provider_error_code"] = result.error.provider_error_code
    return record


def _output_count(output: object) -> int | None:
    if isinstance(output, list):
        return len(output)
    if isinstance(output, dict):
        return len(output)
    if isinstance(output, str):
        return 1
    return None
