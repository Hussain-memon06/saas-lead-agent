"""Tests for the company_researcher agent node.

Strategy:
- _extract_json is a pure function — tested directly with no mocking.
- company_researcher is an async node — _get_researcher_agent is patched to
  return a MagicMock whose ainvoke is an AsyncMock, so no real LLM or network
  calls occur.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas_lead_agent.agents.company_researcher import _extract_json, company_researcher
from saas_lead_agent.state import LeadState

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
    "errors": [],
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
