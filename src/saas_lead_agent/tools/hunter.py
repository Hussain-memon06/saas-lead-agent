"""Hunter.io Domain Search tool — finds the top decision-maker email for a domain."""

import hashlib
import json
import os
from time import perf_counter
from typing import Any

import httpx
from langchain_core.tools import tool

from saas_lead_agent.tools.contracts import (
    ToolCallContext,
    ToolResult,
    ToolSpec,
    ToolTimeoutPolicy,
    completed_tool_result,
    failed_tool_result,
)
from saas_lead_agent.tools.recording import record_tool_result

_BASE_URL = "https://api.hunter.io/v2/domain-search"

# Seniority levels and departments that indicate decision-making authority.
_TARGET_SENIORITY = {"senior", "executive"}
_TARGET_DEPARTMENTS = {"executive", "it", "engineering", "management"}

HUNT_CONTACT_SPEC = ToolSpec(
    name="hunt_contact",
    category="contact_finding",
    provider="hunter",
    description="Find a likely decision-maker contact for a company domain.",
    timeout_policy=ToolTimeoutPolicy(timeout_ms=15_000, max_attempts=1),
)


def _pick_best(emails: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the highest-confidence decision-maker from an email list.

    Prefers records matching _TARGET_SENIORITY / _TARGET_DEPARTMENTS, then
    falls back to the first result by confidence descending.
    """
    if not emails:
        return None

    scored = sorted(emails, key=lambda e: e.get("confidence", 0), reverse=True)

    for email in scored:
        seniority = (email.get("seniority") or "").lower()
        department = (email.get("department") or "").lower()
        if seniority in _TARGET_SENIORITY or department in _TARGET_DEPARTMENTS:
            return email

    return scored[0]


@tool
def hunt_contact(domain: str) -> dict[str, Any]:
    """Search Hunter.io for the top decision-maker email address at a domain.

    Calls the Hunter.io Domain Search API and returns the highest-confidence
    contact matching senior/executive seniority or executive/IT/engineering
    department. Falls back to the top result by confidence if no match found.

    Returns a dict with keys: value, first_name, last_name, position, seniority,
    department, confidence, linkedin (all nullable except value). Returns an
    empty dict when the domain has no results.

    Reads HUNTER_API_KEY from the environment.

    Args:
        domain: The company domain to search (e.g. ``"acme.com"``).

    Returns:
        Contact dict, or empty dict if no results.

    Raises:
        RuntimeError: If HUNTER_API_KEY is not set, the request fails with a
            non-2xx status, or a network error occurs.
    """
    result = run_hunt_contact(domain)
    record_tool_result(result)

    if result.metadata.status == "completed" and isinstance(result.output, dict):
        return result.output

    if result.error is not None:
        raise RuntimeError(result.error.message)

    raise RuntimeError("Unknown Hunter.io failure")


def run_hunt_contact(domain: str) -> ToolResult:
    """Search Hunter.io and return a typed tool-result envelope."""
    context = ToolCallContext(input_hash=_input_hash(domain=domain))
    started_at = perf_counter()

    api_key = os.environ.get("HUNTER_API_KEY")
    if not api_key:
        return failed_tool_result(
            spec=HUNT_CONTACT_SPEC,
            context=context,
            error_kind="configuration",
            error_message="HUNTER_API_KEY environment variable is not set",
            duration_ms=_elapsed_ms(started_at),
        )

    try:
        response = httpx.get(
            _BASE_URL,
            params={
                "domain": domain,
                "api_key": api_key,
                "limit": 10,
                "type": "personal",
            },
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        return failed_tool_result(
            spec=HUNT_CONTACT_SPEC,
            context=context,
            status="rate_limited" if status_code == 429 else "failed",
            error_kind="rate_limit" if status_code == 429 else "http_status",
            error_message=f"Hunter.io API error {status_code} for domain '{domain}'",
            retryable=status_code in {408, 409, 425, 429, 500, 502, 503, 504},
            duration_ms=_elapsed_ms(started_at),
            provider_status_code=status_code,
        )
    except httpx.RequestError:
        return failed_tool_result(
            spec=HUNT_CONTACT_SPEC,
            context=context,
            error_kind="network",
            error_message=f"Network error contacting Hunter.io for domain '{domain}'",
            retryable=True,
            duration_ms=_elapsed_ms(started_at),
        )

    payload: dict[str, Any] = response.json()
    emails: list[dict[str, Any]] = payload.get("data", {}).get("emails", [])
    best = _pick_best(emails)

    if best is None:
        return completed_tool_result(
            spec=HUNT_CONTACT_SPEC,
            context=context,
            output={},
            duration_ms=_elapsed_ms(started_at),
        )

    output = {
        "value": best.get("value"),
        "first_name": best.get("first_name"),
        "last_name": best.get("last_name"),
        "position": best.get("position"),
        "seniority": best.get("seniority"),
        "department": best.get("department"),
        "confidence": best.get("confidence"),
        "linkedin": best.get("linkedin"),
    }
    return completed_tool_result(
        spec=HUNT_CONTACT_SPEC,
        context=context,
        output=output,
        duration_ms=_elapsed_ms(started_at),
    )


def _input_hash(*, domain: str) -> str:
    raw = json.dumps({"domain": domain}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
