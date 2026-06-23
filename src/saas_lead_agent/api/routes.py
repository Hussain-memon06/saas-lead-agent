"""Lead-research API endpoints: qualify, recover, approve, reject."""

import logging
import os
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, status
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from saas_lead_agent.api.auth import public_auth_metadata, resolve_auth_context
from saas_lead_agent.api.schemas import (
    ApproveResponse,
    LeadListResponse,
    LeadSummary,
    QualifyRequest,
    QualifyResponse,
    RunEventResponse,
    RunEventsResponse,
)
from saas_lead_agent.api.security import enforce_write_rate_limit
from saas_lead_agent.graph import build_graph_with_memory
from saas_lead_agent.memory.langfuse_handler import get_langfuse_handler
from saas_lead_agent.persistence import (
    InMemoryLeadRunRepository,
    LeadRunRepository,
    LeadRunSnapshot,
    RunEvent,
    RunStatus,
    can_read_snapshot,
)
from saas_lead_agent.schemas import AuthContext, ProcessingMetadata
from saas_lead_agent.state import LeadState

router = APIRouter()
logger = logging.getLogger(__name__)

# Module-level singletons are swapped by the FastAPI lifespan when Postgres is
# configured. The in-memory defaults keep local dev and tests cheap.
_graph = build_graph_with_memory()
_lead_store: LeadRunRepository = InMemoryLeadRunRepository()


def _domain_from_url(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc.removeprefix("www.")


def _config(
    thread_id: str,
    request_id: str | None = None,
    run_id: str | None = None,
) -> RunnableConfig:
    """Build LangGraph config with trace correlation metadata."""
    cfg: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "metadata": {"thread_id": thread_id},
    }
    if request_id is not None:
        cfg["metadata"]["request_id"] = request_id
    if run_id is not None:
        cfg["metadata"]["run_id"] = run_id
    handler = get_langfuse_handler()
    if handler is not None:
        cfg["callbacks"] = [handler]
    return cast(RunnableConfig, cfg)


async def _is_interrupted(
    thread_id: str,
    request_id: str | None = None,
    run_id: str | None = None,
) -> bool:
    """Return True when the graph has pending nodes for this thread."""
    snapshot = await _graph.aget_state(_config(thread_id, request_id, run_id))
    return bool(snapshot.next)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _status_from_state(result: dict[str, Any], interrupted: bool) -> RunStatus:
    if interrupted:
        return "interrupted"
    if result.get("errors") and not result.get("email_subject"):
        return "failed"
    return "completed"


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def _provider_usage_records(state: dict[str, Any]) -> list[dict[str, Any]]:
    provider_usage = state.get("provider_usage")
    if not isinstance(provider_usage, list):
        return []
    return [record for record in provider_usage if isinstance(record, dict)]


def _retrieval_event_records(state: dict[str, Any]) -> list[dict[str, object]]:
    retrieval_events = state.get("retrieval_events")
    if not isinstance(retrieval_events, list):
        return []
    return [_public_retrieval_event(event) for event in retrieval_events if isinstance(event, dict)]


def _tool_usage_records(state: dict[str, Any]) -> list[dict[str, object]]:
    tool_usage = state.get("tool_usage")
    if not isinstance(tool_usage, list):
        return []
    return [_public_tool_usage(record) for record in tool_usage if isinstance(record, dict)]


def _public_retrieval_event(event: dict[str, Any]) -> dict[str, object]:
    allowed_keys = {
        "event_id",
        "run_id",
        "thread_id",
        "request_id",
        "user_id",
        "retrieval_node",
        "query_text_hash",
        "query_metadata",
        "filters",
        "top_k",
        "selected_chunk_ids",
        "scores",
        "reasons",
        "token_budget",
        "tokens_selected",
        "created_at",
    }
    return {key: event[key] for key in allowed_keys if key in event}


def _public_tool_usage(record: dict[str, Any]) -> dict[str, object]:
    allowed_keys = {
        "node",
        "run_id",
        "thread_id",
        "request_id",
        "tool_name",
        "category",
        "provider",
        "status",
        "duration_ms",
        "attempt",
        "max_attempts",
        "timeout_ms",
        "input_hash",
        "output_count",
        "error_kind",
        "retryable",
        "provider_status_code",
        "provider_error_code",
        "has_idempotency_key",
    }
    return {key: record[key] for key in allowed_keys if key in record}


def _aggregate_provider_usage(provider_usage: list[dict[str, Any]]) -> dict[str, Any]:
    token_usage: dict[str, int] = {}
    node_timings: dict[str, float] = {}
    provider_status: dict[str, str] = {}
    models: set[str] = set()

    for index, record in enumerate(provider_usage):
        node = str(record.get("node") or f"unknown_{index}")
        model = record.get("model")
        if isinstance(model, str) and model:
            models.add(model)

        status_value = record.get("status")
        if isinstance(status_value, str) and status_value:
            provider_status[node] = status_value

        duration_ms = _nonnegative_float(record.get("duration_ms"))
        if duration_ms is not None:
            node_timings[f"node.{node}"] = duration_ms

        raw_usage = record.get("token_usage")
        if isinstance(raw_usage, dict):
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = _nonnegative_int(raw_usage.get(key))
                if value is not None:
                    token_usage[key] = token_usage.get(key, 0) + value

    if "total_tokens" not in token_usage:
        total = token_usage.get("input_tokens", 0) + token_usage.get("output_tokens", 0)
        if total:
            token_usage["total_tokens"] = total

    estimated_cost_usd, cost_breakdown = _estimate_cost_usd(token_usage)
    return {
        "model_used": ", ".join(sorted(models)) if models else None,
        "total_tokens": token_usage.get("total_tokens", 0),
        "estimated_cost_usd": estimated_cost_usd,
        "timings_ms": node_timings,
        "token_usage": token_usage,
        "cost_breakdown_usd": cost_breakdown,
        "provider_status": provider_status,
    }


def _aggregate_tool_usage(tool_usage: list[dict[str, object]]) -> dict[str, Any]:
    tool_status: dict[str, str] = {}
    tool_timings: dict[str, float] = {}

    for index, record in enumerate(tool_usage):
        tool_name = str(record.get("tool_name") or f"unknown_{index}")
        node = record.get("node")
        timing_key = (
            f"tool.{node}.{tool_name}"
            if isinstance(node, str) and node
            else f"tool.{tool_name}.{index}"
        )
        status_key = f"{node}.{tool_name}" if isinstance(node, str) and node else tool_name

        status_value = record.get("status")
        if isinstance(status_value, str) and status_value:
            tool_status[status_key] = status_value

        duration_ms = _nonnegative_float(record.get("duration_ms"))
        if duration_ms is not None:
            tool_timings[timing_key] = duration_ms

    return {"tool_status": tool_status, "tool_timings": tool_timings}


def _estimate_cost_usd(token_usage: dict[str, int]) -> tuple[float, dict[str, float]]:
    input_rate = _env_float("OPENAI_GPT_4O_MINI_INPUT_COST_PER_MILLION")
    output_rate = _env_float("OPENAI_GPT_4O_MINI_OUTPUT_COST_PER_MILLION")
    input_cost = (token_usage.get("input_tokens", 0) / 1_000_000) * input_rate
    output_cost = (token_usage.get("output_tokens", 0) / 1_000_000) * output_rate

    breakdown: dict[str, float] = {}
    if input_cost:
        breakdown["openai_input"] = round(input_cost, 8)
    if output_cost:
        breakdown["openai_output"] = round(output_cost, 8)
    return round(sum(breakdown.values()), 8), breakdown


def _env_float(name: str) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return 0.0
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return 0.0


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(value, 0)
    return None


def _nonnegative_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return max(round(float(value), 3), 0.0)
    return None


def _log_context(
    *,
    request_id: str | None,
    thread_id: str,
    run_id: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "thread_id": thread_id,
        "run_id": run_id,
        **extra,
    }


def _steps_from_state(state: dict[str, Any], interrupted: bool) -> list[str]:
    steps: list[str] = []
    retrieval_nodes = _retrieval_nodes_from_state(state)
    if "retrieve_icp_context" in retrieval_nodes:
        steps.append("retrieve_icp_context")
    if state.get("company_profile") is not None:
        steps.append("company_researcher")
    if state.get("contact") is not None:
        steps.append("contact_finder")
    if state.get("signals") is not None:
        steps.append("signal_detector")
    if "retrieve_similar_leads" in retrieval_nodes:
        steps.append("retrieve_similar_leads")
    if "retrieve_outreach_examples" in retrieval_nodes:
        steps.append("retrieve_outreach_examples")
    if state.get("email_subject") is not None or state.get("email_body") is not None:
        steps.append("dossier_writer")
    if interrupted:
        steps.append("await_approval")
    if state.get("send_result") is not None:
        steps.append("send_email")
    return steps


def _retrieval_nodes_from_state(state: dict[str, Any]) -> set[str]:
    nodes: set[str] = set()
    retrieval_events = state.get("retrieval_events")
    if not isinstance(retrieval_events, list):
        return nodes
    for event in retrieval_events:
        if isinstance(event, dict) and isinstance(event.get("retrieval_node"), str):
            nodes.add(event["retrieval_node"])
    return nodes


def _processing_metadata(
    *,
    run_id: str,
    thread_id: str,
    started_at: datetime,
    completed_at: datetime,
    timings_ms: dict[str, float],
    steps_completed: list[str],
    errors: list[str],
    provider_usage: list[dict[str, Any]] | None = None,
    retrieval_events: list[dict[str, object]] | None = None,
    tool_usage: list[dict[str, object]] | None = None,
    auth_metadata: dict[str, object] | None = None,
) -> dict[str, Any]:
    provider_summary = _aggregate_provider_usage(provider_usage or [])
    public_tool_usage = tool_usage or []
    tool_summary = _aggregate_tool_usage(public_tool_usage)
    auth_mode = auth_metadata.get("auth_mode") if auth_metadata else None
    auth_user_present = auth_metadata.get("auth_user_present") if auth_metadata else False
    combined_timings = {
        **timings_ms,
        **provider_summary["timings_ms"],
        **tool_summary["tool_timings"],
    }
    metadata = ProcessingMetadata(
        run_id=run_id,
        thread_id=thread_id,
        model_used=provider_summary["model_used"] or "gpt-4o-mini",
        total_tokens=provider_summary["total_tokens"],
        estimated_cost_usd=provider_summary["estimated_cost_usd"],
        timings_ms=combined_timings,
        token_usage=provider_summary["token_usage"],
        cost_breakdown_usd=provider_summary["cost_breakdown_usd"],
        provider_status=provider_summary["provider_status"],
        auth_mode=auth_mode if isinstance(auth_mode, str) else None,
        auth_user_present=auth_user_present is True,
        retrieval_events=retrieval_events or [],
        tool_events=public_tool_usage,
        tool_status=tool_summary["tool_status"],
        duration_seconds=max((completed_at - started_at).total_seconds(), 0.0),
        steps_completed=steps_completed,
        errors=errors,
        started_at=started_at,
        completed_at=completed_at,
    )
    return metadata.model_dump(mode="json")


def _response_from_state(
    *,
    state: dict[str, Any],
    request_id: str | None,
    thread_id: str,
    run_id: str,
    interrupted: bool,
) -> QualifyResponse:
    return QualifyResponse(
        request_id=request_id,
        run_id=run_id,
        thread_id=thread_id,
        company_profile=state.get("company_profile"),
        contact=state.get("contact"),
        signals=state.get("signals"),
        fit_score=state.get("fit_score"),
        fit_level=state.get("fit_level"),
        score_breakdown=state.get("score_breakdown"),
        score_confidence=state.get("score_confidence"),
        score_explanation=state.get("score_explanation"),
        needs_human_review=state.get("needs_human_review"),
        score_reasons=state.get("score_reasons"),
        score_uncertainty=state.get("score_uncertainty"),
        grounding_report=state.get("grounding_report"),
        outreach_quality=state.get("outreach_quality"),
        processing_metadata=state.get("processing_metadata"),
        email_subject=state.get("email_subject"),
        email_body=state.get("email_body"),
        email_approved=state.get("email_approved"),
        send_result=state.get("send_result"),
        delivery_idempotency_key=state.get("delivery_idempotency_key"),
        message_id=state.get("message_id"),
        sent_at=state.get("sent_at"),
        interrupted=interrupted,
        errors=state.get("errors", []),
    )


def _lead_summary_from_snapshot(snapshot: LeadRunSnapshot) -> LeadSummary:
    result = snapshot.result
    profile = result.get("company_profile")
    processing_metadata = result.get("processing_metadata")
    profile_data = profile if isinstance(profile, dict) else {}
    metadata = processing_metadata if isinstance(processing_metadata, dict) else {}

    return LeadSummary(
        request_id=snapshot.request_id,
        run_id=snapshot.run_id,
        thread_id=snapshot.thread_id,
        domain=snapshot.domain,
        company_url=snapshot.company_url,
        company_name=profile_data.get("name"),
        status=snapshot.status,
        fit_score=result.get("fit_score"),
        fit_level=result.get("fit_level"),
        score_confidence=result.get("score_confidence"),
        needs_human_review=result.get("needs_human_review"),
        interrupted=bool(result.get("interrupted", snapshot.status == "interrupted")),
        send_result=result.get("send_result"),
        total_tokens=int(metadata.get("total_tokens") or 0),
        estimated_cost_usd=float(metadata.get("estimated_cost_usd") or 0.0),
        duration_seconds=float(metadata.get("duration_seconds") or 0.0),
        created_at=snapshot.created_at.isoformat(),
        updated_at=snapshot.updated_at.isoformat(),
    )


def _public_event_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "status",
        "interrupted",
        "send_result",
        "delivery_idempotency_key",
        "timings_ms",
        "total_tokens",
        "estimated_cost_usd",
        "token_usage",
        "cost_breakdown_usd",
        "provider_status",
        "auth_mode",
        "auth_user_present",
        "retrieval_events",
        "tool_events",
        "tool_status",
        "error_type",
    }
    public: dict[str, Any] = {}
    for key in allowed_keys:
        if key not in metadata:
            continue
        if key == "retrieval_events" and isinstance(metadata[key], list):
            public[key] = [
                _public_retrieval_event(event) for event in metadata[key] if isinstance(event, dict)
            ]
            continue
        if key == "tool_events" and isinstance(metadata[key], list):
            public[key] = [
                _public_tool_usage(record) for record in metadata[key] if isinstance(record, dict)
            ]
            continue
        public[key] = metadata[key]
    return public


def _event_response(event: RunEvent) -> RunEventResponse:
    return RunEventResponse(
        run_id=event.run_id,
        thread_id=event.thread_id,
        event_type=event.event_type,
        metadata=_public_event_metadata(event.metadata),
        request_id=event.request_id,
        created_at=event.created_at.isoformat(),
    )


async def _save_snapshot(
    *,
    response: QualifyResponse,
    company_url: str,
    domain: str,
    status_value: RunStatus,
    owner_user_id: str | None = None,
) -> None:
    result = response.model_dump()
    if owner_user_id is not None:
        result["user_id"] = owner_user_id
    await _lead_store.save_snapshot(
        LeadRunSnapshot(
            run_id=response.run_id or str(uuid4()),
            thread_id=response.thread_id,
            domain=domain,
            company_url=company_url,
            status=status_value,
            request_id=response.request_id,
            result=result,
        )
    )


async def _record_event(
    *,
    run_id: str,
    thread_id: str,
    event_type: str,
    request_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await _lead_store.record_event(
        RunEvent(
            run_id=run_id,
            thread_id=thread_id,
            event_type=event_type,
            request_id=request_id,
            metadata=metadata or {},
        )
    )


def _initial_state(
    *,
    run_id: str,
    company_url: str,
    domain: str,
    icp_context: dict[str, Any] | None,
) -> LeadState:
    return {
        "run_id": run_id,
        "company_url": company_url,
        "domain": domain,
        "icp_context": icp_context,
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
        "retrieval_context": None,
        "retrieval_events": [],
        "tool_usage": [],
        "provider_usage": [],
        "processing_metadata": None,
        "email_subject": None,
        "email_body": None,
        "email_approved": None,
        "send_result": None,
        "delivery_idempotency_key": None,
        "message_id": None,
        "sent_at": None,
        "errors": [],
    }


@router.post(
    "/api/qualify",
    response_model=QualifyResponse,
    summary="Research and qualify a B2B SaaS company",
)
async def qualify(body: QualifyRequest, request: Request) -> QualifyResponse:
    """Invoke the lead-research graph for a given company URL."""
    domain = _domain_from_url(body.url)
    thread_id = f"lead:{domain}"
    request_id = _request_id(request)
    auth = await resolve_auth_context(request)
    await enforce_write_rate_limit(action="qualify", auth=auth, request=request)
    auth_metadata = public_auth_metadata(auth)
    run_id = str(uuid4())
    started_at = datetime.now(UTC)
    api_start = perf_counter()
    graph_duration_ms = 0.0

    logger.info(
        "qualify_started",
        extra=_log_context(
            request_id=request_id,
            thread_id=thread_id,
            run_id=run_id,
            domain=domain,
        ),
    )

    try:
        graph_start = perf_counter()
        result = await _graph.ainvoke(
            _initial_state(
                run_id=run_id,
                company_url=body.url,
                domain=domain,
                icp_context=body.icp_context,
            ),
            config=_config(thread_id, request_id, run_id),
            durability="sync",
        )
        graph_duration_ms = _elapsed_ms(graph_start)
    except Exception as exc:
        completed_at = datetime.now(UTC)
        processing_metadata = _processing_metadata(
            run_id=run_id,
            thread_id=thread_id,
            started_at=started_at,
            completed_at=completed_at,
            timings_ms={
                "graph": graph_duration_ms or _elapsed_ms(api_start),
                "api_total": _elapsed_ms(api_start),
            },
            steps_completed=[],
            errors=[f"Graph execution failed: {exc}"],
            auth_metadata=auth_metadata,
        )
        failed_response = _response_from_state(
            state={
                "errors": [f"Graph execution failed: {exc}"],
                "processing_metadata": processing_metadata,
            },
            request_id=request_id,
            thread_id=thread_id,
            run_id=run_id,
            interrupted=False,
        )
        await _save_snapshot(
            response=failed_response,
            company_url=body.url,
            domain=domain,
            status_value="failed",
            owner_user_id=auth.user_id,
        )
        await _record_event(
            run_id=run_id,
            thread_id=thread_id,
            event_type="qualify_failed",
            request_id=request_id,
            metadata={
                "error_type": type(exc).__name__,
                **auth_metadata,
                "timings_ms": processing_metadata["timings_ms"],
            },
        )
        logger.exception(
            "qualify_failed",
            extra=_log_context(
                request_id=request_id,
                thread_id=thread_id,
                run_id=run_id,
                domain=domain,
                error_type=type(exc).__name__,
                timings_ms=processing_metadata["timings_ms"],
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph execution failed: {exc}",
        ) from exc

    interrupt_start = perf_counter()
    interrupted = await _is_interrupted(thread_id, request_id, run_id)
    interrupt_duration_ms = _elapsed_ms(interrupt_start)
    completed_at = datetime.now(UTC)
    response_run_id = str(result.get("run_id") or run_id)
    processing_metadata = _processing_metadata(
        run_id=response_run_id,
        thread_id=thread_id,
        started_at=started_at,
        completed_at=completed_at,
        timings_ms={
            "graph": graph_duration_ms,
            "interrupt_check": interrupt_duration_ms,
            "api_total": _elapsed_ms(api_start),
        },
        steps_completed=_steps_from_state(result, interrupted),
        errors=[str(error) for error in result.get("errors", [])],
        provider_usage=_provider_usage_records(result),
        retrieval_events=_retrieval_event_records(result),
        tool_usage=_tool_usage_records(result),
        auth_metadata=auth_metadata,
    )
    result = {**result, "processing_metadata": processing_metadata}
    response = _response_from_state(
        state=result,
        request_id=request_id,
        thread_id=thread_id,
        run_id=response_run_id,
        interrupted=interrupted,
    )
    status_value = _status_from_state(result, interrupted)
    await _save_snapshot(
        response=response,
        company_url=body.url,
        domain=domain,
        status_value=status_value,
        owner_user_id=auth.user_id,
    )
    await _record_event(
        run_id=response.run_id or run_id,
        thread_id=thread_id,
        event_type="qualify_completed",
        request_id=request_id,
        metadata={
            "status": status_value,
            "interrupted": interrupted,
            "timings_ms": processing_metadata["timings_ms"],
            "total_tokens": processing_metadata["total_tokens"],
            "estimated_cost_usd": processing_metadata["estimated_cost_usd"],
            "token_usage": processing_metadata["token_usage"],
            "cost_breakdown_usd": processing_metadata["cost_breakdown_usd"],
            "provider_status": processing_metadata["provider_status"],
            "auth_mode": processing_metadata["auth_mode"],
            "auth_user_present": processing_metadata["auth_user_present"],
            "retrieval_events": processing_metadata["retrieval_events"],
            "tool_events": processing_metadata["tool_events"],
            "tool_status": processing_metadata["tool_status"],
        },
    )
    logger.info(
        "qualify_completed",
        extra=_log_context(
            request_id=request_id,
            thread_id=thread_id,
            run_id=response.run_id or run_id,
            domain=domain,
            status=status_value,
            interrupted=interrupted,
            timings_ms=processing_metadata["timings_ms"],
        ),
    )
    return response


@router.get(
    "/api/leads",
    response_model=LeadListResponse,
    summary="List recent stored lead runs",
)
async def list_leads(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
) -> LeadListResponse:
    """Return recent app-owned lead summaries without draft/contact PII."""
    auth = await resolve_auth_context(request)
    if "admin" in auth.roles:
        visible_snapshots = await _lead_store.list_snapshots(limit)
    else:
        visible_snapshots = await _lead_store.list_snapshots_for_owner(auth.user_id, limit)
    return LeadListResponse(
        request_id=_request_id(request),
        leads=[_lead_summary_from_snapshot(snapshot) for snapshot in visible_snapshots],
    )


@router.get(
    "/api/leads/{thread_id}",
    response_model=QualifyResponse,
    summary="Return the latest stored lead dossier state",
)
async def get_lead(thread_id: str, request: Request) -> QualifyResponse:
    """Recover the latest app-owned lead snapshot by LangGraph thread ID."""
    auth = await resolve_auth_context(request)
    snapshot = await _lead_store.get_by_thread_id(thread_id)
    if snapshot is None or not can_read_snapshot(auth, snapshot).allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored lead run found for thread_id={thread_id}",
        )

    return _response_from_state(
        state=snapshot.result,
        request_id=_request_id(request),
        thread_id=snapshot.thread_id,
        run_id=snapshot.run_id,
        interrupted=bool(snapshot.result.get("interrupted", snapshot.status == "interrupted")),
    )


@router.get(
    "/api/leads/{thread_id}/events",
    response_model=RunEventsResponse,
    summary="Return audit-style run events for a lead",
)
async def get_lead_events(thread_id: str, request: Request) -> RunEventsResponse:
    """Return sanitized lifecycle events for the stored lead thread."""
    auth = await resolve_auth_context(request)
    snapshot = await _lead_store.get_by_thread_id(thread_id)
    if snapshot is None or not can_read_snapshot(auth, snapshot).allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored lead run found for thread_id={thread_id}",
        )
    events = await _lead_store.list_events(thread_id)
    return RunEventsResponse(
        request_id=_request_id(request),
        thread_id=thread_id,
        events=[_event_response(event) for event in events],
    )


async def _resume(
    thread_id: str,
    decision: bool,
    request_id: str | None = None,
    auth: AuthContext | None = None,
) -> ApproveResponse:
    """Shared logic for /approve and /reject: resume the graph with a bool."""
    auth = auth or AuthContext()
    snapshot = await _lead_store.get_by_thread_id(thread_id)
    if snapshot is None or not can_read_snapshot(auth, snapshot).allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored lead run found for thread_id={thread_id}",
        )
    auth_metadata = public_auth_metadata(auth)
    owner_user_id = auth.user_id
    if snapshot is not None and isinstance(snapshot.result.get("user_id"), str):
        owner_user_id = snapshot.result["user_id"]
    run_id = snapshot.run_id if snapshot is not None else str(uuid4())
    started_at = datetime.now(UTC)
    api_start = perf_counter()
    graph_duration_ms = 0.0

    logger.info(
        "lead_resume_started",
        extra=_log_context(
            request_id=request_id,
            thread_id=thread_id,
            run_id=run_id,
            decision="approve" if decision else "reject",
        ),
    )

    try:
        graph_start = perf_counter()
        result = await _graph.ainvoke(
            Command(resume=decision),
            config=_config(thread_id, request_id, run_id),
            durability="sync",
        )
        graph_duration_ms = _elapsed_ms(graph_start)
    except Exception as exc:
        timings_ms = {
            "graph": graph_duration_ms or _elapsed_ms(api_start),
            "api_total": _elapsed_ms(api_start),
        }
        logger.exception(
            "lead_resume_failed",
            extra=_log_context(
                request_id=request_id,
                thread_id=thread_id,
                run_id=run_id,
                decision="approve" if decision else "reject",
                error_type=type(exc).__name__,
                timings_ms=timings_ms,
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume failed: {exc}",
        ) from exc

    interrupt_start = perf_counter()
    interrupted = await _is_interrupted(thread_id, request_id, run_id)
    interrupt_duration_ms = _elapsed_ms(interrupt_start)
    completed_at = datetime.now(UTC)
    response_run_id = str(result.get("run_id") or run_id)
    processing_metadata = _processing_metadata(
        run_id=response_run_id,
        thread_id=thread_id,
        started_at=started_at,
        completed_at=completed_at,
        timings_ms={
            "graph": graph_duration_ms,
            "interrupt_check": interrupt_duration_ms,
            "api_total": _elapsed_ms(api_start),
        },
        steps_completed=_steps_from_state(result, interrupted),
        errors=[str(error) for error in result.get("errors", [])],
        provider_usage=_provider_usage_records(result),
        retrieval_events=_retrieval_event_records(result),
        tool_usage=_tool_usage_records(result),
        auth_metadata=auth_metadata,
    )
    result = {**result, "processing_metadata": processing_metadata}
    response_state = _response_from_state(
        state=result,
        request_id=request_id,
        thread_id=thread_id,
        run_id=response_run_id,
        interrupted=interrupted,
    )
    status_value = _status_from_state(result, interrupted)

    if snapshot is not None or result.get("company_url"):
        company_url = str(
            result.get("company_url") or (snapshot.company_url if snapshot is not None else "")
        )
        domain = str(
            result.get("domain")
            or (snapshot.domain if snapshot is not None else thread_id.removeprefix("lead:"))
        )
        await _save_snapshot(
            response=response_state,
            company_url=company_url,
            domain=domain,
            status_value=status_value,
            owner_user_id=owner_user_id,
        )

    await _record_event(
        run_id=response_state.run_id or run_id,
        thread_id=thread_id,
        event_type="lead_approved" if decision else "lead_rejected",
        request_id=request_id,
        metadata={
            "status": status_value,
            "send_result": result.get("send_result"),
            "delivery_idempotency_key": result.get("delivery_idempotency_key"),
            "interrupted": interrupted,
            "timings_ms": processing_metadata["timings_ms"],
            "total_tokens": processing_metadata["total_tokens"],
            "estimated_cost_usd": processing_metadata["estimated_cost_usd"],
            "token_usage": processing_metadata["token_usage"],
            "cost_breakdown_usd": processing_metadata["cost_breakdown_usd"],
            "provider_status": processing_metadata["provider_status"],
            "auth_mode": processing_metadata["auth_mode"],
            "auth_user_present": processing_metadata["auth_user_present"],
            "retrieval_events": processing_metadata["retrieval_events"],
            "tool_events": processing_metadata["tool_events"],
            "tool_status": processing_metadata["tool_status"],
        },
    )
    logger.info(
        "lead_resume_completed",
        extra=_log_context(
            request_id=request_id,
            thread_id=thread_id,
            run_id=response_state.run_id or run_id,
            decision="approve" if decision else "reject",
            status=status_value,
            send_result=result.get("send_result"),
            interrupted=interrupted,
            timings_ms=processing_metadata["timings_ms"],
        ),
    )

    return ApproveResponse(
        request_id=request_id,
        run_id=response_state.run_id,
        thread_id=thread_id,
        email_approved=result.get("email_approved"),
        send_result=result.get("send_result"),
        delivery_idempotency_key=result.get("delivery_idempotency_key"),
        message_id=result.get("message_id"),
        sent_at=result.get("sent_at"),
        processing_metadata=result.get("processing_metadata"),
        interrupted=interrupted,
        errors=result.get("errors", []),
    )


@router.post(
    "/api/leads/{thread_id}/approve",
    response_model=ApproveResponse,
    summary="Approve the drafted email and resume the graph",
)
async def approve(thread_id: str, request: Request) -> ApproveResponse:
    """Resume an interrupted graph with ``Command(resume=True)``."""
    auth = await resolve_auth_context(request)
    await enforce_write_rate_limit(action="decision", auth=auth, request=request)
    return await _resume(
        thread_id,
        True,
        _request_id(request),
        auth,
    )


@router.post(
    "/api/leads/{thread_id}/reject",
    response_model=ApproveResponse,
    summary="Reject the drafted email and resume the graph",
)
async def reject(thread_id: str, request: Request) -> ApproveResponse:
    """Resume an interrupted graph with ``Command(resume=False)``."""
    auth = await resolve_auth_context(request)
    await enforce_write_rate_limit(action="decision", auth=auth, request=request)
    return await _resume(
        thread_id,
        False,
        _request_id(request),
        auth,
    )
