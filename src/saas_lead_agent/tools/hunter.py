"""Hunter.io Domain Search tool — finds the top decision-maker email for a domain."""

import os
from typing import Any

import httpx
from langchain_core.tools import tool

_BASE_URL = "https://api.hunter.io/v2/domain-search"

# Seniority levels and departments that indicate decision-making authority.
_TARGET_SENIORITY = {"senior", "executive"}
_TARGET_DEPARTMENTS = {"executive", "it", "engineering", "management"}


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
    api_key = os.environ.get("HUNTER_API_KEY")
    if not api_key:
        raise RuntimeError("HUNTER_API_KEY environment variable is not set")

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
        raise RuntimeError(
            f"Hunter.io API error {exc.response.status_code} for domain '{domain}'"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Network error contacting Hunter.io for domain '{domain}': {exc}"
        ) from exc

    payload: dict[str, Any] = response.json()
    emails: list[dict[str, Any]] = payload.get("data", {}).get("emails", [])
    best = _pick_best(emails)

    if best is None:
        return {}

    return {
        "value": best.get("value"),
        "first_name": best.get("first_name"),
        "last_name": best.get("last_name"),
        "position": best.get("position"),
        "seniority": best.get("seniority"),
        "department": best.get("department"),
        "confidence": best.get("confidence"),
        "linkedin": best.get("linkedin"),
    }
