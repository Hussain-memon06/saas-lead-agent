"""Tests for the POST /api/qualify endpoint.

Strategy:
- QualifyRequest validation is tested directly (pure Pydantic, no HTTP layer).
- Endpoint tests use httpx.AsyncClient + ASGITransport against the real FastAPI
  app.  The module-level _graph in routes.py is patched with an AsyncMock so no
  real LangGraph / LLM calls occur.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from saas_lead_agent.api.main import app
from saas_lead_agent.api.schemas import QualifyRequest, QualifyResponse
from saas_lead_agent.persistence import InMemoryLeadRunRepository, LeadRunSnapshot, RunEvent

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
    assert resp.run_id is None
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
    assert resp.processing_metadata is None
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
    assert body["run_id"]
    assert body["thread_id"] == "lead:acme.example.com"
    metadata = body["processing_metadata"]
    assert metadata["run_id"] == body["run_id"]
    assert metadata["thread_id"] == body["thread_id"]
    assert metadata["auth_mode"] == "anonymous_demo"
    assert metadata["auth_user_present"] is False
    assert metadata["model_used"] == "gpt-4o-mini"
    assert metadata["total_tokens"] == 0
    assert metadata["estimated_cost_usd"] == 0.0
    assert metadata["timings_ms"]["graph"] >= 0
    assert metadata["timings_ms"]["api_total"] >= metadata["timings_ms"]["graph"]
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
async def test_qualify_processing_metadata_aggregates_provider_usage() -> None:
    store = InMemoryLeadRunRepository()
    result = {
        **_GRAPH_RESULT,
        "retrieval_events": [
            {
                "event_id": "ret-1",
                "run_id": "run-from-graph",
                "thread_id": "lead:acme.example.com",
                "request_id": "req-from-graph",
                "retrieval_node": "retrieve_icp_context",
                "query_text_hash": "abc1234567890def",
                "query_metadata": {"query_kind": "icp"},
                "filters": {
                    "document_types": ["icp", "offer"],
                    "trust_labels": ["trusted_user"],
                },
                "top_k": 3,
                "selected_chunk_ids": ["chunk-1"],
                "scores": {"chunk-1": 0.9},
                "reasons": {"chunk-1": "lexical_term_match"},
                "token_budget": 400,
                "tokens_selected": 125,
                "raw_prompt": "do not return prompt text",
                "chunk_text": "do not return retrieved chunk text",
                "embedding_vector": [0.1, 0.2],
            }
        ],
        "tool_usage": [
            {
                "node": "company_researcher",
                "run_id": "run-from-graph",
                "thread_id": "lead:acme.example.com",
                "request_id": "req-from-graph",
                "tool_name": "web_search",
                "category": "search",
                "provider": "tavily",
                "status": "completed",
                "duration_ms": 4.25,
                "attempt": 1,
                "max_attempts": 1,
                "timeout_ms": 15000,
                "input_hash": "d" * 64,
                "output_count": 2,
                "raw_provider_payload": {"api_key": "secret"},
                "output": [{"title": "raw result should not be returned"}],
                "error_message": "raw provider error should not be returned",
            }
        ],
        "provider_usage": [
            {
                "node": "company_researcher",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "status": "completed",
                "duration_ms": 11.5,
                "token_usage": {
                    "input_tokens": 100,
                    "output_tokens": 25,
                    "total_tokens": 125,
                },
            },
            {
                "node": "dossier_writer",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "status": "completed",
                "duration_ms": 7.0,
                "token_usage": {
                    "input_tokens": 20,
                    "output_tokens": 25,
                    "total_tokens": 45,
                },
            },
        ],
    }
    mock_graph = _make_graph_mock(result)

    with (
        patch("saas_lead_agent.api.routes._graph", mock_graph),
        patch("saas_lead_agent.api.routes._lead_store", store),
        patch.dict(
            "os.environ",
            {
                "OPENAI_GPT_4O_MINI_INPUT_COST_PER_MILLION": "1",
                "OPENAI_GPT_4O_MINI_OUTPUT_COST_PER_MILLION": "2",
            },
            clear=False,
        ),
    ):
        async with await _client() as client:
            resp = await client.post("/api/qualify", json={"url": "https://acme.example.com"})

    assert resp.status_code == 200
    metadata = resp.json()["processing_metadata"]
    assert metadata["total_tokens"] == 170
    assert metadata["token_usage"] == {
        "input_tokens": 120,
        "output_tokens": 50,
        "total_tokens": 170,
    }
    assert metadata["estimated_cost_usd"] == 0.00022
    assert metadata["cost_breakdown_usd"] == {
        "openai_input": 0.00012,
        "openai_output": 0.0001,
    }
    assert metadata["provider_status"] == {
        "company_researcher": "completed",
        "dossier_writer": "completed",
    }
    assert metadata["timings_ms"]["node.company_researcher"] == 11.5
    assert metadata["timings_ms"]["node.dossier_writer"] == 7.0
    assert metadata["auth_mode"] == "anonymous_demo"
    assert metadata["auth_user_present"] is False
    assert metadata["retrieval_events"] == [
        {
            "event_id": "ret-1",
            "run_id": "run-from-graph",
            "thread_id": "lead:acme.example.com",
            "request_id": "req-from-graph",
            "retrieval_node": "retrieve_icp_context",
            "query_text_hash": "abc1234567890def",
            "query_metadata": {"query_kind": "icp"},
            "filters": {
                "document_types": ["icp", "offer"],
                "trust_labels": ["trusted_user"],
            },
            "top_k": 3,
            "selected_chunk_ids": ["chunk-1"],
            "scores": {"chunk-1": 0.9},
            "reasons": {"chunk-1": "lexical_term_match"},
            "token_budget": 400,
            "tokens_selected": 125,
        }
    ]
    assert metadata["tool_status"] == {"company_researcher.web_search": "completed"}
    assert metadata["tool_events"] == [
        {
            "node": "company_researcher",
            "run_id": "run-from-graph",
            "thread_id": "lead:acme.example.com",
            "request_id": "req-from-graph",
            "tool_name": "web_search",
            "category": "search",
            "provider": "tavily",
            "status": "completed",
            "duration_ms": 4.25,
            "attempt": 1,
            "max_attempts": 1,
            "timeout_ms": 15000,
            "input_hash": "d" * 64,
            "output_count": 2,
        }
    ]
    assert metadata["timings_ms"]["tool.company_researcher.web_search"] == 4.25

    events = await store.list_events("lead:acme.example.com")
    assert events[0].metadata["total_tokens"] == 170
    assert events[0].metadata["provider_status"]["dossier_writer"] == "completed"
    assert events[0].metadata["retrieval_events"][0]["selected_chunk_ids"] == ["chunk-1"]
    assert "chunk_text" not in events[0].metadata["retrieval_events"][0]
    assert events[0].metadata["tool_events"][0]["tool_name"] == "web_search"
    assert events[0].metadata["tool_status"] == {"company_researcher.web_search": "completed"}
    assert "raw_provider_payload" not in events[0].metadata["tool_events"][0]
    assert "output" not in events[0].metadata["tool_events"][0]
    assert "error_message" not in events[0].metadata["tool_events"][0]


@pytest.mark.asyncio
async def test_get_lead_recovers_snapshot_after_qualify() -> None:
    store = InMemoryLeadRunRepository()
    mock_graph = _make_graph_mock(_GRAPH_RESULT, next_nodes=("await_approval",))

    with (
        patch("saas_lead_agent.api.routes._graph", mock_graph),
        patch("saas_lead_agent.api.routes._lead_store", store),
    ):
        async with await _client() as client:
            qualify_resp = await client.post(
                "/api/qualify",
                json={"url": "https://acme.example.com"},
            )
            get_resp = await client.get("/api/leads/lead%3Aacme.example.com")

    assert qualify_resp.status_code == 200
    assert get_resp.status_code == 200
    qualified = qualify_resp.json()
    recovered = get_resp.json()
    assert recovered["thread_id"] == qualified["thread_id"]
    assert recovered["run_id"] == qualified["run_id"]
    assert recovered["company_profile"]["name"] == "Acme Corp"
    assert recovered["processing_metadata"]["run_id"] == qualified["run_id"]
    assert recovered["interrupted"] is True

    events = await store.list_events("lead:acme.example.com")
    assert [event.event_type for event in events] == ["qualify_completed"]
    assert events[0].metadata["status"] == "interrupted"
    assert events[0].metadata["total_tokens"] == 0
    assert events[0].metadata["estimated_cost_usd"] == 0.0
    assert events[0].metadata["timings_ms"]["graph"] >= 0

    artifacts = await store.get_artifacts_by_thread_id("lead:acme.example.com")
    assert artifacts is not None
    assert artifacts.lead.company_name == "Acme Corp"
    assert artifacts.lead.fit_score == 8
    assert artifacts.score_breakdown is not None
    assert artifacts.score_breakdown.score_confidence == "high"
    assert artifacts.outreach_draft is not None
    assert artifacts.outreach_draft.email_subject == "Quick question about Acme Corp"


@pytest.mark.asyncio
async def test_qualify_attaches_user_id_to_snapshot_and_lead_artifact() -> None:
    store = InMemoryLeadRunRepository()
    mock_graph = _make_graph_mock(_GRAPH_RESULT, next_nodes=("await_approval",))

    with (
        patch("saas_lead_agent.api.routes._graph", mock_graph),
        patch("saas_lead_agent.api.routes._lead_store", store),
    ):
        async with await _client() as client:
            resp = await client.post(
                "/api/qualify",
                json={"url": "https://acme.example.com"},
                headers={"X-OLA-User-ID": "user-1"},
            )

    snapshot = await store.get_by_thread_id("lead:acme.example.com")
    artifacts = await store.get_artifacts_by_thread_id("lead:acme.example.com")

    assert resp.status_code == 200
    assert "user_id" not in resp.json()
    assert snapshot is not None
    assert snapshot.result["user_id"] == "user-1"
    assert artifacts is not None
    assert artifacts.lead.user_id == "user-1"


@pytest.mark.asyncio
async def test_get_lead_returns_404_when_snapshot_missing() -> None:
    store = InMemoryLeadRunRepository()

    with patch("saas_lead_agent.api.routes._lead_store", store):
        async with await _client() as client:
            resp = await client.get("/api/leads/lead%3Amissing.example.com")

    assert resp.status_code == 404
    assert "No stored lead run found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_leads_returns_recent_summary_without_dossier_body() -> None:
    store = InMemoryLeadRunRepository()
    await store.save_snapshot(
        LeadRunSnapshot(
            run_id="run-old",
            thread_id="lead:old.example.com",
            domain="old.example.com",
            company_url="https://old.example.com",
            status="completed",
            result={
                "thread_id": "lead:old.example.com",
                "company_profile": {"name": "Old Co"},
                "email_body": "This should not appear in summary responses.",
            },
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    await store.save_snapshot(
        LeadRunSnapshot(
            run_id="run-new",
            thread_id="lead:new.example.com",
            domain="new.example.com",
            company_url="https://new.example.com",
            status="interrupted",
            result={
                "thread_id": "lead:new.example.com",
                "company_profile": {"name": "New Co"},
                "fit_score": 8,
                "fit_level": "high",
                "score_confidence": "high",
                "needs_human_review": False,
                "interrupted": True,
                "send_result": None,
                "processing_metadata": {
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "duration_seconds": 1.25,
                },
                "email_body": "This should not appear in summary responses.",
            },
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )

    with patch("saas_lead_agent.api.routes._lead_store", store):
        async with await _client() as client:
            resp = await client.get("/api/leads?limit=1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["request_id"]
    assert len(body["leads"]) == 1
    lead = body["leads"][0]
    assert lead["run_id"] == "run-new"
    assert lead["company_name"] == "New Co"
    assert lead["fit_score"] == 8
    assert lead["interrupted"] is True
    assert lead["duration_seconds"] == 1.25
    assert "email_body" not in lead


@pytest.mark.asyncio
async def test_list_leads_filters_snapshots_by_authenticated_owner() -> None:
    store = InMemoryLeadRunRepository()
    for thread_id, user_id in (
        ("lead:mine.example.com", "user-1"),
        ("lead:other.example.com", "user-2"),
        ("lead:legacy.example.com", None),
    ):
        await store.save_snapshot(
            LeadRunSnapshot(
                run_id=f"run:{thread_id}",
                thread_id=thread_id,
                domain=thread_id.removeprefix("lead:"),
                company_url=f"https://{thread_id.removeprefix('lead:')}",
                status="completed",
                result={
                    "user_id": user_id,
                    "company_profile": {"name": thread_id},
                },
            )
        )

    with patch("saas_lead_agent.api.routes._lead_store", store):
        async with await _client() as client:
            resp = await client.get("/api/leads", headers={"X-OLA-User-ID": "user-1"})

    assert resp.status_code == 200
    assert [lead["thread_id"] for lead in resp.json()["leads"]] == ["lead:mine.example.com"]


@pytest.mark.asyncio
async def test_get_lead_events_returns_sanitized_metadata() -> None:
    store = InMemoryLeadRunRepository()
    await store.save_snapshot(
        LeadRunSnapshot(
            run_id="run-1",
            thread_id="lead:acme.example.com",
            domain="acme.example.com",
            company_url="https://acme.example.com",
            status="completed",
            result={"thread_id": "lead:acme.example.com"},
        )
    )
    await store.record_event(
        RunEvent(
            run_id="run-1",
            thread_id="lead:acme.example.com",
            event_type="qualify_failed",
            request_id="req-1",
            metadata={
                "status": "failed",
                "error_type": "RuntimeError",
                "error": "raw provider message should not be returned",
                "raw_prompt": "do not return prompt text",
                "provider_payload": {"choices": ["raw model payload"]},
                "email_body": "raw outreach copy should not be returned here",
                "source_text": "raw scraped website text should not be returned here",
                "timings_ms": {"graph": 12.0},
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "provider_status": {"dossier_writer": "failed"},
                "retrieval_events": [
                    {
                        "event_id": "ret-1",
                        "retrieval_node": "retrieve_icp_context",
                        "query_text_hash": "abc1234567890def",
                        "selected_chunk_ids": ["chunk-1"],
                        "token_budget": 400,
                        "tokens_selected": 125,
                        "chunk_text": "raw retrieved text should not be returned",
                    }
                ],
                "tool_events": [
                    {
                        "tool_name": "web_search",
                        "category": "search",
                        "provider": "tavily",
                        "status": "failed",
                        "duration_ms": 4.25,
                        "error_kind": "provider",
                        "error_message": "raw provider error should not be returned",
                        "raw_provider_payload": {"results": ["raw provider payload"]},
                        "output": [{"title": "raw result should not be returned"}],
                    }
                ],
                "tool_status": {"company_researcher.web_search": "failed"},
            },
        )
    )

    with patch("saas_lead_agent.api.routes._lead_store", store):
        async with await _client() as client:
            resp = await client.get("/api/leads/lead%3Aacme.example.com/events")

    assert resp.status_code == 200
    body = resp.json()
    assert body["request_id"]
    assert body["thread_id"] == "lead:acme.example.com"
    assert body["events"][0]["event_type"] == "qualify_failed"
    metadata = body["events"][0]["metadata"]
    assert metadata["status"] == "failed"
    assert metadata["error_type"] == "RuntimeError"
    assert metadata["timings_ms"] == {"graph": 12.0}
    assert metadata["provider_status"] == {"dossier_writer": "failed"}
    assert metadata["retrieval_events"] == [
        {
            "event_id": "ret-1",
            "retrieval_node": "retrieve_icp_context",
            "query_text_hash": "abc1234567890def",
            "selected_chunk_ids": ["chunk-1"],
            "token_budget": 400,
            "tokens_selected": 125,
        }
    ]
    assert metadata["tool_events"] == [
        {
            "tool_name": "web_search",
            "category": "search",
            "provider": "tavily",
            "status": "failed",
            "duration_ms": 4.25,
            "error_kind": "provider",
        }
    ]
    assert metadata["tool_status"] == {"company_researcher.web_search": "failed"}
    assert "error" not in metadata
    assert "raw_prompt" not in metadata
    assert "provider_payload" not in metadata
    assert "email_body" not in metadata
    assert "source_text" not in metadata
    assert "chunk_text" not in metadata["retrieval_events"][0]
    assert "error_message" not in metadata["tool_events"][0]
    assert "raw_provider_payload" not in metadata["tool_events"][0]
    assert "output" not in metadata["tool_events"][0]


@pytest.mark.asyncio
async def test_get_lead_events_returns_404_when_snapshot_missing() -> None:
    store = InMemoryLeadRunRepository()

    with patch("saas_lead_agent.api.routes._lead_store", store):
        async with await _client() as client:
            resp = await client.get("/api/leads/lead%3Amissing.example.com/events")

    assert resp.status_code == 404
    assert "No stored lead run found" in resp.json()["detail"]


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
    assert state["run_id"]
    assert state["company_url"] == "https://acme.example.com"
    assert state["domain"] == "acme.example.com"
    assert state["icp_context"] is None
    assert state["company_profile"] is None
    assert state["fit_level"] is None
    assert state["score_breakdown"] is None
    assert state["score_confidence"] is None
    assert state["grounding_report"] is None
    assert state["outreach_quality"] is None
    assert state["retrieval_context"] is None
    assert state["retrieval_events"] == []
    assert state["tool_usage"] == []
    assert state["provider_usage"] == []
    assert state["processing_metadata"] is None
    assert state["errors"] == []

    config = call_args.kwargs["config"]
    assert config["configurable"]["thread_id"] == "lead:acme.example.com"
    assert config["metadata"]["thread_id"] == "lead:acme.example.com"
    assert config["metadata"]["request_id"]
    assert config["metadata"]["run_id"] == state["run_id"]


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

    resumed_result = {
        **_GRAPH_RESULT,
        "email_approved": True,
        "send_result": "sent",
        "delivery_idempotency_key": "delivery:test-key",
    }
    mock_graph = _make_graph_mock(resumed_result, next_nodes=())
    store = InMemoryLeadRunRepository()

    with (
        patch("saas_lead_agent.api.routes._graph", mock_graph),
        patch("saas_lead_agent.api.routes._lead_store", store),
    ):
        await store.save_snapshot(
            LeadRunSnapshot(
                run_id="run-existing",
                thread_id="lead:acme.example.com",
                domain="acme.example.com",
                company_url="https://acme.example.com",
                status="interrupted",
                result={**_GRAPH_RESULT, "run_id": "run-existing", "interrupted": True},
            )
        )
        async with await _client() as client:
            resp = await client.post("/api/leads/lead:acme.example.com/approve")

    assert resp.status_code == 200
    body = resp.json()
    assert body["request_id"]
    assert body["run_id"] == "run-existing"
    assert body["thread_id"] == "lead:acme.example.com"
    assert body["email_approved"] is True
    assert body["send_result"] == "sent"
    assert body["delivery_idempotency_key"] == "delivery:test-key"
    assert body["interrupted"] is False
    assert body["processing_metadata"]["run_id"] == "run-existing"
    assert body["processing_metadata"]["timings_ms"]["graph"] >= 0

    artifacts = await store.get_artifacts_by_thread_id("lead:acme.example.com")
    assert artifacts is not None
    assert artifacts.decision is not None
    assert artifacts.decision.decision == "approved"
    assert artifacts.delivery_event is not None
    assert artifacts.delivery_event.send_result == "sent"
    assert artifacts.delivery_event.delivery_idempotency_key == "delivery:test-key"

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
