"""Tests for the orchestrator supervisor node.

Strategy:
- _parse_orchestrator_output is a pure function — tested directly.
- orchestrator node is async — _get_orchestrator_agent is patched to return
  a MagicMock whose ainvoke is an AsyncMock; no real LLM or network calls.
- run_company_researcher / run_contact_finder / run_signal_detector tool
  wrappers are tested by patching the underlying agent functions.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas_lead_agent.agents.orchestrator import (
    _parse_orchestrator_output,
    orchestrator,
    run_company_researcher,
    run_contact_finder,
    run_signal_detector,
)
from saas_lead_agent.state import LeadState

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_BASE_STATE: LeadState = {
    "company_url": "https://acme.example.com",
    "domain": "acme.example.com",
    "messages": [],
    "company_profile": None,
    "contact": None,
    "signals": None,
    "errors": [],
}

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

_SIGNALS: list[dict[str, Any]] = []

_ORCHESTRATOR_OUTPUT: dict[str, Any] = {
    "company_profile": _PROFILE,
    "contact": _CONTACT,
    "signals": _SIGNALS,
}


def _make_agent_mock(content: str) -> MagicMock:
    from langchain_core.messages import AIMessage

    agent = MagicMock()
    agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content=content)]})
    return agent


# ---------------------------------------------------------------------------
# _parse_orchestrator_output
# ---------------------------------------------------------------------------


def test_parse_output_plain_json() -> None:
    raw = json.dumps(_ORCHESTRATOR_OUTPUT)
    result = _parse_orchestrator_output(raw)
    assert result["company_profile"]["name"] == "Acme Corp"
    assert result["contact"]["source"] == "stub"
    assert result["signals"] == []


def test_parse_output_markdown_fence() -> None:
    raw = f"```json\n{json.dumps(_ORCHESTRATOR_OUTPUT)}\n```"
    result = _parse_orchestrator_output(raw)
    assert result["company_profile"]["funding_stage"] == "Series A"


def test_parse_output_partial_keys() -> None:
    raw = json.dumps({"company_profile": _PROFILE})
    result = _parse_orchestrator_output(raw)
    assert "company_profile" in result
    assert "contact" not in result
    assert "signals" not in result


def test_parse_output_string_values_decoded() -> None:
    """Values that are JSON strings should be decoded to dicts/lists."""
    raw = json.dumps(
        {
            "company_profile": json.dumps(_PROFILE),
            "contact": json.dumps(_CONTACT),
            "signals": json.dumps(_SIGNALS),
        }
    )
    result = _parse_orchestrator_output(raw)
    assert isinstance(result["company_profile"], dict)
    assert result["company_profile"]["name"] == "Acme Corp"
    assert isinstance(result["signals"], list)


def test_parse_output_unwraps_nested_key() -> None:
    """Subagent may return {"company_profile": {...}} — unwrap one level."""
    raw = json.dumps({"company_profile": {"company_profile": _PROFILE}})
    result = _parse_orchestrator_output(raw)
    assert result["company_profile"]["name"] == "Acme Corp"


def test_parse_output_raises_on_invalid_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        _parse_orchestrator_output("not json {{{")


def test_parse_output_raises_on_non_dict() -> None:
    with pytest.raises(ValueError, match="Expected JSON object"):
        _parse_orchestrator_output("[1, 2, 3]")


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_company_researcher_calls_node() -> None:
    state_json = json.dumps(dict(_BASE_STATE, messages=[], errors=[]))

    with patch(
        "saas_lead_agent.agents.orchestrator.company_researcher",
        new=AsyncMock(return_value={"company_profile": _PROFILE}),
    ):
        raw = await run_company_researcher.ainvoke({"state_json": state_json})

    parsed = json.loads(raw)
    assert parsed["company_profile"]["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_run_contact_finder_calls_node() -> None:
    state_json = json.dumps(dict(_BASE_STATE, messages=[], errors=[]))

    with patch(
        "saas_lead_agent.agents.orchestrator.contact_finder",
        new=AsyncMock(return_value={"contact": _CONTACT}),
    ):
        raw = await run_contact_finder.ainvoke({"state_json": state_json})

    parsed = json.loads(raw)
    assert parsed["contact"]["source"] == "stub"


@pytest.mark.asyncio
async def test_run_signal_detector_calls_node() -> None:
    state_json = json.dumps(dict(_BASE_STATE, messages=[], errors=[]))

    with patch(
        "saas_lead_agent.agents.orchestrator.signal_detector",
        new=AsyncMock(return_value={"signals": []}),
    ):
        raw = await run_signal_detector.ainvoke({"state_json": state_json})

    parsed = json.loads(raw)
    assert parsed["signals"] == []


# ---------------------------------------------------------------------------
# orchestrator node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_happy_path() -> None:
    mock_agent = _make_agent_mock(json.dumps(_ORCHESTRATOR_OUTPUT))

    with patch(
        "saas_lead_agent.agents.orchestrator._get_orchestrator_agent",
        return_value=mock_agent,
    ):
        result = await orchestrator(_BASE_STATE)

    assert result["company_profile"]["name"] == "Acme Corp"
    assert result["contact"]["source"] == "stub"
    assert result["signals"] == []
    assert "errors" not in result


@pytest.mark.asyncio
async def test_orchestrator_markdown_response() -> None:
    content = f"```json\n{json.dumps(_ORCHESTRATOR_OUTPUT)}\n```"
    mock_agent = _make_agent_mock(content)

    with patch(
        "saas_lead_agent.agents.orchestrator._get_orchestrator_agent",
        return_value=mock_agent,
    ):
        result = await orchestrator(_BASE_STATE)

    assert result["company_profile"]["funding_stage"] == "Series A"


@pytest.mark.asyncio
async def test_orchestrator_parse_error_returns_errors() -> None:
    mock_agent = _make_agent_mock("Sorry, I cannot do that.")

    with patch(
        "saas_lead_agent.agents.orchestrator._get_orchestrator_agent",
        return_value=mock_agent,
    ):
        result = await orchestrator(_BASE_STATE)

    assert "errors" in result
    assert "output parse error" in result["errors"][0]


@pytest.mark.asyncio
async def test_orchestrator_agent_exception_returns_errors() -> None:
    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(side_effect=RuntimeError("quota exceeded"))

    with patch(
        "saas_lead_agent.agents.orchestrator._get_orchestrator_agent",
        return_value=mock_agent,
    ):
        result = await orchestrator(_BASE_STATE)

    assert "errors" in result
    assert "agent invocation failed" in result["errors"][0]
    assert "quota exceeded" in result["errors"][0]


@pytest.mark.asyncio
async def test_orchestrator_empty_messages_returns_errors() -> None:
    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value={"messages": []})

    with patch(
        "saas_lead_agent.agents.orchestrator._get_orchestrator_agent",
        return_value=mock_agent,
    ):
        result = await orchestrator(_BASE_STATE)

    assert "errors" in result
    assert "no messages" in result["errors"][0]


@pytest.mark.asyncio
async def test_orchestrator_passes_url_and_domain_in_prompt() -> None:
    mock_agent = _make_agent_mock(json.dumps(_ORCHESTRATOR_OUTPUT))

    with patch(
        "saas_lead_agent.agents.orchestrator._get_orchestrator_agent",
        return_value=mock_agent,
    ):
        await orchestrator(_BASE_STATE)

    call_args = mock_agent.ainvoke.call_args
    messages = call_args[0][0]["messages"]
    content = messages[0].content
    assert "https://acme.example.com" in content
    assert "acme.example.com" in content
