"""Tests for app-owned lead run persistence repositories."""

import pytest

from saas_lead_agent.persistence import (
    InMemoryLeadRunRepository,
    LeadRunSnapshot,
    RunEvent,
    build_lead_artifacts,
)

pytestmark = pytest.mark.asyncio


def _snapshot(result: dict[str, object] | None = None) -> LeadRunSnapshot:
    return LeadRunSnapshot(
        run_id="run-1",
        thread_id="lead:acme.example.com",
        domain="acme.example.com",
        company_url="https://acme.example.com",
        status="completed",
        request_id="req-1",
        result=result
        or {
            "thread_id": "lead:acme.example.com",
            "company_profile": {
                "name": "Acme Corp",
                "tagline": "Revenue automation",
                "hq": "Austin, USA",
                "employees_estimate": "50-200",
                "funding_stage": "Series A",
                "sources": ["https://acme.example.com/about"],
            },
            "contact": {
                "name": "Alice Smith",
                "title": "VP Sales",
                "email": "alice@acme.example.com",
                "linkedin": "https://linkedin.com/in/alice",
                "confidence": 92,
                "source": "hunter",
            },
            "signals": [
                {
                    "signal_type": "funding",
                    "date": "2026-01-15",
                    "source": "https://acme.example.com/funding",
                    "details": "Acme announced Series A funding.",
                }
            ],
            "fit_score": 8,
            "fit_level": "high",
            "score_breakdown": {"baseline": 2.5, "signal_strength": 1.5},
            "score_confidence": "high",
            "score_explanation": "Strong fit with sourced evidence.",
            "needs_human_review": False,
            "score_reasons": ["verified funding signal"],
            "score_uncertainty": [],
            "grounding_report": {
                "source_urls": ["https://acme.example.com/funding"],
                "evidence": {
                    "items": [
                        {
                            "claim": "Acme announced Series A funding.",
                            "source_text": "Series A announcement",
                            "source_location": "press",
                            "source_url": "https://acme.example.com/funding",
                            "confidence": "high",
                        }
                    ]
                },
            },
            "outreach_quality": {"quality_score": 94, "passed": True},
            "email_subject": "Quick question about Acme Corp",
            "email_body": "Hi Alice, congrats on the Series A.",
            "email_approved": True,
            "send_result": "sent",
            "message_id": "msg-123",
            "sent_at": "2026-01-16T00:00:00Z",
        },
    )


async def test_build_lead_artifacts_extracts_current_state_records() -> None:
    artifacts = build_lead_artifacts(_snapshot())

    assert artifacts.lead.company_name == "Acme Corp"
    assert artifacts.lead.fit_score == 8
    assert artifacts.lead.score_confidence == "high"
    assert artifacts.contacts[0].email == "alice@acme.example.com"
    assert artifacts.company_signals[0].signal_type == "funding"
    assert artifacts.score_breakdown is not None
    assert artifacts.score_breakdown.score_breakdown["signal_strength"] == 1.5
    assert artifacts.outreach_draft is not None
    assert artifacts.outreach_draft.email_subject == "Quick question about Acme Corp"
    assert artifacts.decision is not None
    assert artifacts.decision.decision == "approved"
    assert artifacts.delivery_event is not None
    assert artifacts.delivery_event.message_id == "msg-123"
    assert {source.source_type for source in artifacts.sources} == {
        "company_profile",
        "company_signal",
        "grounding_report",
        "evidence",
    }


async def test_in_memory_repository_saves_and_updates_snapshot() -> None:
    repo = InMemoryLeadRunRepository()
    first = LeadRunSnapshot(
        run_id="run-1",
        thread_id="lead:acme.example.com",
        domain="acme.example.com",
        company_url="https://acme.example.com",
        status="interrupted",
        request_id="req-1",
        result={"thread_id": "lead:acme.example.com", "interrupted": True},
    )
    saved = await repo.save_snapshot(first)

    updated = await repo.save_snapshot(
        LeadRunSnapshot(
            run_id="run-1",
            thread_id="lead:acme.example.com",
            domain="acme.example.com",
            company_url="https://acme.example.com",
            status="completed",
            request_id="req-2",
            result={
                "thread_id": "lead:acme.example.com",
                "send_result": "rejected",
                "interrupted": False,
            },
        )
    )

    recovered = await repo.get_by_thread_id("lead:acme.example.com")

    assert recovered == updated
    assert recovered is not None
    assert recovered.created_at == saved.created_at
    assert recovered.updated_at >= saved.updated_at
    assert recovered.status == "completed"
    assert recovered.result["send_result"] == "rejected"


async def test_in_memory_repository_saves_artifacts_with_snapshot() -> None:
    repo = InMemoryLeadRunRepository()

    await repo.save_snapshot(_snapshot())
    artifacts = await repo.get_artifacts_by_thread_id("lead:acme.example.com")

    assert artifacts is not None
    assert artifacts.lead.company_name == "Acme Corp"
    assert artifacts.contacts[0].name == "Alice Smith"
    assert artifacts.company_signals[0].details == "Acme announced Series A funding."
    assert artifacts.delivery_event is not None
    assert artifacts.delivery_event.send_result == "sent"

    await repo.save_snapshot(
        _snapshot(
            {
                "thread_id": "lead:acme.example.com",
                "company_profile": {"name": "Acme Corp", "sources": []},
                "contact": None,
                "signals": [],
                "fit_score": 4,
                "fit_level": "low",
            }
        )
    )
    updated = await repo.get_artifacts_by_thread_id("lead:acme.example.com")

    assert updated is not None
    assert updated.lead.fit_score == 4
    assert updated.contacts == []
    assert updated.company_signals == []
    assert updated.delivery_event is None


async def test_in_memory_repository_records_run_events() -> None:
    repo = InMemoryLeadRunRepository()

    await repo.record_event(
        RunEvent(
            run_id="run-1",
            thread_id="lead:acme.example.com",
            event_type="qualify_completed",
            request_id="req-1",
            metadata={"status": "interrupted"},
        )
    )

    events = await repo.list_events("lead:acme.example.com")

    assert len(events) == 1
    assert events[0].event_type == "qualify_completed"
    assert events[0].metadata == {"status": "interrupted"}
