"""Tests for deterministic retrieval-quality metrics."""

import pytest

from saas_lead_agent.retrieval import evaluate_retrieval_quality
from saas_lead_agent.schemas import RetrievedChunk


def _chunk(
    chunk_id: str,
    *,
    source_uri: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        document_type="icp",
        trust_label="trusted_user",
        text=f"Chunk {chunk_id}",
        token_count=2,
        score=1.0,
        source_uri=source_uri,
    )


def test_evaluate_retrieval_quality_reports_core_metrics() -> None:
    result = evaluate_retrieval_quality(
        [
            _chunk("expected-1", source_uri="user://icp/a"),
            _chunk("unexpected", source_uri="user://icp/other"),
            _chunk("expected-2", source_uri="user://icp/b"),
        ],
        expected_chunk_ids={"expected-1", "expected-2", "missing"},
        expected_source_uris={"user://icp/a", "user://icp/b", "user://icp/missing"},
        k=3,
    )

    assert result.recall_at_k == 0.666667
    assert result.precision_at_k == 0.666667
    assert result.mrr == 1.0
    assert result.source_coverage == 0.666667
    assert result.expected_chunk_retrieval == {
        "expected-1": True,
        "expected-2": True,
        "missing": False,
    }
    assert result.retrieved_chunk_ids == ["expected-1", "unexpected", "expected-2"]


def test_evaluate_retrieval_quality_respects_k() -> None:
    result = evaluate_retrieval_quality(
        [
            _chunk("unexpected"),
            _chunk("expected-1"),
            _chunk("expected-2"),
        ],
        expected_chunk_ids={"expected-1", "expected-2"},
        k=2,
    )

    assert result.recall_at_k == 0.5
    assert result.precision_at_k == 0.5
    assert result.mrr == 0.5
    assert result.retrieved_chunk_ids == ["unexpected", "expected-1"]


def test_evaluate_retrieval_quality_rejects_invalid_k() -> None:
    with pytest.raises(ValueError, match="k"):
        evaluate_retrieval_quality([], expected_chunk_ids={"expected"}, k=0)
