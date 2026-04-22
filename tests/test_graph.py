"""Tests for the lead-research StateGraph assembly.

Strategy:
- Structural tests verify the compiled graph has the expected nodes and edges
  without invoking any node logic.
- State-flow tests patch all four node functions with AsyncMocks so the graph
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


def _patch_all_nodes(
    orchestrator_update: dict[str, Any] | None = None,
    researcher_update: dict[str, Any] | None = None,
    contact_update: dict[str, Any] | None = None,
    signal_update: dict[str, Any] | None = None,
):
    """Return a context manager that patches all four node functions."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with (
            patch(
                "saas_lead_agent.agents.orchestrator.orchestrator",
                new=AsyncMock(return_value=orchestrator_update or {}),
            ),
            patch(
                "saas_lead_agent.agents.company_researcher.company_researcher",
                new=AsyncMock(return_value=researcher_update or {"company_profile": _PROFILE}),
            ),
            patch(
                "saas_lead_agent.agents.contact_finder.contact_finder",
                new=AsyncMock(return_value=contact_update or {"contact": _CONTACT}),
            ),
            patch(
                "saas_lead_agent.agents.signal_detector.signal_detector",
                new=AsyncMock(return_value=signal_update or {"signals": []}),
            ),
        ):
            yield

    return _ctx()


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
    for expected in ("orchestrator", "company_researcher", "contact_finder", "signal_detector"):
        assert expected in node_names, f"Missing node: {expected}"


def test_graph_start_goes_to_orchestrator() -> None:
    """START must connect directly to orchestrator."""
    graph = build_graph()
    # builder.edges holds the compiled edge set as (src, dst) tuples
    start_targets = {dst for src, dst in graph.builder.edges if src == "__start__"}
    assert "orchestrator" in start_targets


def test_graph_orchestrator_fans_out() -> None:
    """Orchestrator must have outgoing edges to all three subagent nodes."""
    graph = build_graph()
    orch_targets = {dst for src, dst in graph.builder.edges if src == "orchestrator"}
    assert orch_targets == {"company_researcher", "contact_finder", "signal_detector"}


def test_graph_subagents_fan_in_to_end() -> None:
    """All three subagent nodes must connect to END."""
    graph = build_graph()
    # _all_edges includes fan-in edges to __end__ that builder.edges omits
    end_sources = {src for src, dst in graph.builder._all_edges if dst == "__end__"}
    assert {"company_researcher", "contact_finder", "signal_detector"}.issubset(end_sources)


# ---------------------------------------------------------------------------
# State-flow tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_run_populates_company_profile() -> None:
    # Patch at saas_lead_agent.graph.* — that's where build_graph() reads the
    # callable references when it calls add_node().  build_graph() must be
    # called inside the patch context so it captures the mocks, not originals.
    with patch(
        "saas_lead_agent.graph.orchestrator", new=AsyncMock(return_value={})
    ), patch(
        "saas_lead_agent.graph.company_researcher",
        new=AsyncMock(return_value={"company_profile": _PROFILE}),
    ), patch(
        "saas_lead_agent.graph.contact_finder",
        new=AsyncMock(return_value={"contact": _CONTACT}),
    ), patch(
        "saas_lead_agent.graph.signal_detector",
        new=AsyncMock(return_value={"signals": []}),
    ):
        graph = build_graph()
        config = {"configurable": {"thread_id": "lead:acme.example.com"}}
        result = await graph.ainvoke(_BASE_INPUT, config=config)

    assert result["company_profile"]["name"] == "Acme Corp"
    assert result["contact"]["source"] == "stub"
    assert result["signals"] == []


@pytest.mark.asyncio
async def test_graph_run_with_memory_preserves_thread() -> None:
    """build_graph_with_memory should compile and run successfully."""
    with patch(
        "saas_lead_agent.graph.orchestrator", new=AsyncMock(return_value={})
    ), patch(
        "saas_lead_agent.graph.company_researcher",
        new=AsyncMock(return_value={"company_profile": _PROFILE}),
    ), patch(
        "saas_lead_agent.graph.contact_finder",
        new=AsyncMock(return_value={"contact": _CONTACT}),
    ), patch(
        "saas_lead_agent.graph.signal_detector",
        new=AsyncMock(return_value={"signals": []}),
    ):
        graph = build_graph_with_memory()
        config = {"configurable": {"thread_id": "lead:acme.example.com"}}
        result = await graph.ainvoke(_BASE_INPUT, config=config)

    assert result["company_profile"] is not None


@pytest.mark.asyncio
async def test_graph_errors_accumulate_across_nodes() -> None:
    """errors reducer (operator.add) must concatenate errors from all nodes."""
    with patch(
        "saas_lead_agent.graph.orchestrator", new=AsyncMock(return_value={})
    ), patch(
        "saas_lead_agent.graph.company_researcher",
        new=AsyncMock(return_value={"errors": ["researcher failed"]}),
    ), patch(
        "saas_lead_agent.graph.contact_finder",
        new=AsyncMock(return_value={"errors": ["contact failed"]}),
    ), patch(
        "saas_lead_agent.graph.signal_detector",
        new=AsyncMock(return_value={"signals": []}),
    ):
        graph = build_graph()
        config = {"configurable": {"thread_id": "lead:error-test"}}
        result = await graph.ainvoke(_BASE_INPUT, config=config)

    assert "researcher failed" in result["errors"]
    assert "contact failed" in result["errors"]


@pytest.mark.asyncio
async def test_graph_partial_results_on_node_error() -> None:
    """A node returning only errors should not overwrite other nodes' results."""
    with patch(
        "saas_lead_agent.graph.orchestrator", new=AsyncMock(return_value={})
    ), patch(
        "saas_lead_agent.graph.company_researcher",
        new=AsyncMock(return_value={"company_profile": _PROFILE}),
    ), patch(
        "saas_lead_agent.graph.contact_finder",
        new=AsyncMock(return_value={"errors": ["contact failed"]}),
    ), patch(
        "saas_lead_agent.graph.signal_detector",
        new=AsyncMock(return_value={"signals": []}),
    ):
        graph = build_graph()
        config = {"configurable": {"thread_id": "lead:partial-test"}}
        result = await graph.ainvoke(_BASE_INPUT, config=config)

    assert result["company_profile"]["name"] == "Acme Corp"
    assert "contact failed" in result["errors"]
