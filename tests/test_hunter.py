"""Tests for the hunt_contact tool.

All Hunter.io HTTP calls are mocked — no real API key needed.
Tests invoke via hunt_contact.invoke({...}) to exercise the full @tool stack.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from saas_lead_agent.tools.hunter import _pick_best, hunt_contact

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_EMAIL_EXECUTIVE: dict[str, Any] = {
    "value": "ceo@acme.com",
    "first_name": "Alice",
    "last_name": "Smith",
    "position": "CEO",
    "seniority": "executive",
    "department": "executive",
    "confidence": 92,
    "linkedin": "https://linkedin.com/in/alice-smith",
}

_EMAIL_JUNIOR: dict[str, Any] = {
    "value": "dev@acme.com",
    "first_name": "Bob",
    "last_name": "Jones",
    "position": "Developer",
    "seniority": "junior",
    "department": "engineering",
    "confidence": 75,
    "linkedin": None,
}

_EMAIL_SENIOR_IT: dict[str, Any] = {
    "value": "cto@acme.com",
    "first_name": "Carol",
    "last_name": "Lee",
    "position": "CTO",
    "seniority": "senior",
    "department": "it",
    "confidence": 88,
    "linkedin": "https://linkedin.com/in/carol-lee",
}


def _mock_response(emails: list[dict[str, Any]], status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = {"data": {"domain": "acme.com", "emails": emails}}
    resp.raise_for_status = MagicMock()
    return resp


def _mock_error_response(status_code: int) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = {
        "errors": [{"id": "unauthorized", "code": status_code, "details": "Invalid API key"}]
    }
    exc = httpx.HTTPStatusError("error", request=MagicMock(), response=resp)
    resp.raise_for_status.side_effect = exc
    return resp


# ---------------------------------------------------------------------------
# _pick_best unit tests (pure function)
# ---------------------------------------------------------------------------


def test_pick_best_returns_none_for_empty() -> None:
    assert _pick_best([]) is None


def test_pick_best_prefers_executive_seniority() -> None:
    result = _pick_best([_EMAIL_JUNIOR, _EMAIL_EXECUTIVE])
    assert result is not None
    assert result["value"] == "ceo@acme.com"


def test_pick_best_prefers_target_department_over_confidence() -> None:
    # _EMAIL_JUNIOR has department=engineering (target) but lower confidence
    # than a hypothetical high-confidence non-target entry
    high_conf_sales: dict[str, Any] = {
        "value": "sales@acme.com",
        "seniority": "junior",
        "department": "sales",
        "confidence": 99,
    }
    result = _pick_best([high_conf_sales, _EMAIL_JUNIOR])
    assert result is not None
    assert result["value"] == "dev@acme.com"  # engineering dept wins


def test_pick_best_falls_back_to_highest_confidence() -> None:
    no_target: dict[str, Any] = {"value": "a@acme.com", "seniority": "junior",
                                  "department": "sales", "confidence": 60}
    higher: dict[str, Any] = {"value": "b@acme.com", "seniority": "junior",
                               "department": "sales", "confidence": 80}
    result = _pick_best([no_target, higher])
    assert result is not None
    assert result["value"] == "b@acme.com"


# ---------------------------------------------------------------------------
# hunt_contact happy paths
# ---------------------------------------------------------------------------


def test_hunt_contact_returns_best_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUNTER_API_KEY", "test-key")
    mock_resp = _mock_response([_EMAIL_JUNIOR, _EMAIL_EXECUTIVE])

    with patch("saas_lead_agent.tools.hunter.httpx.get", return_value=mock_resp):
        result = hunt_contact.invoke({"domain": "acme.com"})

    assert result["value"] == "ceo@acme.com"
    assert result["first_name"] == "Alice"
    assert result["confidence"] == 92
    assert result["linkedin"] == "https://linkedin.com/in/alice-smith"


def test_hunt_contact_returns_empty_dict_when_no_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HUNTER_API_KEY", "test-key")
    mock_resp = _mock_response([])

    with patch("saas_lead_agent.tools.hunter.httpx.get", return_value=mock_resp):
        result = hunt_contact.invoke({"domain": "unknown-startup.io"})

    assert result == {}


def test_hunt_contact_passes_correct_params(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUNTER_API_KEY", "my-key")
    mock_get = MagicMock(return_value=_mock_response([_EMAIL_EXECUTIVE]))

    with patch("saas_lead_agent.tools.hunter.httpx.get", mock_get):
        hunt_contact.invoke({"domain": "acme.com"})

    call_kwargs = mock_get.call_args
    params = call_kwargs.kwargs["params"]
    assert params["domain"] == "acme.com"
    assert params["api_key"] == "my-key"
    assert params["type"] == "personal"
    assert params["limit"] == 10


def test_hunt_contact_all_fields_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUNTER_API_KEY", "test-key")
    mock_resp = _mock_response([_EMAIL_SENIOR_IT])

    with patch("saas_lead_agent.tools.hunter.httpx.get", return_value=mock_resp):
        result = hunt_contact.invoke({"domain": "acme.com"})

    for field in ("value", "first_name", "last_name", "position", "seniority",
                  "department", "confidence", "linkedin"):
        assert field in result, f"missing field: {field}"


# ---------------------------------------------------------------------------
# hunt_contact error cases
# ---------------------------------------------------------------------------


def test_hunt_contact_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HUNTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="HUNTER_API_KEY"):
        hunt_contact.invoke({"domain": "acme.com"})


def test_hunt_contact_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUNTER_API_KEY", "bad-key")
    bad_resp = _mock_error_response(401)

    with patch("saas_lead_agent.tools.hunter.httpx.get", return_value=bad_resp):
        with pytest.raises(RuntimeError, match="Hunter.io API error 401"):
            hunt_contact.invoke({"domain": "acme.com"})


def test_hunt_contact_raises_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUNTER_API_KEY", "test-key")
    exc = httpx.ConnectError("Connection refused")

    with patch("saas_lead_agent.tools.hunter.httpx.get", side_effect=exc):
        with pytest.raises(RuntimeError, match="Network error"):
            hunt_contact.invoke({"domain": "acme.com"})


def test_hunt_contact_raises_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUNTER_API_KEY", "test-key")
    bad_resp = _mock_error_response(429)

    with patch("saas_lead_agent.tools.hunter.httpx.get", return_value=bad_resp):
        with pytest.raises(RuntimeError, match="Hunter.io API error 429"):
            hunt_contact.invoke({"domain": "acme.com"})
