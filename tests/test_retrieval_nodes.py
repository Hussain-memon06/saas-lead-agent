"""Tests for provider-free Phase 4 retrieval graph nodes."""

from typing import Any

import pytest

from saas_lead_agent.agents.retrieval import (
    retrieve_icp_context,
    retrieve_outreach_examples,
    retrieve_similar_leads,
)
from saas_lead_agent.state import LeadState

_BASE_STATE: LeadState = {
    "run_id": "run-test",
    "company_url": "https://acme.example.com",
    "domain": "acme.example.com",
    "icp_context": None,
    "messages": [],
    "company_profile": None,
    "contact": None,
    "signals": None,
    "fit_score": None,
    "fit_level": None,
    "score_breakdown": None,
    "score_confidence": None,
    "score_explanation": None,
    "needs_human_review": None,
    "score_reasons": None,
    "score_uncertainty": None,
    "grounding_report": None,
    "outreach_quality": None,
    "retrieval_context": None,
    "retrieval_events": [],
    "tool_usage": [],
    "provider_usage": [],
    "processing_metadata": None,
    "email_subject": None,
    "email_body": None,
    "email_approved": None,
    "send_result": None,
    "delivery_idempotency_key": None,
    "message_id": None,
    "sent_at": None,
    "errors": [],
}

_ICP: dict[str, Any] = {
    "seller_name": "Outbound Labs",
    "offering": "AI outbound research automation",
    "target_industries": ["B2B SaaS", "Fintech"],
    "target_stages": ["Series A", "Series B"],
    "must_have_signals": ["Hiring sales leaders", "Recent funding"],
    "red_flags": ["Consumer app"],
    "value_proposition": "Find high-fit accounts with sourced evidence.",
}


@pytest.mark.asyncio
async def test_retrieve_icp_context_builds_context_and_sanitized_event() -> None:
    state: LeadState = {**_BASE_STATE, "icp_context": _ICP}

    result = await retrieve_icp_context(state)

    assert "errors" not in result
    context = result["retrieval_context"]["icp"]
    assert context["status"] == "completed"
    assert {chunk["document_type"] for chunk in context["trusted_chunks"]} == {
        "icp",
        "offer",
    }
    assert {chunk["trust_label"] for chunk in context["trusted_chunks"]} == {"trusted_user"}
    assert context["token_count"] > 0

    events = result["retrieval_events"]
    assert len(events) == 1
    event = events[0]
    assert event["retrieval_node"] == "retrieve_icp_context"
    assert event["thread_id"] == "lead:acme.example.com"
    assert event["top_k"] == 3
    assert event["selected_chunk_ids"] == [chunk["chunk_id"] for chunk in context["trusted_chunks"]]
    assert event["query_metadata"]["status"] == "completed"
    assert event["filters"] == {
        "document_types": ["icp", "offer"],
        "trust_labels": ["trusted_user"],
        "mode": "request_icp_transient",
    }
    assert "Outbound Labs" not in str(event)
    assert "Find high-fit accounts" not in str(event)


@pytest.mark.asyncio
async def test_retrieve_icp_context_skips_without_icp() -> None:
    result = await retrieve_icp_context(_BASE_STATE)

    context = result["retrieval_context"]["icp"]
    assert context["status"] == "skipped"
    assert context["reason"] == "missing_icp_context"
    assert context["trusted_chunks"] == []
    event = result["retrieval_events"][0]
    assert event["selected_chunk_ids"] == []
    assert event["query_metadata"] == {
        "query_kind": "icp_context",
        "status": "skipped",
        "reason": "missing_icp_context",
    }


@pytest.mark.asyncio
async def test_retrieve_similar_leads_records_no_corpus_event_and_preserves_context() -> None:
    state: LeadState = {
        **_BASE_STATE,
        "retrieval_context": {"icp": {"status": "completed"}},
        "company_profile": {
            "name": "Acme Corp",
            "tagline": "Revenue automation for SaaS teams",
            "funding_stage": "Series A",
            "products": ["Outbound AI"],
        },
        "signals": [
            {
                "signal_type": "hiring",
                "details": "Hiring SDR managers",
                "source": "https://acme.example.com/careers",
            }
        ],
    }

    result = await retrieve_similar_leads(state)

    assert result["retrieval_context"]["icp"] == {"status": "completed"}
    context = result["retrieval_context"]["similar_leads"]
    assert context["status"] == "skipped"
    assert context["reason"] == "no_lead_example_corpus"
    assert context["trusted_chunks"] == []

    event = result["retrieval_events"][0]
    assert event["retrieval_node"] == "retrieve_similar_leads"
    assert event["selected_chunk_ids"] == []
    assert event["filters"] == {
        "document_types": ["lead_example", "prior_dossier"],
        "trust_labels": ["trusted_user", "trusted_generated"],
        "mode": "no_provider_no_corpus",
    }
    assert event["query_metadata"]["reason"] == "no_lead_example_corpus"
    assert "Acme Corp" not in str(event)
    assert "Hiring SDR managers" not in str(event)


@pytest.mark.asyncio
async def test_retrieve_outreach_examples_records_no_corpus_event() -> None:
    state: LeadState = {
        **_BASE_STATE,
        "retrieval_context": {
            "icp": {
                "status": "completed",
                "trusted_chunks": [
                    {
                        "chunk_id": "chunk-icp-1",
                        "document_type": "icp",
                        "trust_label": "trusted_user",
                    }
                ],
            }
        },
        "company_profile": {
            "name": "Acme Corp",
            "tagline": "Revenue automation for SaaS teams",
        },
        "contact": {"title": "VP Sales", "source": "hunter"},
        "signals": [
            {
                "signal_type": "funding",
                "details": "Raised a Series A",
                "source": "https://acme.example.com/news",
            }
        ],
    }

    result = await retrieve_outreach_examples(state)

    assert result["retrieval_context"]["icp"]["status"] == "completed"
    context = result["retrieval_context"]["outreach_examples"]
    assert context["status"] == "skipped"
    assert context["reason"] == "no_outreach_example_corpus"
    assert context["trusted_chunks"] == []

    event = result["retrieval_events"][0]
    assert event["retrieval_node"] == "retrieve_outreach_examples"
    assert event["selected_chunk_ids"] == []
    assert event["filters"] == {
        "document_types": ["outreach_example"],
        "trust_labels": ["trusted_user", "trusted_generated"],
        "mode": "no_provider_no_corpus",
    }
    assert event["query_metadata"]["reason"] == "no_outreach_example_corpus"
    assert "VP Sales" not in str(event)
    assert "Raised a Series A" not in str(event)
