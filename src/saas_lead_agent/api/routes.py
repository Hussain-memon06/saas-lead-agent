"""POST /api/qualify endpoint — invokes the lead-research graph."""

from typing import cast
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, status
from langchain_core.runnables import RunnableConfig

from saas_lead_agent.api.schemas import QualifyRequest, QualifyResponse
from saas_lead_agent.graph import build_graph_with_memory
from saas_lead_agent.state import LeadState

router = APIRouter()

# Module-level singleton so the graph (and its InMemorySaver) persists across
# requests within one process lifetime.  Re-created on each worker startup.
_graph = build_graph_with_memory()


def _domain_from_url(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc.removeprefix("www.")


@router.post(
    "/api/qualify",
    response_model=QualifyResponse,
    summary="Research and qualify a B2B SaaS company",
)
async def qualify(body: QualifyRequest) -> QualifyResponse:
    """Invoke the lead-research graph for a given company URL.

    Builds a ``LeadState``, runs the full orchestrator → subagent pipeline
    with ``InMemorySaver`` checkpointing, and returns the populated dossier.

    Returns 422 if the URL is malformed (validated by ``QualifyRequest``).
    Returns 500 if the graph raises an unexpected exception.
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
        "errors": [],
    }
    config: RunnableConfig = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})

    try:
        result = await _graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph execution failed: {exc}",
        ) from exc

    return QualifyResponse(
        thread_id=thread_id,
        company_profile=result.get("company_profile"),
        contact=result.get("contact"),
        signals=result.get("signals"),
        errors=result.get("errors", []),
    )
