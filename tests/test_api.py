"""Tests for the POST /api/qualify endpoint.

Strategy:
- QualifyRequest validation is tested directly (pure Pydantic, no HTTP layer).
- Endpoint tests use httpx.AsyncClient + ASGITransport against the real FastAPI
  app.  The module-level _graph in routes.py is patched with an AsyncMock so no
  real LangGraph / LLM calls occur.
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from saas_lead_agent.api.main import app
from saas_lead_agent.api.schemas import QualifyRequest, QualifyResponse

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_PROFILE: dict[str, Any] = {
    "name": "Acme Corp",
    "tagline": "Anvils for every occasion",
    "hq": "Tucson, USA",
    "employees_estimate": "50-200",
    "funding_stage": "Series A",
    "products": ["Heavy Anvil"],
    "notable_customers": ["Wile E. Coyote"],
}

_CONTACT: dict[str, Any] = {
    "name": None,
    "title": None,
    "email": None,
    "linkedin": None,
    "source": "stub",
    "domain": "acme.example.com",
}

_GRAPH_RESULT: dict[str, Any] = {
    "company_url": "https://acme.example.com",
    "domain": "acme.example.com",
    "messages": [],
    "company_profile": _PROFILE,
    "contact": _CONTACT,
    "signals": [],
    "fit_score": 8,
    "email_subject": "Quick question about Acme Corp",
    "email_body": "Hi Alice, saw your recent Series A — congrats!",
    "errors": [],
}


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# QualifyRequest validation (no HTTP layer)
# ---------------------------------------------------------------------------


def test_qualify_request_valid_https() -> None:
    req = QualifyRequest(url="https://acme.example.com")
    assert req.url == "https://acme.example.com"


def test_qualify_request_valid_http() -> None:
    req = QualifyRequest(url="http://acme.example.com")
    assert req.url == "http://acme.example.com"


def test_qualify_request_strips_whitespace() -> None:
    req = QualifyRequest(url="  https://acme.example.com  ")
    assert req.url == "https://acme.example.com"


def test_qualify_request_rejects_bare_hostname() -> None:
    with pytest.raises(ValidationError, match="HTTP/HTTPS"):
        QualifyRequest(url="acme.example.com")


def test_qualify_request_rejects_ftp() -> None:
    with pytest.raises(ValidationError, match="HTTP/HTTPS"):
        QualifyRequest(url="ftp://acme.example.com")


def test_qualify_request_rejects_empty_string() -> None:
    with pytest.raises(ValidationError):
        QualifyRequest(url="")


# ---------------------------------------------------------------------------
# QualifyResponse schema
# ---------------------------------------------------------------------------


def test_qualify_response_defaults() -> None:
    resp = QualifyResponse(thread_id="lead:acme.example.com")
    assert resp.company_profile is None
    assert resp.contact is None
    assert resp.signals is None
    assert resp.fit_score is None
    assert resp.email_subject is None
    assert resp.email_body is None
    assert resp.errors == []


# ---------------------------------------------------------------------------
# POST /api/qualify — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qualify_happy_path() -> None:
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=_GRAPH_RESULT)

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/qualify", json={"url": "https://acme.example.com"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["thread_id"] == "lead:acme.example.com"
    assert body["company_profile"]["name"] == "Acme Corp"
    assert body["contact"]["source"] == "stub"
    assert body["signals"] == []
    assert body["fit_score"] == 8
    assert body["email_subject"] == "Quick question about Acme Corp"
    assert body["email_body"] == "Hi Alice, saw your recent Series A — congrats!"
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_qualify_www_prefix_stripped_from_domain() -> None:
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value={**_GRAPH_RESULT, "domain": "acme.example.com"})

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post(
                "/api/qualify", json={"url": "https://www.acme.example.com"}
            )

    assert resp.status_code == 200
    assert resp.json()["thread_id"] == "lead:acme.example.com"


@pytest.mark.asyncio
async def test_qualify_thread_id_format() -> None:
    """thread_id must follow lead:{domain} per CLAUDE.md."""
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=_GRAPH_RESULT)

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/qualify", json={"url": "https://acme.example.com"})

    assert resp.json()["thread_id"].startswith("lead:")


@pytest.mark.asyncio
async def test_qualify_passes_correct_state_to_graph() -> None:
    """ainvoke must receive a properly formed LeadState."""
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=_GRAPH_RESULT)

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            await client.post("/api/qualify", json={"url": "https://acme.example.com"})

    call_args = mock_graph.ainvoke.call_args
    # state is the first positional arg; config is the second positional arg
    # (routes.py calls ainvoke(initial_state, config=config) so config is kwargs)
    state = call_args.args[0]
    assert state["company_url"] == "https://acme.example.com"
    assert state["domain"] == "acme.example.com"
    assert state["company_profile"] is None
    assert state["errors"] == []

    config = call_args.kwargs["config"]
    assert config["configurable"]["thread_id"] == "lead:acme.example.com"


@pytest.mark.asyncio
async def test_qualify_errors_in_result_returned_not_raised() -> None:
    """Graph-level errors (soft failures) go into the response, not HTTP 500."""
    result_with_errors = {
        **_GRAPH_RESULT,
        "company_profile": None,
        "errors": ["company_researcher: JSON parse error"],
    }
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=result_with_errors)

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/qualify", json={"url": "https://acme.example.com"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["company_profile"] is None
    assert "company_researcher: JSON parse error" in body["errors"]


# ---------------------------------------------------------------------------
# POST /api/qualify — error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qualify_invalid_url_returns_422() -> None:
    async with await _client() as client:
        resp = await client.post("/api/qualify", json={"url": "not-a-url"})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_qualify_missing_url_field_returns_422() -> None:
    async with await _client() as client:
        resp = await client.post("/api/qualify", json={})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_qualify_graph_exception_returns_500() -> None:
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("LLM quota exceeded"))

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/qualify", json={"url": "https://acme.example.com"})

    assert resp.status_code == 500
    assert "LLM quota exceeded" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_qualify_ftp_url_returns_422() -> None:
    async with await _client() as client:
        resp = await client.post("/api/qualify", json={"url": "ftp://acme.example.com"})

    assert resp.status_code == 422
