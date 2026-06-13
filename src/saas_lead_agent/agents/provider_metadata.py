"""Sanitized provider metadata helpers for graph nodes."""

from collections.abc import Iterable, Mapping
from time import perf_counter
from typing import Any


def elapsed_ms(started_at: float) -> float:
    """Return elapsed milliseconds rounded for stable metadata output."""
    return round((perf_counter() - started_at) * 1000, 3)


def token_usage_from_messages(messages: Iterable[Any]) -> dict[str, int]:
    """Extract normalized token counts from LangChain messages when available."""
    totals: dict[str, int] = {}
    for message in messages:
        usage = _usage_from_mapping(getattr(message, "usage_metadata", None))
        if not usage:
            response_metadata = getattr(message, "response_metadata", None)
            if isinstance(response_metadata, Mapping):
                usage = _usage_from_mapping(
                    response_metadata.get("token_usage") or response_metadata.get("usage")
                )
        _add_usage(totals, usage)
    return totals


def provider_usage_record(
    *,
    node: str,
    provider: str,
    model: str | None,
    started_at: float,
    status: str,
    messages: Iterable[Any] = (),
    error_type: str | None = None,
) -> dict[str, Any]:
    """Build a provider usage record without prompts, completions, or PII."""
    record: dict[str, Any] = {
        "node": node,
        "provider": provider,
        "model": model,
        "status": status,
        "duration_ms": elapsed_ms(started_at),
        "token_usage": token_usage_from_messages(messages),
    }
    if error_type:
        record["error_type"] = error_type
    return record


def _usage_from_mapping(raw: Any) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        return {}

    input_tokens = _first_int(raw, ("input_tokens", "prompt_tokens"))
    output_tokens = _first_int(raw, ("output_tokens", "completion_tokens"))
    total_tokens = _first_int(raw, ("total_tokens",))
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)

    usage: dict[str, int] = {}
    if input_tokens is not None:
        usage["input_tokens"] = input_tokens
    if output_tokens is not None:
        usage["output_tokens"] = output_tokens
    if total_tokens is not None:
        usage["total_tokens"] = total_tokens
    return usage


def _first_int(raw: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return max(value, 0)
    return None


def _add_usage(totals: dict[str, int], usage: dict[str, int]) -> None:
    for key, value in usage.items():
        totals[key] = totals.get(key, 0) + value
