import operator

from langchain_core.messages import HumanMessage

from saas_lead_agent.state import LeadState


def _merge(a: LeadState, b: dict) -> LeadState:  # type: ignore[return]
    """Apply reducer logic field-by-field, mirroring LangGraph behaviour."""
    from langgraph.graph.message import add_messages

    result = dict(a)
    for key, val in b.items():
        if key == "messages":
            result["messages"] = add_messages(a.get("messages", []), val)
        elif key == "errors":
            result["errors"] = operator.add(a.get("errors", []), val)
        elif key in {"provider_usage", "retrieval_events", "tool_usage"}:
            result[key] = operator.add(a.get(key, []), val)
        else:
            result[key] = val
    return result  # type: ignore[return-value]


_BASE: LeadState = {
    "run_id": "run-test",
    "company_url": "https://example.com",
    "domain": "example.com",
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


def test_messages_reducer_appends() -> None:
    state: LeadState = {**_BASE, "messages": [HumanMessage(content="first")]}
    updated = _merge(state, {"messages": [HumanMessage(content="second")]})
    assert len(updated["messages"]) == 2
    assert updated["messages"][1].content == "second"


def test_errors_reducer_concatenates() -> None:
    state: LeadState = {**_BASE, "errors": ["err1"]}
    updated = _merge(state, {"errors": ["err2", "err3"]})
    assert updated["errors"] == ["err1", "err2", "err3"]


def test_provider_usage_reducer_concatenates() -> None:
    state: LeadState = {
        **_BASE,
        "provider_usage": [{"node": "company_researcher", "status": "completed"}],
    }
    updated = _merge(
        state,
        {"provider_usage": [{"node": "dossier_writer", "status": "completed"}]},
    )

    assert updated["provider_usage"] == [
        {"node": "company_researcher", "status": "completed"},
        {"node": "dossier_writer", "status": "completed"},
    ]


def test_retrieval_events_reducer_concatenates() -> None:
    state: LeadState = {
        **_BASE,
        "retrieval_events": [{"retrieval_node": "retrieve_icp_context"}],
    }
    updated = _merge(
        state,
        {"retrieval_events": [{"retrieval_node": "retrieve_similar_leads"}]},
    )

    assert updated["retrieval_events"] == [
        {"retrieval_node": "retrieve_icp_context"},
        {"retrieval_node": "retrieve_similar_leads"},
    ]


def test_tool_usage_reducer_concatenates() -> None:
    state: LeadState = {
        **_BASE,
        "tool_usage": [{"node": "company_researcher", "tool_name": "web_search"}],
    }
    updated = _merge(
        state,
        {"tool_usage": [{"node": "signal_detector", "tool_name": "web_search"}]},
    )

    assert updated["tool_usage"] == [
        {"node": "company_researcher", "tool_name": "web_search"},
        {"node": "signal_detector", "tool_name": "web_search"},
    ]


def test_scalar_fields_overwrite() -> None:
    updated = _merge(
        _BASE,
        {"domain": "new.com", "company_profile": {"name": "Acme"}},
    )
    assert updated["domain"] == "new.com"
    assert updated["company_profile"] == {"name": "Acme"}
    assert updated["company_url"] == "https://example.com"  # untouched


def test_initial_state_is_valid() -> None:
    assert _BASE["run_id"] == "run-test"
    assert _BASE["company_url"] == "https://example.com"
    assert _BASE["company_profile"] is None
    assert _BASE["fit_score"] is None
    assert _BASE["fit_level"] is None
    assert _BASE["score_breakdown"] is None
    assert _BASE["score_confidence"] is None
    assert _BASE["grounding_report"] is None
    assert _BASE["outreach_quality"] is None
    assert _BASE["retrieval_context"] is None
    assert _BASE["retrieval_events"] == []
    assert _BASE["tool_usage"] == []
    assert _BASE["provider_usage"] == []
    assert _BASE["processing_metadata"] is None
    assert _BASE["email_subject"] is None
    assert _BASE["email_body"] is None
    assert _BASE["email_approved"] is None
    assert _BASE["send_result"] is None
    assert _BASE["delivery_idempotency_key"] is None
    assert _BASE["errors"] == []


def test_dossier_fields_overwrite() -> None:
    updated = _merge(
        _BASE,
        {
            "fit_score": 7,
            "fit_level": "medium",
            "score_breakdown": {"baseline": 2.5},
            "score_confidence": "medium",
            "grounding_report": {"is_sufficient": True},
            "outreach_quality": {"passed": True},
            "email_subject": "Quick question",
            "email_body": "Hi Alice,",
        },
    )
    assert updated["fit_score"] == 7
    assert updated["fit_level"] == "medium"
    assert updated["score_breakdown"] == {"baseline": 2.5}
    assert updated["score_confidence"] == "medium"
    assert updated["grounding_report"] == {"is_sufficient": True}
    assert updated["outreach_quality"] == {"passed": True}
    assert updated["email_subject"] == "Quick question"
    assert updated["email_body"] == "Hi Alice,"
    assert updated["company_url"] == "https://example.com"  # untouched


def test_hitl_fields_overwrite() -> None:
    updated = _merge(
        _BASE,
        {"email_approved": True, "send_result": "sent"},
    )
    assert updated["email_approved"] is True
    assert updated["send_result"] == "sent"


def test_delivery_fields_overwrite() -> None:
    updated = _merge(
        _BASE,
        {"message_id": "msg-abc-123", "sent_at": "2026-04-25T12:00:00+00:00"},
    )
    assert updated["message_id"] == "msg-abc-123"
    assert updated["sent_at"] == "2026-04-25T12:00:00+00:00"


def test_processing_metadata_overwrites() -> None:
    metadata = {
        "run_id": "run-test",
        "thread_id": "lead:example.com",
        "timings_ms": {"graph": 1.0},
    }
    updated = _merge(_BASE, {"processing_metadata": metadata})

    assert updated["processing_metadata"] == metadata
