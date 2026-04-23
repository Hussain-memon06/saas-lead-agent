"""Tests for agent nodes: company_researcher, contact_finder, signal_detector.

Strategy:
- _extract_json / _extract_json_list are pure functions — tested directly.
- Async nodes patch their _get_*_agent singleton with an AsyncMock so no
  real LLM or network calls occur.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas_lead_agent.agents.company_researcher import company_researcher
from saas_lead_agent.agents.contact_finder import contact_finder
from saas_lead_agent.agents.signal_detector import signal_detector
from saas_lead_agent.state import LeadState
from saas_lead_agent.utils import _extract_json, _extract_json_list

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PROFILE: dict[str, Any] = {
    "name": "Acme Corp",
    "tagline": "Anvils for every occasion",
    "hq": "Tucson, USA",
    "employees_estimate": "50-200",
    "funding_stage": "Series A",
    "products": ["Heavy Anvil", "Rocket Skates"],
    "notable_customers": ["Wile E. Coyote"],
}

_BASE_STATE: LeadState = {
    "company_url": "https://acme.example.com",
    "domain": "acme.example.com",
    "messages": [],
    "company_profile": None,
    "contact": None,
    "signals": None,
    "errors": [],
}

_CONTACT: dict[str, Any] = {
    "name": "Alice Smith",
    "title": "CEO",
    "email": "alice@acme.example.com",
    "linkedin": "https://linkedin.com/in/alice-smith",
    "confidence": 92,
    "source": "hunter",
}

_NULL_CONTACT: dict[str, Any] = {
    "name": None,
    "title": None,
    "email": None,
    "linkedin": None,
    "confidence": None,
    "source": "hunter",
}


def _make_agent_mock(content: str) -> MagicMock:
    """Return a mock agent whose ainvoke resolves to a message list with content."""
    from langchain_core.messages import AIMessage

    agent = MagicMock()
    agent.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content=content)]}
    )
    return agent


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------


def test_extract_json_plain() -> None:
    raw = json.dumps(_PROFILE)
    result = _extract_json(raw)
    assert result["name"] == "Acme Corp"
    assert result["funding_stage"] == "Series A"


def test_extract_json_markdown_json_fence() -> None:
    raw = f"```json\n{json.dumps(_PROFILE)}\n```"
    result = _extract_json(raw)
    assert result["name"] == "Acme Corp"


def test_extract_json_plain_code_fence() -> None:
    raw = f"```\n{json.dumps(_PROFILE)}\n```"
    result = _extract_json(raw)
    assert result["products"] == ["Heavy Anvil", "Rocket Skates"]


def test_extract_json_strips_whitespace() -> None:
    raw = f"  \n  {json.dumps(_PROFILE)}  \n  "
    result = _extract_json(raw)
    assert result["hq"] == "Tucson, USA"


def test_extract_json_raises_on_invalid_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        _extract_json("not valid json {{{")


def test_extract_json_raises_on_non_dict() -> None:
    with pytest.raises(ValueError, match="Expected JSON object"):
        _extract_json("[1, 2, 3]")


# ---------------------------------------------------------------------------
# _extract_json_list
# ---------------------------------------------------------------------------

_SIGNALS: list[dict[str, Any]] = [
    {
        "signal_type": "funding",
        "date": "2024-03",
        "source": "https://techcrunch.com/acme-series-a",
        "details": "Acme Corp raised $10M Series A",
    },
    {
        "signal_type": "hiring",
        "date": None,
        "source": "https://linkedin.com/jobs/acme",
        "details": "20+ open engineering roles posted",
    },
]


def test_extract_json_list_plain() -> None:
    result = _extract_json_list(json.dumps(_SIGNALS))
    assert len(result) == 2
    assert result[0]["signal_type"] == "funding"
    assert result[1]["signal_type"] == "hiring"


def test_extract_json_list_fenced() -> None:
    raw = f"```json\n{json.dumps(_SIGNALS)}\n```"
    result = _extract_json_list(raw)
    assert result[0]["details"] == "Acme Corp raised $10M Series A"


def test_extract_json_list_empty_array_is_valid() -> None:
    result = _extract_json_list("[]")
    assert result == []


def test_extract_json_list_raises_on_dict() -> None:
    with pytest.raises(ValueError, match="Expected JSON array"):
        _extract_json_list('{"signal_type": "funding"}')


def test_extract_json_list_raises_on_non_dict_elements() -> None:
    with pytest.raises(ValueError, match="Expected array of objects"):
        _extract_json_list('["funding", "hiring"]')


# ---------------------------------------------------------------------------
# company_researcher node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_company_researcher_happy_path() -> None:
    mock_agent = _make_agent_mock(json.dumps(_PROFILE))

    with patch(
        "saas_lead_agent.agents.company_researcher._get_researcher_agent",
        return_value=mock_agent,
    ):
        result = await company_researcher(_BASE_STATE)

    assert "company_profile" in result
    profile = result["company_profile"]
    assert profile["name"] == "Acme Corp"
    assert profile["funding_stage"] == "Series A"
    assert "errors" not in result


@pytest.mark.asyncio
async def test_company_researcher_markdown_response() -> None:
    content = f"```json\n{json.dumps(_PROFILE)}\n```"
    mock_agent = _make_agent_mock(content)

    with patch(
        "saas_lead_agent.agents.company_researcher._get_researcher_agent",
        return_value=mock_agent,
    ):
        result = await company_researcher(_BASE_STATE)

    assert result.get("company_profile", {}).get("name") == "Acme Corp"


@pytest.mark.asyncio
async def test_company_researcher_json_parse_error() -> None:
    mock_agent = _make_agent_mock("Sorry, I cannot research that company.")

    with patch(
        "saas_lead_agent.agents.company_researcher._get_researcher_agent",
        return_value=mock_agent,
    ):
        result = await company_researcher(_BASE_STATE)

    assert "errors" in result
    assert len(result["errors"]) == 1
    assert "JSON parse error" in result["errors"][0]
    assert "company_profile" not in result


@pytest.mark.asyncio
async def test_company_researcher_agent_exception() -> None:
    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(side_effect=RuntimeError("LLM quota exceeded"))

    with patch(
        "saas_lead_agent.agents.company_researcher._get_researcher_agent",
        return_value=mock_agent,
    ):
        result = await company_researcher(_BASE_STATE)

    assert "errors" in result
    assert "agent invocation failed" in result["errors"][0]
    assert "LLM quota exceeded" in result["errors"][0]


@pytest.mark.asyncio
async def test_company_researcher_empty_messages() -> None:
    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value={"messages": []})

    with patch(
        "saas_lead_agent.agents.company_researcher._get_researcher_agent",
        return_value=mock_agent,
    ):
        result = await company_researcher(_BASE_STATE)

    assert "errors" in result
    assert "no messages" in result["errors"][0]


@pytest.mark.asyncio
async def test_company_researcher_passes_url_in_prompt() -> None:
    mock_agent = _make_agent_mock(json.dumps(_PROFILE))

    with patch(
        "saas_lead_agent.agents.company_researcher._get_researcher_agent",
        return_value=mock_agent,
    ):
        await company_researcher(_BASE_STATE)

    call_args = mock_agent.ainvoke.call_args
    messages = call_args[0][0]["messages"]
    assert any("https://acme.example.com" in m.content for m in messages)


# ---------------------------------------------------------------------------
# contact_finder node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contact_finder_happy_path() -> None:
    mock_agent = _make_agent_mock(json.dumps(_CONTACT))

    with patch(
        "saas_lead_agent.agents.contact_finder._get_contact_finder_agent",
        return_value=mock_agent,
    ):
        result = await contact_finder(_BASE_STATE)

    assert "contact" in result
    assert result["contact"]["name"] == "Alice Smith"
    assert result["contact"]["email"] == "alice@acme.example.com"
    assert result["contact"]["source"] == "hunter"
    assert "errors" not in result


@pytest.mark.asyncio
async def test_contact_finder_null_fields() -> None:
    mock_agent = _make_agent_mock(json.dumps(_NULL_CONTACT))

    with patch(
        "saas_lead_agent.agents.contact_finder._get_contact_finder_agent",
        return_value=mock_agent,
    ):
        result = await contact_finder(_BASE_STATE)

    assert "contact" in result
    assert result["contact"]["name"] is None
    assert result["contact"]["source"] == "hunter"
    assert "errors" not in result


@pytest.mark.asyncio
async def test_contact_finder_markdown_response() -> None:
    content = f"```json\n{json.dumps(_CONTACT)}\n```"
    mock_agent = _make_agent_mock(content)

    with patch(
        "saas_lead_agent.agents.contact_finder._get_contact_finder_agent",
        return_value=mock_agent,
    ):
        result = await contact_finder(_BASE_STATE)

    assert result.get("contact", {}).get("name") == "Alice Smith"


@pytest.mark.asyncio
async def test_contact_finder_json_parse_error() -> None:
    mock_agent = _make_agent_mock("Sorry, I could not find a contact.")

    with patch(
        "saas_lead_agent.agents.contact_finder._get_contact_finder_agent",
        return_value=mock_agent,
    ):
        result = await contact_finder(_BASE_STATE)

    assert "errors" in result
    assert "JSON parse error" in result["errors"][0]
    assert "contact" not in result


@pytest.mark.asyncio
async def test_contact_finder_agent_exception() -> None:
    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(side_effect=RuntimeError("LLM quota exceeded"))

    with patch(
        "saas_lead_agent.agents.contact_finder._get_contact_finder_agent",
        return_value=mock_agent,
    ):
        result = await contact_finder(_BASE_STATE)

    assert "errors" in result
    assert "agent invocation failed" in result["errors"][0]
    assert "LLM quota exceeded" in result["errors"][0]


@pytest.mark.asyncio
async def test_contact_finder_empty_messages() -> None:
    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value={"messages": []})

    with patch(
        "saas_lead_agent.agents.contact_finder._get_contact_finder_agent",
        return_value=mock_agent,
    ):
        result = await contact_finder(_BASE_STATE)

    assert "errors" in result
    assert "no messages" in result["errors"][0]


@pytest.mark.asyncio
async def test_contact_finder_passes_domain_in_prompt() -> None:
    mock_agent = _make_agent_mock(json.dumps(_CONTACT))

    with patch(
        "saas_lead_agent.agents.contact_finder._get_contact_finder_agent",
        return_value=mock_agent,
    ):
        await contact_finder(_BASE_STATE)

    call_args = mock_agent.ainvoke.call_args
    messages = call_args[0][0]["messages"]
    assert any("acme.example.com" in m.content for m in messages)


# ---------------------------------------------------------------------------
# signal_detector node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signal_detector_happy_path() -> None:
    mock_agent = _make_agent_mock(json.dumps(_SIGNALS))

    with patch(
        "saas_lead_agent.agents.signal_detector._get_signal_detector_agent",
        return_value=mock_agent,
    ):
        result = await signal_detector(_BASE_STATE)

    assert "signals" in result
    assert len(result["signals"]) == 2
    assert result["signals"][0]["signal_type"] == "funding"
    assert result["signals"][1]["signal_type"] == "hiring"
    assert "errors" not in result


@pytest.mark.asyncio
async def test_signal_detector_empty_array() -> None:
    mock_agent = _make_agent_mock("[]")

    with patch(
        "saas_lead_agent.agents.signal_detector._get_signal_detector_agent",
        return_value=mock_agent,
    ):
        result = await signal_detector(_BASE_STATE)

    assert "signals" in result
    assert result["signals"] == []
    assert "errors" not in result


@pytest.mark.asyncio
async def test_signal_detector_markdown_response() -> None:
    content = f"```json\n{json.dumps(_SIGNALS)}\n```"
    mock_agent = _make_agent_mock(content)

    with patch(
        "saas_lead_agent.agents.signal_detector._get_signal_detector_agent",
        return_value=mock_agent,
    ):
        result = await signal_detector(_BASE_STATE)

    assert result.get("signals", [])[0]["signal_type"] == "funding"


@pytest.mark.asyncio
async def test_signal_detector_json_parse_error() -> None:
    mock_agent = _make_agent_mock("No signals found for this company.")

    with patch(
        "saas_lead_agent.agents.signal_detector._get_signal_detector_agent",
        return_value=mock_agent,
    ):
        result = await signal_detector(_BASE_STATE)

    assert "errors" in result
    assert "JSON parse error" in result["errors"][0]
    assert "signals" not in result


@pytest.mark.asyncio
async def test_signal_detector_agent_exception() -> None:
    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(side_effect=RuntimeError("LLM quota exceeded"))

    with patch(
        "saas_lead_agent.agents.signal_detector._get_signal_detector_agent",
        return_value=mock_agent,
    ):
        result = await signal_detector(_BASE_STATE)

    assert "errors" in result
    assert "agent invocation failed" in result["errors"][0]
    assert "LLM quota exceeded" in result["errors"][0]


@pytest.mark.asyncio
async def test_signal_detector_empty_messages() -> None:
    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value={"messages": []})

    with patch(
        "saas_lead_agent.agents.signal_detector._get_signal_detector_agent",
        return_value=mock_agent,
    ):
        result = await signal_detector(_BASE_STATE)

    assert "errors" in result
    assert "no messages" in result["errors"][0]


@pytest.mark.asyncio
async def test_signal_detector_uses_company_name_when_available() -> None:
    """When company_profile is populated, company name appears in the prompt."""
    state_with_profile: LeadState = {
        **_BASE_STATE,
        "company_profile": {**_PROFILE},
    }
    mock_agent = _make_agent_mock(json.dumps(_SIGNALS))

    with patch(
        "saas_lead_agent.agents.signal_detector._get_signal_detector_agent",
        return_value=mock_agent,
    ):
        await signal_detector(state_with_profile)

    call_args = mock_agent.ainvoke.call_args
    messages = call_args[0][0]["messages"]
    assert any("Acme Corp" in m.content for m in messages)
