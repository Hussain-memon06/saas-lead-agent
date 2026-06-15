"""StateGraph assembly for the lead-research pipeline.

Topology (sequential — Tier 1 OpenAI rate-limit friendly):
  START → retrieve_icp_context → company_researcher → contact_finder
        → signal_detector → retrieve_similar_leads
        → retrieve_outreach_examples → dossier_writer → await_approval
        → send_email → END

The three research subagents run sequentially rather than in parallel.
This trades wall-clock time for reliability: parallel execution from a
single graph step burst-fires the OpenAI API and trips Tier 1 RPM/TPM
limits, whereas a serial chain stays comfortably under quota.

dossier_writer runs after the research chain.  await_approval calls
``interrupt()``, pausing the graph until a human resumes via
``Command(resume=<bool>)``.  send_email delivers (or stubs) the draft.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from saas_lead_agent.agents.await_approval import await_approval
from saas_lead_agent.agents.company_researcher import company_researcher
from saas_lead_agent.agents.contact_finder import contact_finder
from saas_lead_agent.agents.dossier_writer import dossier_writer
from saas_lead_agent.agents.retrieval import (
    retrieve_icp_context,
    retrieve_outreach_examples,
    retrieve_similar_leads,
)
from saas_lead_agent.agents.send_email import send_email
from saas_lead_agent.agents.signal_detector import signal_detector
from saas_lead_agent.state import LeadState


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

    graph.add_node("retrieve_icp_context", retrieve_icp_context)
    graph.add_node("company_researcher", company_researcher)
    graph.add_node("contact_finder", contact_finder)
    graph.add_node("signal_detector", signal_detector)
    graph.add_node("retrieve_similar_leads", retrieve_similar_leads)
    graph.add_node("retrieve_outreach_examples", retrieve_outreach_examples)
    graph.add_node("dossier_writer", dossier_writer)
    graph.add_node("await_approval", await_approval)
    graph.add_node("send_email", send_email)

    graph.add_edge(START, "retrieve_icp_context")
    graph.add_edge("retrieve_icp_context", "company_researcher")
    graph.add_edge("company_researcher", "contact_finder")
    graph.add_edge("contact_finder", "signal_detector")
    graph.add_edge("signal_detector", "retrieve_similar_leads")
    graph.add_edge("retrieve_similar_leads", "retrieve_outreach_examples")
    graph.add_edge("retrieve_outreach_examples", "dossier_writer")
    graph.add_edge("dossier_writer", "await_approval")
    graph.add_edge("await_approval", "send_email")
    graph.add_edge("send_email", END)

    return graph.compile(checkpointer=checkpointer)


def build_graph_with_memory() -> "CompiledStateGraph[LeadState, None, LeadState, LeadState]":
    """Convenience factory that attaches an ``InMemorySaver`` checkpointer.

    Used by tests and local dev without Postgres.
    """
    return build_graph(checkpointer=MemorySaver())


@asynccontextmanager
async def build_graph_with_postgres(
    url: str | None = None,
) -> AsyncIterator["CompiledStateGraph[LeadState, None, LeadState, LeadState]"]:
    """Async context manager that yields a Postgres-backed compiled graph.

    Opens a connection pool, runs idempotent DDL, yields the graph, then
    closes the pool on exit.  Use inside a FastAPI lifespan or an async
    ``with`` block:

        async with build_graph_with_postgres(url) as graph:
            result = await graph.ainvoke(...)

    Args:
        url: PostgreSQL DSN.  Defaults to the ``POSTGRES_URL`` env var.
    """
    from saas_lead_agent.memory.checkpointer import postgres_checkpointer

    async with postgres_checkpointer(url) as checkpointer:
        yield build_graph(checkpointer)
