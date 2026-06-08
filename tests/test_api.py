"""Tests for the POST /api/qualify endpoint.

Strategy:
- QualifyRequest validation is tested directly (pure Pydantic, no HTTP layer).
- Endpoint tests use httpx.AsyncClient + ASGITransport against the real FastAPI
  app.  The module-level _graph in routes.py is patched with an AsyncMock so no
  real LangGraph / LLM calls occur.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
    "fit_level": "high",
    "score_breakdown": {"baseline": 2.5, "signal_strength": 1.5},
    "score_confidence": "high",
    "needs_human_review": False,
    "score_reasons": ["company profile has usable sourced detail"],
    "score_uncertainty": [],
    "grounding_report": {
        "evidence": {"items": []},
        "source_urls": ["https://acme.example.com/about"],
        "supported_claim_count": 1,
        "unsupported_claims": [],
        "missing_source_count": 0,
        "evidence_coverage": 1.0,
        "is_sufficient": True,
    },
    "outreach_quality": {
        "quality_score": 95,
        "passed": True,
        "issues": [],
        "personalization_hooks": ["company_name", "buying_signal"],
        "spam_terms": [],
        "placeholder_terms": [],
        "word_count": 42,
    },
    "score_explanation": "8/10 — B2B SaaS ✅, Series A ✅, US ✅, hiring SDRs ✅",
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


def test_qualify_request_icp_context_defaults_to_none() -> None:
    req = QualifyRequest(url="https://acme.example.com")
    assert req.icp_context is None


def test_qualify_request_accepts_icp_context() -> None:
    req = QualifyRequest(
        url="https://acme.example.com",
        icp_context={"target_industries": ["B2B SaaS"], "value_proposition": "..."},
    )
    assert req.icp_context == {
        "target_industries": ["B2B SaaS"],
        "value_proposition": "...",
    }


def test_qualify_request_rejects_localhost_url() -> None:
    with pytest.raises(ValidationError, match="hostname is not allowed"):
        QualifyRequest(url="https://localhost")


def test_qualify_request_rejects_private_ip_url() -> None:
    with pytest.raises(ValidationError, match="IP address is not allowed"):
        QualifyRequest(url="http://10.0.0.5")


def test_qualify_request_rejects_invalid_icp_shape() -> None:
    with pytest.raises(ValidationError, match="must be a list"):
        QualifyRequest(
            url="https://acme.example.com",
            icp_context={"target_industries": "B2B SaaS"},
        )


# ---------------------------------------------------------------------------
# QualifyResponse schema
# ---------------------------------------------------------------------------


def test_qualify_response_defaults() -> None:
    resp = QualifyResponse(thread_id="lead:acme.example.com")
    assert resp.request_id is None
    assert resp.company_profile is None
    assert resp.contact is None
    assert resp.signals is None
    assert resp.fit_score is None
    assert resp.fit_level is None
    assert resp.score_breakdown is None
    assert resp.score_confidence is None
    assert resp.score_explanation is None
    assert resp.needs_human_review is None
    assert resp.score_reasons is None
    assert resp.score_uncertainty is None
    assert resp.grounding_report is None
    assert resp.outreach_quality is None
    assert resp.email_subject is None
    assert resp.email_body is None
    assert resp.email_approved is None
    assert resp.send_result is None
    assert resp.message_id is None
    assert resp.sent_at is None
    assert resp.interrupted is False
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
    assert body["request_id"]
    assert body["thread_id"] == "lead:acme.example.com"
    assert body["company_profile"]["name"] == "Acme Corp"
    assert body["contact"]["source"] == "stub"
    assert body["signals"] == []
    assert body["fit_score"] == 8
    assert body["fit_level"] == "high"
    assert body["score_breakdown"]["signal_strength"] == 1.5
    assert body["score_confidence"] == "high"
    assert body["needs_human_review"] is False
    assert body["score_reasons"] == ["company profile has usable sourced detail"]
    assert body["score_uncertainty"] == []
    assert body["grounding_report"]["is_sufficient"] is True
    assert body["outreach_quality"]["passed"] is True
    assert body["score_explanation"] == "8/10 — B2B SaaS ✅, Series A ✅, US ✅, hiring SDRs ✅"
    assert body["email_subject"] == "Quick question about Acme Corp"
    assert body["email_body"] == "Hi Alice, saw your recent Series A — congrats!"
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_qualify_www_prefix_stripped_from_domain() -> None:
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value={**_GRAPH_RESULT, "domain": "acme.example.com"})

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/qualify", json={"url": "https://www.acme.example.com"})

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
    assert state["icp_context"] is None
    assert state["company_profile"] is None
    assert state["fit_level"] is None
    assert state["score_breakdown"] is None
    assert state["score_confidence"] is None
    assert state["grounding_report"] is None
    assert state["outreach_quality"] is None
    assert state["errors"] == []

    config = call_args.kwargs["config"]
    assert config["configurable"]["thread_id"] == "lead:acme.example.com"
    assert config["metadata"]["thread_id"] == "lead:acme.example.com"
    assert config["metadata"]["request_id"]


@pytest.mark.asyncio
async def test_qualify_forwards_icp_context_into_state() -> None:
    """When the request carries icp_context, it must reach the graph state."""
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=_GRAPH_RESULT)
    icp = {
        "seller_name": "John at Acme Agency",
        "target_industries": ["B2B SaaS"],
        "must_have_signals": ["Recent funding"],
        "value_proposition": "We help SaaS teams ship faster.",
    }

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            await client.post(
                "/api/qualify",
                json={"url": "https://acme.example.com", "icp_context": icp},
            )

    state = mock_graph.ainvoke.call_args.args[0]
    assert state["icp_context"] == icp


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
async def test_qualify_invalid_private_ip_returns_422() -> None:
    async with await _client() as client:
        resp = await client.post("/api/qualify", json={"url": "http://127.0.0.1"})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_request_id_header_generated_on_error_response() -> None:
    async with await _client() as client:
        resp = await client.post("/api/qualify", json={"url": "not-a-url"})

    assert resp.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_request_id_header_preserved_from_client() -> None:
    async with await _client() as client:
        resp = await client.post(
            "/api/qualify",
            json={"url": "not-a-url"},
            headers={"X-Request-ID": "req-test-123"},
        )

    assert resp.headers["X-Request-ID"] == "req-test-123"


@pytest.mark.asyncio
async def test_qualify_response_includes_request_id_from_client() -> None:
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=_GRAPH_RESULT)

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post(
                "/api/qualify",
                json={"url": "https://acme.example.com"},
                headers={"X-Request-ID": "req-test-123"},
            )

    assert resp.json()["request_id"] == "req-test-123"
    config = mock_graph.ainvoke.call_args.kwargs["config"]
    assert config["metadata"]["request_id"] == "req-test-123"


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


# ---------------------------------------------------------------------------
# HITL — interrupted flag, /approve, /reject
# ---------------------------------------------------------------------------


def _make_graph_mock(
    ainvoke_result: dict[str, Any],
    next_nodes: tuple[str, ...] = (),
) -> AsyncMock:
    """Return an AsyncMock graph with controllable ainvoke + aget_state.

    ``next_nodes`` populates ``snapshot.next`` — non-empty means the graph
    is paused at an interrupt.
    """
    snapshot = MagicMock()
    snapshot.next = next_nodes

    mock = AsyncMock()
    mock.ainvoke = AsyncMock(return_value=ainvoke_result)
    mock.aget_state = AsyncMock(return_value=snapshot)
    return mock


@pytest.mark.asyncio
async def test_qualify_returns_interrupted_true_when_paused() -> None:
    """/qualify reports interrupted=True when the graph paused at await_approval."""
    paused_result = {**_GRAPH_RESULT, "send_result": None}
    mock_graph = _make_graph_mock(paused_result, next_nodes=("await_approval",))

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/qualify", json={"url": "https://acme.example.com"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["interrupted"] is True
    assert body["send_result"] is None


@pytest.mark.asyncio
async def test_qualify_returns_interrupted_false_when_complete() -> None:
    """/qualify reports interrupted=False when the graph ran to END."""
    complete_result = {**_GRAPH_RESULT, "send_result": "sent", "email_approved": True}
    mock_graph = _make_graph_mock(complete_result, next_nodes=())

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/qualify", json={"url": "https://acme.example.com"})

    assert resp.status_code == 200
    assert resp.json()["interrupted"] is False


@pytest.mark.asyncio
async def test_approve_resumes_graph_with_true() -> None:
    """POST /api/leads/{thread_id}/approve calls ainvoke(Command(resume=True))."""
    from langgraph.types import Command

    resumed_result = {**_GRAPH_RESULT, "email_approved": True, "send_result": "sent"}
    mock_graph = _make_graph_mock(resumed_result, next_nodes=())

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/leads/lead:acme.example.com/approve")

    assert resp.status_code == 200
    body = resp.json()
    assert body["request_id"]
    assert body["thread_id"] == "lead:acme.example.com"
    assert body["email_approved"] is True
    assert body["send_result"] == "sent"
    assert body["interrupted"] is False

    # Verify Command(resume=True) was passed
    call_args = mock_graph.ainvoke.call_args
    cmd = call_args.args[0]
    assert isinstance(cmd, Command)
    assert cmd.resume is True
    # durability="sync" required for HITL per CLAUDE.md
    assert call_args.kwargs.get("durability") == "sync"


@pytest.mark.asyncio
async def test_reject_resumes_graph_with_false() -> None:
    """POST /api/leads/{thread_id}/reject calls ainvoke(Command(resume=False))."""
    from langgraph.types import Command

    rejected_result = {**_GRAPH_RESULT, "email_approved": False, "send_result": "rejected"}
    mock_graph = _make_graph_mock(rejected_result, next_nodes=())

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/leads/lead:acme.example.com/reject")

    assert resp.status_code == 200
    body = resp.json()
    assert body["email_approved"] is False
    assert body["send_result"] == "rejected"

    call_args = mock_graph.ainvoke.call_args
    cmd = call_args.args[0]
    assert isinstance(cmd, Command)
    assert cmd.resume is False


@pytest.mark.asyncio
async def test_approve_returns_500_on_graph_failure() -> None:
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("checkpointer down"))

    with patch("saas_lead_agent.api.routes._graph", mock_graph):
        async with await _client() as client:
            resp = await client.post("/api/leads/lead:acme.example.com/approve")

    assert resp.status_code == 500
    assert "checkpointer down" in resp.json()["detail"]
