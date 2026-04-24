"""StateGraph assembly for the lead-research pipeline.

Topology (Phase 2):
  START → orchestrator → [company_researcher, contact_finder, signal_detector]
  [company_researcher, contact_finder, signal_detector] → dossier_writer → END

The three subagent nodes run in parallel (one super-step after orchestrator).
dossier_writer runs after the fan-in, with all three results available in state.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from saas_lead_agent.agents.company_researcher import company_researcher
from saas_lead_agent.agents.contact_finder import contact_finder
from saas_lead_agent.agents.dossier_writer import dossier_writer
from saas_lead_agent.agents.orchestrator import orchestrator
from saas_lead_agent.agents.signal_detector import signal_detector
from saas_lead_agent.state import LeadState

_SUBAGENT_NODES = ["company_researcher", "contact_finder", "signal_detector"]


def build_graph(
    checkpointer: "BaseCheckpointSaver[str] | None" = None,
) -> "CompiledStateGraph[LeadState, None, LeadState, LeadState]":
    """Build and compile the lead-research StateGraph.

    Args:
        checkpointer: Persistence backend.  Pass ``None`` for a stateless
            graph (useful in unit tests), or an ``InMemorySaver`` /
            ``AsyncPostgresSaver`` instance for durable runs.

    Returns:
        A compiled ``CompiledStateGraph`` ready for ``.ainvoke()`` /
        ``.astream()``.
    """
    graph = StateGraph(LeadState)

    graph.add_node("orchestrator", orchestrator)
    graph.add_node("company_researcher", company_researcher)
    graph.add_node("contact_finder", contact_finder)
    graph.add_node("signal_detector", signal_detector)
    graph.add_node("dossier_writer", dossier_writer)

    graph.add_edge(START, "orchestrator")
    for node in _SUBAGENT_NODES:
        graph.add_edge("orchestrator", node)
    graph.add_edge(_SUBAGENT_NODES, "dossier_writer")
    graph.add_edge("dossier_writer", END)

    return graph.compile(checkpointer=checkpointer)


def build_graph_with_memory() -> "CompiledStateGraph[LeadState, None, LeadState, LeadState]":
    """Convenience factory that attaches an ``InMemorySaver`` checkpointer.

    Used by the FastAPI routes and manual testing.  Phase 2 will swap this
    for ``AsyncPostgresSaver`` per ADR-001.
    """
    return build_graph(checkpointer=MemorySaver())
