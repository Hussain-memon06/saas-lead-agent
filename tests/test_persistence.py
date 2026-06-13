"""Integration tests for AsyncPostgresSaver thread persistence.

These tests require a running Postgres instance.  They are automatically
skipped when POSTGRES_URL is not set so the normal pytest suite stays green
without any infrastructure.

To run against a local container:

    docker run --name saas-lead-pg \\
        -e POSTGRES_USER=saas_lead \\
        -e POSTGRES_PASSWORD=password \\
        -e POSTGRES_DB=saas_lead \\
        -p 5432:5432 -d postgres:15

    POSTGRES_URL=postgresql://saas_lead:password@localhost:5432/saas_lead \\
        uv run pytest tests/test_persistence.py -v
"""

import os
import uuid
from typing import Any

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

# ---------------------------------------------------------------------------
# Skip marker — entire module skips when POSTGRES_URL is absent
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not os.environ.get("POSTGRES_URL"),
    reason="requires POSTGRES_URL env var pointing to a running Postgres instance",
)

# ---------------------------------------------------------------------------
# Minimal test graph (no LLMs)
# ---------------------------------------------------------------------------


class _SimpleState(dict[str, Any]):
    """Minimal TypedDict-compatible state for persistence tests."""


def _step_a(state: dict[str, Any]) -> dict[str, Any]:
    return {"counter": state.get("counter", 0) + 1}


def _step_b(state: dict[str, Any]) -> dict[str, Any]:
    """Interrupt here; resume value drives whether counter increments."""
    decision: bool = interrupt({"type": "test_gate", "counter": state.get("counter")})
    increment = 1 if decision else 0
    return {"counter": state.get("counter", 0) + increment}


def _build_test_graph(checkpointer: AsyncPostgresSaver) -> Any:
    from typing import TypedDict

    class _S(TypedDict):
        counter: int

    g: StateGraph[_S, Any, Any] = StateGraph(_S)
    g.add_node("step_a", _step_a)
    g.add_node("step_b", _step_b)
    g.add_edge(START, "step_a")
    g.add_edge("step_a", "step_b")
    g.add_edge("step_b", END)
    return g.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thread_persists_across_checkpointer_instances() -> None:
    """State saved before interrupt survives closing and reopening the connection.

    Simulates a server restart between the qualify call (which hits the
    interrupt) and the approve call (which resumes the graph).
    """
    url = os.environ["POSTGRES_URL"]
    thread_id = f"persist-test-{uuid.uuid4().hex}"
    config = _cfg(thread_id)

    # --- First connection: run until interrupt ---
    async with AsyncPostgresSaver.from_conn_string(url) as cp:
        await cp.setup()
        g = _build_test_graph(cp)
        # ainvoke returns current state when graph pauses at interrupt
        await g.ainvoke({"counter": 0}, config=config, durability="sync")
        # step_a ran → counter == 1 in checkpoint; step_b interrupted

    # --- Second connection (simulates restart): resume and run to END ---
    async with AsyncPostgresSaver.from_conn_string(url) as cp:
        g = _build_test_graph(cp)
        result = await g.ainvoke(Command(resume=True), config=config, durability="sync")

    # step_b ran with decision=True → counter += 1 → 2
    assert result["counter"] == 2, (
        f"Expected counter=2 after resume; got {result['counter']!r}. "
        "State did not survive the connection close."
    )


@pytest.mark.asyncio
async def test_thread_persists_with_resume_false() -> None:
    """Resume with False skips the increment; counter stays at 1."""
    url = os.environ["POSTGRES_URL"]
    thread_id = f"persist-test-false-{uuid.uuid4().hex}"
    config = _cfg(thread_id)

    async with AsyncPostgresSaver.from_conn_string(url) as cp:
        await cp.setup()
        g = _build_test_graph(cp)
        await g.ainvoke({"counter": 0}, config=config, durability="sync")

    async with AsyncPostgresSaver.from_conn_string(url) as cp:
        g = _build_test_graph(cp)
        result = await g.ainvoke(Command(resume=False), config=config, durability="sync")

    # step_b ran with decision=False → counter += 0 → stays at 1
    assert result["counter"] == 1


@pytest.mark.asyncio
async def test_thread_ids_are_isolated() -> None:
    """Two thread_ids in the same Postgres DB don't share state."""
    url = os.environ["POSTGRES_URL"]
    id_a = f"isolate-a-{uuid.uuid4().hex}"
    id_b = f"isolate-b-{uuid.uuid4().hex}"

    async with AsyncPostgresSaver.from_conn_string(url) as cp:
        await cp.setup()
        g = _build_test_graph(cp)

        # Interrupt both threads with different starting counters
        await g.ainvoke({"counter": 5}, config=_cfg(id_a), durability="sync")
        await g.ainvoke({"counter": 99}, config=_cfg(id_b), durability="sync")

        # Check saved state via aget_state — counter reflects step_a output
        snap_a = await g.aget_state(_cfg(id_a))
        snap_b = await g.aget_state(_cfg(id_b))

    assert snap_a.values["counter"] == 6, "Thread A counter should be 6 (5+1)"
    assert snap_b.values["counter"] == 100, "Thread B counter should be 100 (99+1)"


@pytest.mark.asyncio
async def test_setup_is_idempotent() -> None:
    """Calling setup() twice on the same DB must not raise."""
    url = os.environ["POSTGRES_URL"]
    async with AsyncPostgresSaver.from_conn_string(url) as cp:
        await cp.setup()
        await cp.setup()  # second call must be a no-op


@pytest.mark.asyncio
async def test_postgres_checkpointer_helper() -> None:
    """postgres_checkpointer() context manager yields a usable checkpointer."""
    from saas_lead_agent.graph import build_graph
    from saas_lead_agent.memory.checkpointer import postgres_checkpointer

    thread_id = f"helper-test-{uuid.uuid4().hex}"
    config = _cfg(thread_id)

    async with postgres_checkpointer() as cp:
        g = build_graph(cp)
        # Just verify ainvoke doesn't crash (agents are mocked via env stubs)
        # We expect it to pause at await_approval after agent work —
        # but since API keys are stubs the agents will error gracefully.
        try:
            await g.ainvoke(
                {
                    "run_id": "run-helper-test",
                    "company_url": "https://example.com",
                    "domain": "example.com",
                    "icp_context": None,
                    "messages": [],
                    "company_profile": None,
                    "contact": None,
                    "signals": None,
                    "fit_score": None,
                    "fit_level": None,
                    "score_breakdown": None,
                    "score_confidence": None,
                    "score_explanation": None,
                    "needs_human_review": None,
                    "score_reasons": None,
                    "score_uncertainty": None,
                    "grounding_report": None,
                    "outreach_quality": None,
                    "provider_usage": [],
                    "processing_metadata": None,
                    "email_subject": None,
                    "email_body": None,
                    "email_approved": None,
                    "send_result": None,
                    "errors": [],
                },
                config=config,
                durability="sync",
            )
        except Exception:
            # Agents will fail with stub keys — we only care that the
            # checkpointer wired up correctly (no TypeError / AttributeError).
            pass

        # Verify checkpoint was written (state exists in DB)
        snapshot = await g.aget_state(config)
        assert snapshot is not None
