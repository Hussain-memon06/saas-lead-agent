"""Lead-research API endpoints — qualify, approve, reject."""

from typing import cast
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, status
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from saas_lead_agent.api.schemas import ApproveResponse, QualifyRequest, QualifyResponse
from saas_lead_agent.graph import build_graph_with_memory
from saas_lead_agent.state import LeadState

router = APIRouter()

# Module-level singleton so the graph (and its InMemorySaver) persists across
# requests within one process lifetime.  Re-created on each worker startup.
_graph = build_graph_with_memory()


def _domain_from_url(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc.removeprefix("www.")


def _config(thread_id: str) -> RunnableConfig:
    return cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})


async def _is_interrupted(thread_id: str) -> bool:
    """Return True if the graph for this thread is paused at an interrupt.

    A non-empty ``snapshot.next`` tuple means there are pending nodes — the
    graph stopped before completion (typically at ``await_approval``).
    """
    snapshot = await _graph.aget_state(_config(thread_id))
    return bool(snapshot.next)


@router.post(
    "/api/qualify",
    response_model=QualifyResponse,
    summary="Research and qualify a B2B SaaS company",
)
async def qualify(body: QualifyRequest) -> QualifyResponse:
    """Invoke the lead-research graph for a given company URL.

    Runs orchestrator → research subagents → dossier_writer → await_approval.
    The graph pauses at ``await_approval`` (interrupt) and the response carries
    ``interrupted=True``.  The client then calls ``/api/leads/{thread_id}/approve``
    or ``/reject`` to resume.

    Returns 422 if the URL is malformed; 500 on graph exceptions.
    """
    domain = _domain_from_url(body.url)
    thread_id = f"lead:{domain}"

    initial_state: LeadState = {
        "company_url": body.url,
        "domain": domain,
        "messages": [],
        "company_profile": None,
        "contact": None,
        "signals": None,
        "fit_score": None,
        "email_subject": None,
        "email_body": None,
        "email_approved": None,
        "send_result": None,
        "errors": [],
    }

    try:
        # durability="sync" required for interrupts per CLAUDE.md.
        result = await _graph.ainvoke(initial_state, config=_config(thread_id), durability="sync")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph execution failed: {exc}",
        ) from exc

    interrupted = await _is_interrupted(thread_id)

    return QualifyResponse(
        thread_id=thread_id,
        company_profile=result.get("company_profile"),
        contact=result.get("contact"),
        signals=result.get("signals"),
        fit_score=result.get("fit_score"),
        email_subject=result.get("email_subject"),
        email_body=result.get("email_body"),
        email_approved=result.get("email_approved"),
        send_result=result.get("send_result"),
        interrupted=interrupted,
        errors=result.get("errors", []),
    )


async def _resume(thread_id: str, decision: bool) -> ApproveResponse:
    """Shared logic for /approve and /reject — resume the graph with a bool."""
    try:
        result = await _graph.ainvoke(
            Command(resume=decision),
            config=_config(thread_id),
            durability="sync",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume failed: {exc}",
        ) from exc

    interrupted = await _is_interrupted(thread_id)

    return ApproveResponse(
        thread_id=thread_id,
        email_approved=result.get("email_approved"),
        send_result=result.get("send_result"),
        interrupted=interrupted,
        errors=result.get("errors", []),
    )


@router.post(
    "/api/leads/{thread_id}/approve",
    response_model=ApproveResponse,
    summary="Approve the drafted email and resume the graph",
)
async def approve(thread_id: str) -> ApproveResponse:
    """Resume an interrupted graph with ``Command(resume=True)``.

    The await_approval node returns ``email_approved=True``, send_email
    proceeds, and the graph runs to END.
    """
    return await _resume(thread_id, True)


@router.post(
    "/api/leads/{thread_id}/reject",
    response_model=ApproveResponse,
    summary="Reject the drafted email and resume the graph",
)
async def reject(thread_id: str) -> ApproveResponse:
    """Resume an interrupted graph with ``Command(resume=False)``.

    The await_approval node returns ``email_approved=False``, send_email
    marks the outcome ``"rejected"``, and the graph runs to END.
    """
    return await _resume(thread_id, False)
