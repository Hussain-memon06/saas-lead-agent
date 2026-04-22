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


def test_messages_reducer_appends() -> None:
    state: LeadState = {
        "company_url": "https://example.com",
        "domain": "example.com",
        "messages": [HumanMessage(content="first")],
        "company_profile": None,
        "errors": [],
    }
    updated = _merge(state, {"messages": [HumanMessage(content="second")]})
    assert len(updated["messages"]) == 2
    assert updated["messages"][1].content == "second"


def test_errors_reducer_concatenates() -> None:
    state: LeadState = {
        "company_url": "https://example.com",
        "domain": "example.com",
        "messages": [],
        "company_profile": None,
        "errors": ["err1"],
    }
    updated = _merge(state, {"errors": ["err2", "err3"]})
    assert updated["errors"] == ["err1", "err2", "err3"]


def test_scalar_fields_overwrite() -> None:
    state: LeadState = {
        "company_url": "https://old.com",
        "domain": "old.com",
        "messages": [],
        "company_profile": None,
        "errors": [],
    }
    updated = _merge(state, {"domain": "new.com", "company_profile": {"name": "Acme"}})
    assert updated["domain"] == "new.com"
    assert updated["company_profile"] == {"name": "Acme"}
    assert updated["company_url"] == "https://old.com"  # untouched


def test_initial_state_is_valid() -> None:
    state: LeadState = {
        "company_url": "https://example.com",
        "domain": "example.com",
        "messages": [],
        "company_profile": None,
        "errors": [],
    }
    assert state["company_url"] == "https://example.com"
    assert state["company_profile"] is None
    assert state["errors"] == []
