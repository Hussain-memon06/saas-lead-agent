"""Dependency-free retrieval nodes for the Phase 4 graph milestone."""

from __future__ import annotations

import json
from typing import Any, cast

from saas_lead_agent.retrieval import (
    InMemoryRetrievalRepository,
    assemble_context_bundle,
    build_retrieval_event,
    hash_text,
)
from saas_lead_agent.schemas import ContextBundle, DocumentType, KnowledgeDocument
from saas_lead_agent.state import LeadState

_ICP_NODE = "retrieve_icp_context"
_SIMILAR_NODE = "retrieve_similar_leads"
_OUTREACH_NODE = "retrieve_outreach_examples"
_ICP_TOP_K = 3
_ICP_TOKEN_BUDGET = 600
_SIMILAR_TOP_K = 4
_SIMILAR_TOKEN_BUDGET = 800
_OUTREACH_TOP_K = 3
_OUTREACH_TOKEN_BUDGET = 500


async def retrieve_icp_context(state: LeadState) -> dict[str, Any]:
    """Retrieve user-owned ICP context from the submitted ICP payload.

    This is intentionally provider-free. It turns the current request's ICP
    fields into a transient document, uses the deterministic lexical repository,
    and appends a sanitized retrieval event. No vectors, embeddings, queues, or
    external services are involved.
    """
    try:
        icp_context = state.get("icp_context")
        query = _icp_query(state)
        filters = {
            "document_types": ["icp", "offer"],
            "trust_labels": ["trusted_user"],
            "mode": "request_icp_transient",
        }

        if not isinstance(icp_context, dict) or not icp_context:
            bundle = ContextBundle()
            event = build_retrieval_event(
                run_id=_run_id(state),
                thread_id=_thread_id(state),
                retrieval_node=_ICP_NODE,
                query_text=query,
                top_k=_ICP_TOP_K,
                context=bundle,
                token_budget=_ICP_TOKEN_BUDGET,
                filters=filters,
                query_metadata={
                    "query_kind": "icp_context",
                    "status": "skipped",
                    "reason": "missing_icp_context",
                },
            )
            return _retrieval_update(
                state,
                key="icp",
                bundle=bundle,
                event=event.model_dump(mode="json"),
                status="skipped",
                reason="missing_icp_context",
            )

        documents = _request_context_documents(icp_context)
        if not documents:
            bundle = ContextBundle()
            event = build_retrieval_event(
                run_id=_run_id(state),
                thread_id=_thread_id(state),
                retrieval_node=_ICP_NODE,
                query_text=query,
                top_k=_ICP_TOP_K,
                context=bundle,
                token_budget=_ICP_TOKEN_BUDGET,
                filters=filters,
                query_metadata={
                    "query_kind": "icp_context",
                    "status": "skipped",
                    "reason": "empty_icp_context",
                },
            )
            return _retrieval_update(
                state,
                key="icp",
                bundle=bundle,
                event=event.model_dump(mode="json"),
                status="skipped",
                reason="empty_icp_context",
            )

        repository = InMemoryRetrievalRepository()
        run_id = _run_id(state)
        for document_type, text in documents.items():
            document = KnowledgeDocument(
                document_id=f"{run_id}:{document_type}:request",
                document_type=cast(DocumentType, document_type),
                trust_label="trusted_user",
                title=f"Submitted {document_type} context",
                source_uri=f"user://{document_type}/request",
                content_hash=hash_text(text),
                metadata={"source": "qualify_request"},
            )
            repository.ingest_document(
                document=document,
                text=text,
                target_tokens=250,
                overlap_tokens=25,
            )
        chunks = repository.search(
            query,
            top_k=_ICP_TOP_K,
            document_types={"icp", "offer"},
            trust_labels={"trusted_user"},
        )
        bundle = assemble_context_bundle(chunks, token_budget=_ICP_TOKEN_BUDGET)
        event = build_retrieval_event(
            run_id=_run_id(state),
            thread_id=_thread_id(state),
            retrieval_node=_ICP_NODE,
            query_text=query,
            top_k=_ICP_TOP_K,
            context=bundle,
            token_budget=_ICP_TOKEN_BUDGET,
            filters=filters,
            query_metadata={
                "query_kind": "icp_context",
                "status": "completed",
                "source": "qualify_request",
            },
        )
        return _retrieval_update(
            state,
            key="icp",
            bundle=bundle,
            event=event.model_dump(mode="json"),
            status="completed",
        )
    except Exception as exc:
        return {"errors": [f"{_ICP_NODE}: retrieval failed - {exc}"]}


async def retrieve_similar_leads(state: LeadState) -> dict[str, Any]:
    """Add a no-provider similar-leads retrieval event.

    There is no persisted lead-example/prior-dossier corpus yet. This node
    still establishes the graph insertion point, deterministic query shape, and
    sanitized event contract without inventing storage or dependencies.
    """
    try:
        query = _similar_leads_query(state)
        bundle = ContextBundle()
        event = build_retrieval_event(
            run_id=_run_id(state),
            thread_id=_thread_id(state),
            retrieval_node=_SIMILAR_NODE,
            query_text=query,
            top_k=_SIMILAR_TOP_K,
            context=bundle,
            token_budget=_SIMILAR_TOKEN_BUDGET,
            filters={
                "document_types": ["lead_example", "prior_dossier"],
                "trust_labels": ["trusted_user", "trusted_generated"],
                "mode": "no_provider_no_corpus",
            },
            query_metadata={
                "query_kind": "similar_leads",
                "status": "skipped",
                "reason": "no_lead_example_corpus",
            },
        )
        return _retrieval_update(
            state,
            key="similar_leads",
            bundle=bundle,
            event=event.model_dump(mode="json"),
            status="skipped",
            reason="no_lead_example_corpus",
        )
    except Exception as exc:
        return {"errors": [f"{_SIMILAR_NODE}: retrieval failed - {exc}"]}


async def retrieve_outreach_examples(state: LeadState) -> dict[str, Any]:
    """Add a no-provider outreach-examples retrieval event."""
    try:
        query = _outreach_examples_query(state)
        bundle = ContextBundle()
        event = build_retrieval_event(
            run_id=_run_id(state),
            thread_id=_thread_id(state),
            retrieval_node=_OUTREACH_NODE,
            query_text=query,
            top_k=_OUTREACH_TOP_K,
            context=bundle,
            token_budget=_OUTREACH_TOKEN_BUDGET,
            filters={
                "document_types": ["outreach_example"],
                "trust_labels": ["trusted_user", "trusted_generated"],
                "mode": "no_provider_no_corpus",
            },
            query_metadata={
                "query_kind": "outreach_examples",
                "status": "skipped",
                "reason": "no_outreach_example_corpus",
            },
        )
        return _retrieval_update(
            state,
            key="outreach_examples",
            bundle=bundle,
            event=event.model_dump(mode="json"),
            status="skipped",
            reason="no_outreach_example_corpus",
        )
    except Exception as exc:
        return {"errors": [f"{_OUTREACH_NODE}: retrieval failed - {exc}"]}


def _retrieval_update(
    state: LeadState,
    *,
    key: str,
    bundle: ContextBundle,
    event: dict[str, Any],
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    existing = state.get("retrieval_context")
    context = dict(existing) if isinstance(existing, dict) else {}
    context[key] = {
        **bundle.model_dump(mode="json"),
        "status": status,
        "reason": reason,
    }
    return {
        "retrieval_context": context,
        "retrieval_events": [event],
    }


def _run_id(state: LeadState) -> str:
    value = state.get("run_id")
    return value if isinstance(value, str) and value else "run:unknown"


def _thread_id(state: LeadState) -> str:
    domain = state.get("domain")
    return f"lead:{domain}" if isinstance(domain, str) and domain else "lead:unknown"


def _icp_query(state: LeadState) -> str:
    icp_context = state.get("icp_context")
    if isinstance(icp_context, dict) and icp_context:
        return "\n".join(_request_context_documents(icp_context).values())
    domain = state.get("domain")
    return f"icp context for {domain}" if isinstance(domain, str) else "icp context"


def _request_context_documents(icp_context: dict[str, Any]) -> dict[str, str]:
    documents: dict[str, str] = {}
    icp_text = _icp_document_text(icp_context)
    offer_text = _offer_document_text(icp_context)
    if icp_text:
        documents["icp"] = icp_text
    if offer_text:
        documents["offer"] = offer_text
    return documents


def _icp_document_text(icp_context: dict[str, Any]) -> str:
    ordered_keys = (
        "target_industries",
        "target_stages",
        "target_geographies",
        "target_employees",
        "must_have_signals",
        "red_flags",
    )
    parts: list[str] = []
    for key in ordered_keys:
        value = icp_context.get(key)
        rendered = _render_value(value)
        if rendered:
            parts.append(f"{key}: {rendered}")
    for key in sorted(set(icp_context) - set(ordered_keys)):
        rendered = _render_value(icp_context.get(key))
        if rendered:
            parts.append(f"{key}: {rendered}")
    return "\n".join(parts)


def _offer_document_text(icp_context: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("seller_name", "offering", "value_proposition"):
        rendered = _render_value(icp_context.get(key))
        if rendered:
            parts.append(f"{key}: {rendered}")
    return "\n".join(parts)


def _similar_leads_query(state: LeadState) -> str:
    profile = state.get("company_profile")
    signals = state.get("signals")
    parts: list[str] = []
    if isinstance(profile, dict):
        for key in ("name", "tagline", "funding_stage", "hq", "employees_estimate"):
            rendered = _render_value(profile.get(key))
            if rendered:
                parts.append(f"{key}: {rendered}")
        for key in ("products", "notable_customers"):
            rendered = _render_value(profile.get(key))
            if rendered:
                parts.append(f"{key}: {rendered}")
    if isinstance(signals, list):
        for signal in signals[:5]:
            if isinstance(signal, dict):
                rendered = _render_value(
                    {
                        "signal_type": signal.get("signal_type"),
                        "details": signal.get("details"),
                    }
                )
                if rendered:
                    parts.append(rendered)
    return "\n".join(parts) if parts else "similar lead examples"


def _outreach_examples_query(state: LeadState) -> str:
    parts = [_similar_leads_query(state)]
    contact = state.get("contact")
    if isinstance(contact, dict):
        for key in ("title", "source"):
            rendered = _render_value(contact.get(key))
            if rendered:
                parts.append(f"contact_{key}: {rendered}")
    retrieval_context = state.get("retrieval_context")
    if isinstance(retrieval_context, dict):
        icp_context = retrieval_context.get("icp")
        if isinstance(icp_context, dict):
            chunk_ids = [
                str(chunk.get("chunk_id"))
                for chunk in icp_context.get("trusted_chunks", [])
                if isinstance(chunk, dict) and chunk.get("chunk_id")
            ]
            if chunk_ids:
                parts.append(f"icp_chunk_ids: {', '.join(chunk_ids)}")
    return "\n".join(part for part in parts if part)


def _render_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value).strip()
