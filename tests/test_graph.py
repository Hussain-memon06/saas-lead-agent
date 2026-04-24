"""Tests for the lead-research StateGraph assembly.

Strategy:
- Structural tests verify the compiled graph has the expected nodes and edges
  without invoking any node logic.
- State-flow tests patch all five node functions with AsyncMocks so the graph
  runs end-to-end with no LLM or network calls.
- Error-propagation test confirms the errors reducer accumulates across nodes.
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
    "messages": [],
    "company_profile": None,
    "contact": None,
    "signals": None,
    "fit_score": None,
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


def _patch_graph(
    orchestrator_rv: dict[str, Any] | None = None,
    researcher_rv: dict[str, Any] | None = None,
    contact_rv: dict[str, Any] | None = None,
    signal_rv: dict[str, Any] | None = None,
    dossier_rv: dict[str, Any] | None = None,
):
    """Stack patches for all five graph node callables at the graph module."""
    return (
        patch("saas_lead_agent.graph.orchestrator",
              new=AsyncMock(return_value=orchestrator_rv or {})),
        patch("saas_lead_agent.graph.company_researcher",
              new=AsyncMock(return_value=researcher_rv or {"company_profile": _PROFILE})),
        patch("saas_lead_agent.graph.contact_finder",
              new=AsyncMock(return_value=contact_rv or {"contact": _CONTACT})),
        patch("saas_lead_agent.graph.signal_detector",
              new=AsyncMock(return_value=signal_rv or {"signals": []})),
        patch("saas_lead_agent.graph.dossier_writer",
              new=AsyncMock(return_value=dossier_rv or _DOSSIER)),
    )


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
        "orchestrator",
        "company_researcher",
        "contact_finder",
        "signal_detector",
        "dossier_writer",
    ):
        assert expected in node_names, f"Missing node: {expected}"


def test_graph_start_goes_to_orchestrator() -> None:
    graph = build_graph()
    start_targets = {dst for src, dst in graph.builder.edges if src == "__start__"}
    assert "orchestrator" in start_targets


def test_graph_orchestrator_fans_out() -> None:
    """Orchestrator must have outgoing edges to all three subagent nodes."""
    graph = build_graph()
    orch_targets = {dst for src, dst in graph.builder.edges if src == "orchestrator"}
    assert orch_targets == {"company_researcher", "contact_finder", "signal_detector"}


def test_graph_subagents_fan_in_to_dossier_writer() -> None:
    """All three subagent nodes must fan in to dossier_writer (not END)."""
    graph = build_graph()
    dossier_sources = {src for src, dst in graph.builder._all_edges if dst == "dossier_writer"}
    assert {"company_researcher", "contact_finder", "signal_detector"}.issubset(dossier_sources)


def test_graph_dossier_writer_goes_to_end() -> None:
    """dossier_writer must connect to END."""
    graph = build_graph()
    end_sources = {src for src, dst in graph.builder._all_edges if dst == "__end__"}
    assert "dossier_writer" in end_sources
    # subagents must NOT connect directly to END any more
    for node in ("company_researcher", "contact_finder", "signal_detector"):
        assert node not in end_sources, f"{node} should not go directly to END"


# ---------------------------------------------------------------------------
# State-flow tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_run_populates_all_fields() -> None:
    with patch("saas_lead_agent.graph.orchestrator", new=AsyncMock(return_value={})), \
         patch("saas_lead_agent.graph.company_researcher",
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
    with patch("saas_lead_agent.graph.orchestrator", new=AsyncMock(return_value={})), \
         patch("saas_lead_agent.graph.company_researcher",
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
async def test_graph_errors_accumulate_across_nodes() -> None:
    """errors reducer (operator.add) must concatenate errors from all nodes."""
    with patch("saas_lead_agent.graph.orchestrator", new=AsyncMock(return_value={})), \
         patch("saas_lead_agent.graph.company_researcher",
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
    with patch("saas_lead_agent.graph.orchestrator", new=AsyncMock(return_value={})), \
         patch("saas_lead_agent.graph.company_researcher",
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
