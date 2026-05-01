"""Tests for the lead-research StateGraph assembly.

Strategy:
- Structural tests verify the compiled graph has the expected nodes and edges
  without invoking any node logic.
- State-flow tests patch all node functions with AsyncMocks so the graph
  runs end-to-end with no LLM or network calls.
- Error-propagation test confirms the errors reducer accumulates across nodes.

The graph runs sequentially: research nodes are chained
(company_researcher → contact_finder → signal_detector) rather than fanned
out, to stay under Tier 1 OpenAI rate limits.
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from saas_lead_agent.graph import build_graph, build_graph_with_memory
from saas_lead_agent.state import LeadState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_INPUT: LeadState = {
    "company_url": "https://acme.example.com",
    "domain": "acme.example.com",
    "icp_context": None,
    "messages": [],
    "company_profile": None,
    "contact": None,
    "signals": None,
    "fit_score": None,
    "score_explanation": None,
    "email_subject": None,
    "email_body": None,
    "errors": [],
}

_PROFILE: dict[str, Any] = {
    "name": "Acme Corp",
    "funding_stage": "Series A",
    "products": [],
    "notable_customers": [],
    "tagline": None,
    "hq": None,
    "employees_estimate": None,
}

_CONTACT: dict[str, Any] = {
    "name": None,
    "title": None,
    "email": None,
    "linkedin": None,
    "source": "stub",
    "domain": "acme.example.com",
}

_DOSSIER: dict[str, Any] = {
    "fit_score": 8,
    "email_subject": "Quick question",
    "email_body": "Hi Alice,",
}


# ---------------------------------------------------------------------------
# Structural tests (no node execution)
# ---------------------------------------------------------------------------


def test_build_graph_compiles() -> None:
    graph = build_graph()
    assert graph is not None


def test_build_graph_with_memory_compiles() -> None:
    graph = build_graph_with_memory()
    assert graph is not None


def test_graph_has_expected_nodes() -> None:
    graph = build_graph()
    node_names = set(graph.nodes.keys())
    for expected in (
        "company_researcher",
        "contact_finder",
        "signal_detector",
        "dossier_writer",
        "await_approval",
        "send_email",
    ):
        assert expected in node_names, f"Missing node: {expected}"


def test_graph_orchestrator_node_removed() -> None:
    """Orchestrator dispatcher is gone; research nodes run sequentially."""
    graph = build_graph()
    assert "orchestrator" not in set(graph.nodes.keys())


def test_graph_start_goes_to_company_researcher() -> None:
    graph = build_graph()
    start_targets = {dst for src, dst in graph.builder.edges if src == "__start__"}
    assert "company_researcher" in start_targets


def test_graph_research_nodes_run_sequentially() -> None:
    """Research subagents must form a chain, not a fan-out."""
    graph = build_graph()
    edges = set(graph.builder.edges)
    assert ("company_researcher", "contact_finder") in edges
    assert ("contact_finder", "signal_detector") in edges
    assert ("signal_detector", "dossier_writer") in edges


def test_graph_dossier_writer_goes_to_await_approval() -> None:
    """dossier_writer must feed into await_approval (HITL gate)."""
    graph = build_graph()
    targets = {dst for src, dst in graph.builder.edges if src == "dossier_writer"}
    assert "await_approval" in targets


def test_graph_await_approval_goes_to_send_email() -> None:
    """After the HITL resume, the graph proceeds to send_email."""
    graph = build_graph()
    targets = {dst for src, dst in graph.builder.edges if src == "await_approval"}
    assert "send_email" in targets


def test_graph_send_email_goes_to_end() -> None:
    """send_email is the terminal node."""
    graph = build_graph()
    end_sources = {src for src, dst in graph.builder._all_edges if dst == "__end__"}
    assert "send_email" in end_sources
    # Research/dossier nodes must not connect directly to END.
    for node in ("company_researcher", "contact_finder", "signal_detector", "dossier_writer"):
        assert node not in end_sources, f"{node} should not go directly to END"


# ---------------------------------------------------------------------------
# State-flow tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_run_populates_all_fields() -> None:
    with patch("saas_lead_agent.graph.company_researcher",
               new=AsyncMock(return_value={"company_profile": _PROFILE})), \
         patch("saas_lead_agent.graph.contact_finder",
               new=AsyncMock(return_value={"contact": _CONTACT})), \
         patch("saas_lead_agent.graph.signal_detector",
               new=AsyncMock(return_value={"signals": []})), \
         patch("saas_lead_agent.graph.dossier_writer",
               new=AsyncMock(return_value=_DOSSIER)):
        graph = build_graph()
        config = {"configurable": {"thread_id": "lead:acme.example.com"}}
        result = await graph.ainvoke(_BASE_INPUT, config=config)

    assert result["company_profile"]["name"] == "Acme Corp"
    assert result["contact"]["source"] == "stub"
    assert result["signals"] == []
    assert result["fit_score"] == 8
    assert result["email_subject"] == "Quick question"
    assert result["email_body"] == "Hi Alice,"


@pytest.mark.asyncio
async def test_graph_run_with_memory_compiles_and_runs() -> None:
    with patch("saas_lead_agent.graph.company_researcher",
               new=AsyncMock(return_value={"company_profile": _PROFILE})), \
         patch("saas_lead_agent.graph.contact_finder",
               new=AsyncMock(return_value={"contact": _CONTACT})), \
         patch("saas_lead_agent.graph.signal_detector",
               new=AsyncMock(return_value={"signals": []})), \
         patch("saas_lead_agent.graph.dossier_writer",
               new=AsyncMock(return_value=_DOSSIER)):
        graph = build_graph_with_memory()
        config = {"configurable": {"thread_id": "lead:acme.example.com"}}
        result = await graph.ainvoke(_BASE_INPUT, config=config)

    assert result["company_profile"] is not None
    assert result["fit_score"] == 8


@pytest.mark.asyncio
async def test_graph_research_nodes_called_in_order() -> None:
    """company_researcher runs first, then contact_finder, then signal_detector."""
    call_order: list[str] = []

    async def _researcher(state: LeadState) -> dict[str, Any]:
        call_order.append("company_researcher")
        return {"company_profile": _PROFILE}

    async def _contact(state: LeadState) -> dict[str, Any]:
        call_order.append("contact_finder")
        return {"contact": _CONTACT}

    async def _signal(state: LeadState) -> dict[str, Any]:
        call_order.append("signal_detector")
        return {"signals": []}

    with patch("saas_lead_agent.graph.company_researcher", new=_researcher), \
         patch("saas_lead_agent.graph.contact_finder", new=_contact), \
         patch("saas_lead_agent.graph.signal_detector", new=_signal), \
         patch("saas_lead_agent.graph.dossier_writer",
               new=AsyncMock(return_value=_DOSSIER)):
        graph = build_graph()
        config = {"configurable": {"thread_id": "lead:order-test"}}
        await graph.ainvoke(_BASE_INPUT, config=config)

    assert call_order == ["company_researcher", "contact_finder", "signal_detector"]


@pytest.mark.asyncio
async def test_graph_errors_accumulate_across_nodes() -> None:
    """errors reducer (operator.add) must concatenate errors from all nodes."""
    with patch("saas_lead_agent.graph.company_researcher",
               new=AsyncMock(return_value={"errors": ["researcher failed"]})), \
         patch("saas_lead_agent.graph.contact_finder",
               new=AsyncMock(return_value={"errors": ["contact failed"]})), \
         patch("saas_lead_agent.graph.signal_detector",
               new=AsyncMock(return_value={"signals": []})), \
         patch("saas_lead_agent.graph.dossier_writer",
               new=AsyncMock(return_value={"errors": ["dossier failed"]})):
        graph = build_graph()
        config = {"configurable": {"thread_id": "lead:error-test"}}
        result = await graph.ainvoke(_BASE_INPUT, config=config)

    assert "researcher failed" in result["errors"]
    assert "contact failed" in result["errors"]
    assert "dossier failed" in result["errors"]


@pytest.mark.asyncio
async def test_graph_partial_results_on_node_error() -> None:
    """A node returning only errors should not overwrite other nodes' results."""
    with patch("saas_lead_agent.graph.company_researcher",
               new=AsyncMock(return_value={"company_profile": _PROFILE})), \
         patch("saas_lead_agent.graph.contact_finder",
               new=AsyncMock(return_value={"errors": ["contact failed"]})), \
         patch("saas_lead_agent.graph.signal_detector",
               new=AsyncMock(return_value={"signals": []})), \
         patch("saas_lead_agent.graph.dossier_writer",
               new=AsyncMock(return_value=_DOSSIER)):
        graph = build_graph()
        config = {"configurable": {"thread_id": "lead:partial-test"}}
        result = await graph.ainvoke(_BASE_INPUT, config=config)

    assert result["company_profile"]["name"] == "Acme Corp"
    assert "contact failed" in result["errors"]
    assert result["fit_score"] == 8
