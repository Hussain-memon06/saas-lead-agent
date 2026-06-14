"""Retrieval event construction helpers."""

from typing import Any

from saas_lead_agent.retrieval.chunking import hash_text
from saas_lead_agent.schemas import ContextBundle, RetrievalEvent, RetrievedChunk


def build_retrieval_event(
    *,
    run_id: str,
    thread_id: str,
    retrieval_node: str,
    query_text: str,
    top_k: int,
    context: ContextBundle,
    token_budget: int,
    request_id: str | None = None,
    user_id: str | None = None,
    filters: dict[str, Any] | None = None,
    query_metadata: dict[str, Any] | None = None,
) -> RetrievalEvent:
    """Create a sanitized retrieval event from selected context."""
    selected = [*context.trusted_chunks, *context.untrusted_chunks]
    query_hash = hash_text(query_text)
    return RetrievalEvent(
        event_id=f"{run_id}:{retrieval_node}:{query_hash[:12]}",
        run_id=run_id,
        thread_id=thread_id,
        request_id=request_id,
        user_id=user_id,
        retrieval_node=retrieval_node,
        query_text_hash=query_hash,
        query_metadata=query_metadata or {},
        filters=filters or {},
        top_k=top_k,
        selected_chunk_ids=[chunk.chunk_id for chunk in selected],
        scores=_scores(selected),
        reasons=_reasons(selected, context.omitted_reasons),
        token_budget=token_budget,
        tokens_selected=context.token_count,
    )


def _scores(chunks: list[RetrievedChunk]) -> dict[str, float]:
    return {chunk.chunk_id: chunk.score for chunk in chunks if chunk.score is not None}


def _reasons(
    chunks: list[RetrievedChunk],
    omitted_reasons: dict[str, str],
) -> dict[str, str]:
    reasons = {
        chunk.chunk_id: str(chunk.metadata.get("retrieval_reason") or "selected")
        for chunk in chunks
    }
    reasons.update(omitted_reasons)
    return reasons
