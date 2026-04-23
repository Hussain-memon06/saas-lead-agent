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
        else:
            result[key] = val
    return result  # type: ignore[return-value]


_BASE: LeadState = {
    "company_url": "https://example.com",
    "domain": "example.com",
    "messages": [],
    "company_profile": None,
    "contact": None,
    "signals": None,
    "fit_score": None,
    "email_subject": None,
    "email_body": None,
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


def test_scalar_fields_overwrite() -> None:
    updated = _merge(
        _BASE,
        {"domain": "new.com", "company_profile": {"name": "Acme"}},
    )
    assert updated["domain"] == "new.com"
    assert updated["company_profile"] == {"name": "Acme"}
    assert updated["company_url"] == "https://example.com"  # untouched


def test_initial_state_is_valid() -> None:
    assert _BASE["company_url"] == "https://example.com"
    assert _BASE["company_profile"] is None
    assert _BASE["fit_score"] is None
    assert _BASE["email_subject"] is None
    assert _BASE["email_body"] is None
    assert _BASE["errors"] == []


def test_dossier_fields_overwrite() -> None:
    updated = _merge(
        _BASE,
        {"fit_score": 7, "email_subject": "Quick question", "email_body": "Hi Alice,"},
    )
    assert updated["fit_score"] == 7
    assert updated["email_subject"] == "Quick question"
    assert updated["email_body"] == "Hi Alice,"
    assert updated["company_url"] == "https://example.com"  # untouched
