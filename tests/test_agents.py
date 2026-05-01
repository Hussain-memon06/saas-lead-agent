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
from langchain_core.messages import AIMessage

from saas_lead_agent.agents.company_researcher import company_researcher
from saas_lead_agent.agents.contact_finder import contact_finder
from saas_lead_agent.agents.dossier_writer import dossier_writer
from saas_lead_agent.agents.send_email import send_email
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
    "sources": ["https://acme.example.com/about", "https://blog.acme.example.com/team"],
}

_BASE_STATE: LeadState = {
    "company_url": "https://acme.example.com",
    "domain": "acme.example.com",
    "icp_context": None,
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
        "source": "https://blog.acme.example.com/series-a-announcement",
        "details": "Acme Corp raised $10M Series A",
    },
    {
        "signal_type": "hiring",
        "date": None,
        "source": "https://careers.acme.example.com/engineering",
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


@pytest.mark.asyncio
async def test_company_researcher_keeps_profile_when_sources_contain_domain() -> None:
    """When at least one source URL contains the domain, profile is preserved."""
    mock_agent = _make_agent_mock(json.dumps(_PROFILE))

    with patch(
        "saas_lead_agent.agents.company_researcher._get_researcher_agent",
        return_value=mock_agent,
    ):
        result = await company_researcher(_BASE_STATE)

    profile = result["company_profile"]
    assert profile["name"] == "Acme Corp"
    assert profile["tagline"] == "Anvils for every occasion"
    assert profile["funding_stage"] == "Series A"
    assert profile["products"] == ["Heavy Anvil", "Rocket Skates"]
    assert len(profile["sources"]) == 2


@pytest.mark.asyncio
async def test_company_researcher_resets_fields_when_no_sources_match_domain() -> None:
    """When no source URL contains the domain, fields reset to null; name kept."""
    wrong_company_profile: dict[str, Any] = {
        "name": "Acme Corp",  # from the URL, kept
        "tagline": "From a different company",
        "hq": "Wrong City",
        "employees_estimate": "1000+",
        "funding_stage": "Public",
        "products": ["Wrong Product"],
        "notable_customers": ["Wrong Customer"],
        "sources": [
            "https://techcrunch.com/some-other-acme",
            "https://different-company.com/about",
        ],
    }
    mock_agent = _make_agent_mock(json.dumps(wrong_company_profile))

    with patch(
        "saas_lead_agent.agents.company_researcher._get_researcher_agent",
        return_value=mock_agent,
    ):
        result = await company_researcher(_BASE_STATE)

    profile = result["company_profile"]
    assert profile["name"] == "Acme Corp"  # preserved (from URL)
    assert profile["tagline"] is None
    assert profile["hq"] is None
    assert profile["employees_estimate"] is None
    assert profile["funding_stage"] is None
    assert profile["products"] == []
    assert profile["notable_customers"] == []
    # sources kept for debugging
    assert len(profile["sources"]) == 2


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


@pytest.mark.asyncio
async def test_signal_detector_drops_off_domain_signals() -> None:
    """Signals whose source URL does not contain the company domain are dropped."""
    mixed_signals: list[dict[str, Any]] = [
        {
            "signal_type": "funding",
            "date": "2024-03",
            "source": "https://blog.acme.example.com/news",
            "details": "Genuine Acme signal",
        },
        {
            "signal_type": "funding",
            "date": "2024-03",
            "source": "https://different-company.com/news",
            "details": "Signal from a different company with similar name",
        },
        {
            "signal_type": "hiring",
            "date": None,
            "source": None,
            "details": "No source — cannot verify",
        },
    ]
    mock_agent = _make_agent_mock(json.dumps(mixed_signals))

    with patch(
        "saas_lead_agent.agents.signal_detector._get_signal_detector_agent",
        return_value=mock_agent,
    ):
        result = await signal_detector(_BASE_STATE)

    assert len(result["signals"]) == 1
    assert result["signals"][0]["details"] == "Genuine Acme signal"


@pytest.mark.asyncio
async def test_signal_detector_returns_empty_when_all_off_domain() -> None:
    """When every signal source is off-domain, result is empty list (not error)."""
    off_domain: list[dict[str, Any]] = [
        {
            "signal_type": "funding",
            "date": "2024-03",
            "source": "https://techcrunch.com/acme-corp-series-a",
            "details": "Wrong-company signal",
        },
    ]
    mock_agent = _make_agent_mock(json.dumps(off_domain))

    with patch(
        "saas_lead_agent.agents.signal_detector._get_signal_detector_agent",
        return_value=mock_agent,
    ):
        result = await signal_detector(_BASE_STATE)

    assert result["signals"] == []
    assert "errors" not in result


# ---------------------------------------------------------------------------
# dossier_writer node
# ---------------------------------------------------------------------------

_DOSSIER_RESPONSE: dict[str, Any] = {
    "fit_score": 8,
    "score_explanation": "8/10 — B2B SaaS ✅, Series A ✅, US ✅, hiring SDRs ✅",
    "email_subject": "Quick question about Acme Corp",
    "email_body": "Hi Alice, saw your recent funding round — congrats!",
}


def _make_model_mock(content: str) -> MagicMock:
    """Return a mock model whose ainvoke resolves to an AIMessage."""
    model = MagicMock()
    model.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return model


@pytest.mark.asyncio
async def test_dossier_writer_happy_path() -> None:
    mock_model = _make_model_mock(json.dumps(_DOSSIER_RESPONSE))

    with patch("saas_lead_agent.agents.dossier_writer._get_model", return_value=mock_model):
        result = await dossier_writer(_BASE_STATE)

    assert result["fit_score"] == 8
    assert result["score_explanation"] == "8/10 — B2B SaaS ✅, Series A ✅, US ✅, hiring SDRs ✅"
    assert result["email_subject"] == "Quick question about Acme Corp"
    assert result["email_body"] == "Hi Alice, saw your recent funding round — congrats!"
    assert "errors" not in result


@pytest.mark.asyncio
async def test_dossier_writer_score_explanation_defaults_to_empty_when_missing() -> None:
    """If the model omits score_explanation, fall back to '' rather than crash."""
    payload = {k: v for k, v in _DOSSIER_RESPONSE.items() if k != "score_explanation"}
    mock_model = _make_model_mock(json.dumps(payload))

    with patch("saas_lead_agent.agents.dossier_writer._get_model", return_value=mock_model):
        result = await dossier_writer(_BASE_STATE)

    assert result["fit_score"] == 8
    assert result["score_explanation"] == ""
    assert "errors" not in result


@pytest.mark.asyncio
async def test_dossier_writer_separate_subject_and_body() -> None:
    """email_subject and email_body must be distinct keys — not concatenated."""
    mock_model = _make_model_mock(json.dumps(_DOSSIER_RESPONSE))

    with patch("saas_lead_agent.agents.dossier_writer._get_model", return_value=mock_model):
        result = await dossier_writer(_BASE_STATE)

    assert "email_subject" in result
    assert "email_body" in result
    assert result["email_subject"] != result["email_body"]
    assert "\n\n" not in result["email_subject"]


@pytest.mark.asyncio
async def test_dossier_writer_handles_none_upstream_fields() -> None:
    """Node must not crash when company_profile, contact, signals are all None."""
    mock_model = _make_model_mock(json.dumps(_DOSSIER_RESPONSE))

    with patch("saas_lead_agent.agents.dossier_writer._get_model", return_value=mock_model):
        result = await dossier_writer(_BASE_STATE)  # _BASE_STATE has all None

    assert result["fit_score"] == 8
    assert "errors" not in result


@pytest.mark.asyncio
async def test_dossier_writer_json_parse_error() -> None:
    mock_model = _make_model_mock("Sorry, I cannot score this company.")

    with patch("saas_lead_agent.agents.dossier_writer._get_model", return_value=mock_model):
        result = await dossier_writer(_BASE_STATE)

    assert "errors" in result
    assert "JSON parse error" in result["errors"][0]
    assert "fit_score" not in result


@pytest.mark.asyncio
async def test_dossier_writer_model_exception() -> None:
    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(side_effect=RuntimeError("OpenAI quota exceeded"))

    with patch("saas_lead_agent.agents.dossier_writer._get_model", return_value=mock_model):
        result = await dossier_writer(_BASE_STATE)

    assert "errors" in result
    assert "model invocation failed" in result["errors"][0]
    assert "OpenAI quota exceeded" in result["errors"][0]


@pytest.mark.asyncio
async def test_dossier_writer_clamps_fit_score() -> None:
    for raw_score, expected in [(0, 1), (11, 10), (-5, 1), (100, 10)]:
        resp = {**_DOSSIER_RESPONSE, "fit_score": raw_score}
        mock_model = _make_model_mock(json.dumps(resp))

        with patch("saas_lead_agent.agents.dossier_writer._get_model", return_value=mock_model):
            result = await dossier_writer(_BASE_STATE)

        got = result["fit_score"]
        assert got == expected, f"score {raw_score} → expected {expected}, got {got}"


_ICP_FIXTURE: dict[str, Any] = {
    "seller_name": "John at Acme Agency",
    "offering": "B2B sales automation software for SaaS companies",
    "target_industries": ["B2B SaaS", "Fintech"],
    "target_stages": ["Series B", "Series C"],
    "target_geographies": ["US", "EU"],
    "target_employees": "51-200",
    "must_have_signals": ["Recent funding", "Hiring sales team"],
    "red_flags": ["Pre-revenue", "Consumer app"],
    "value_proposition": "We help SaaS teams 3x their meeting volume.",
}


@pytest.mark.asyncio
async def test_dossier_writer_uses_icp_prompt_when_icp_provided() -> None:
    """When state.icp_context is set, the system prompt embeds the rubric."""
    mock_model = _make_model_mock(json.dumps(_DOSSIER_RESPONSE))
    state: LeadState = {**_BASE_STATE, "icp_context": _ICP_FIXTURE}

    with patch("saas_lead_agent.agents.dossier_writer._get_model", return_value=mock_model):
        await dossier_writer(state)

    sent_messages = mock_model.ainvoke.call_args.args[0]
    system_content = sent_messages[0].content
    # ICP fields must appear in the prompt verbatim.
    assert "John at Acme Agency" in system_content
    assert "B2B SaaS, Fintech" in system_content
    assert "Series B, Series C" in system_content
    assert "Recent funding, Hiring sales team" in system_content
    assert "Pre-revenue, Consumer app" in system_content
    assert "We help SaaS teams 3x their meeting volume." in system_content
    # The pipe-format spec must be in the prompt so the model emits the
    # explanation in the shape the dossier UI parses.
    assert "Industry:" in system_content and "✅" in system_content


@pytest.mark.asyncio
async def test_dossier_writer_uses_generic_prompt_when_no_icp() -> None:
    """When state.icp_context is None, the prompt is the generic fallback."""
    mock_model = _make_model_mock(json.dumps(_DOSSIER_RESPONSE))

    with patch("saas_lead_agent.agents.dossier_writer._get_model", return_value=mock_model):
        await dossier_writer(_BASE_STATE)  # _BASE_STATE has icp_context=None

    sent_messages = mock_model.ainvoke.call_args.args[0]
    system_content = sent_messages[0].content
    assert "Set your ICP in Settings" in system_content
    # The ICP-mode rubric phrases must NOT appear.
    assert "STRICTLY against this Ideal Customer Profile" not in system_content


# ===========================================================================
# send_email node — delivery branches
# ===========================================================================

_APPROVED_STATE: LeadState = {
    **_BASE_STATE,
    "contact": {"email": "alice@acme.example.com", "name": "Alice"},
    "email_subject": "Quick question",
    "email_body": "Hi Alice,",
    "email_approved": True,
}


@pytest.mark.asyncio
async def test_send_email_rejected_when_not_approved() -> None:
    """email_approved is None or False → send_result='rejected', no delivery."""
    for approved in (None, False):
        state = {**_APPROVED_STATE, "email_approved": approved}
        result = await send_email(state)  # type: ignore[arg-type]
        assert result == {"send_result": "rejected"}


@pytest.mark.asyncio
async def test_send_email_no_contact_when_email_missing() -> None:
    """Approved but contact has no email → send_result='no_contact'."""
    state = {**_APPROVED_STATE, "contact": {"name": "Alice", "email": None}}
    result = await send_email(state)  # type: ignore[arg-type]
    assert result == {"send_result": "no_contact"}


@pytest.mark.asyncio
async def test_send_email_no_contact_when_contact_dict_missing() -> None:
    """Approved but contact dict is None → send_result='no_contact'."""
    state = {**_APPROVED_STATE, "contact": None}
    result = await send_email(state)  # type: ignore[arg-type]
    assert result == {"send_result": "no_contact"}


@pytest.mark.asyncio
async def test_send_email_stub_mode_when_no_api_key() -> None:
    """Approved + contact email but no SENDGRID_API_KEY → stub 'sent', no delivery."""
    import os as _os
    with patch.dict(_os.environ, {}, clear=False):
        _os.environ.pop("SENDGRID_API_KEY", None)
        result = await send_email(_APPROVED_STATE)  # type: ignore[arg-type]
    assert result == {"send_result": "sent"}


@pytest.mark.asyncio
async def test_send_email_calls_sendgrid_on_success() -> None:
    """Approved + key set → calls send_email_via_sendgrid, returns delivery metadata."""
    import os as _os
    fake_result = {
        "status_code": 202,
        "message_id": "msg-real-123",
        "sent_at": "2026-04-25T12:00:00+00:00",
    }
    with patch.dict(_os.environ, {"SENDGRID_API_KEY": "SG.test"}, clear=False):
        with patch(
            "saas_lead_agent.agents.send_email.send_email_via_sendgrid",
            new=AsyncMock(return_value=fake_result),
        ) as mock_send:
            result = await send_email(_APPROVED_STATE)  # type: ignore[arg-type]

    mock_send.assert_awaited_once_with(
        to="alice@acme.example.com",
        subject="Quick question",
        body="Hi Alice,",
    )
    assert result["send_result"] == "sent"
    assert result["message_id"] == "msg-real-123"
    assert result["sent_at"] == "2026-04-25T12:00:00+00:00"


@pytest.mark.asyncio
async def test_send_email_records_failure_on_sendgrid_error() -> None:
    """SendGrid raises → send_result='failed' + error appended; node does not raise."""
    import os as _os
    with patch.dict(_os.environ, {"SENDGRID_API_KEY": "SG.test"}, clear=False):
        with patch(
            "saas_lead_agent.agents.send_email.send_email_via_sendgrid",
            new=AsyncMock(side_effect=RuntimeError("non-2xx status 500")),
        ):
            result = await send_email(_APPROVED_STATE)  # type: ignore[arg-type]

    assert result["send_result"] == "failed"
    assert any("non-2xx status 500" in err for err in result["errors"])
