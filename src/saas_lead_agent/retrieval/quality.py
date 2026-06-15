"""Deterministic retrieval-quality metrics for Phase 4 tests."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from saas_lead_agent.schemas import RetrievedChunk


@dataclass(frozen=True)
class RetrievalQualityResult:
    """Small retrieval metrics result used before the full eval harness exists."""

    recall_at_k: float
    precision_at_k: float
    mrr: float
    source_coverage: float
    expected_chunk_retrieval: dict[str, bool] = field(default_factory=dict)
    retrieved_chunk_ids: list[str] = field(default_factory=list)


def evaluate_retrieval_quality(
    retrieved_chunks: Sequence[RetrievedChunk],
    *,
    expected_chunk_ids: set[str],
    expected_source_uris: set[str] | None = None,
    k: int = 5,
) -> RetrievalQualityResult:
    """Calculate basic retrieval metrics from already-retrieved chunks."""
    if k < 1:
        raise ValueError("k must be at least 1")

    top_chunks = list(retrieved_chunks[:k])
    retrieved_ids = [chunk.chunk_id for chunk in top_chunks]
    retrieved_id_set = set(retrieved_ids)
    expected_found = expected_chunk_ids & retrieved_id_set
    expected_lookup = {
        chunk_id: chunk_id in retrieved_id_set for chunk_id in sorted(expected_chunk_ids)
    }

    recall = _ratio(len(expected_found), len(expected_chunk_ids), empty_value=1.0)
    precision = _ratio(len(expected_found), len(top_chunks), empty_value=0.0)
    source_coverage = _source_coverage(top_chunks, expected_source_uris or set())
    return RetrievalQualityResult(
        recall_at_k=recall,
        precision_at_k=precision,
        mrr=_mrr(retrieved_ids, expected_chunk_ids),
        source_coverage=source_coverage,
        expected_chunk_retrieval=expected_lookup,
        retrieved_chunk_ids=retrieved_ids,
    )


def _ratio(numerator: int, denominator: int, *, empty_value: float) -> float:
    if denominator == 0:
        return empty_value
    return round(numerator / denominator, 6)


def _mrr(retrieved_ids: list[str], expected_chunk_ids: set[str]) -> float:
    for index, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in expected_chunk_ids:
            return round(1 / index, 6)
    return 0.0


def _source_coverage(
    retrieved_chunks: list[RetrievedChunk],
    expected_source_uris: set[str],
) -> float:
    if not expected_source_uris:
        return 1.0
    retrieved_sources = {
        chunk.source_uri
        for chunk in retrieved_chunks
        if isinstance(chunk.source_uri, str) and chunk.source_uri
    }
    return _ratio(
        len(expected_source_uris & retrieved_sources),
        len(expected_source_uris),
        empty_value=1.0,
    )
