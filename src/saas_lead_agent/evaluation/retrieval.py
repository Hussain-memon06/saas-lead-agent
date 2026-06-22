"""Deterministic adapter for existing retrieval-quality metrics."""

from time import perf_counter

from pydantic import ValidationError

from saas_lead_agent.evaluation.contracts import (
    CaseEvaluationResult,
    EvaluationCase,
    MetricName,
    MetricResult,
)
from saas_lead_agent.retrieval import evaluate_retrieval_quality
from saas_lead_agent.schemas import RetrievedChunk

_EVALUATOR_VERSION = "retrieval-v1"


def evaluate_retrieval_case(case: EvaluationCase) -> CaseEvaluationResult:
    """Evaluate already-ranked synthetic chunks without executing retrieval."""
    if case.category != "retrieval":
        raise ValueError("retrieval evaluator requires a retrieval case")
    started_at = perf_counter()
    try:
        raw_chunks = case.input.get("retrieved_chunks", [])
        if not isinstance(raw_chunks, list):
            raise TypeError("retrieved_chunks must be a list")
        chunks = [RetrievedChunk.model_validate(item) for item in raw_chunks]
    except (TypeError, ValidationError):
        return _failed_fixture_result(case, started_at)

    expected = case.expected
    quality = evaluate_retrieval_quality(
        chunks,
        expected_chunk_ids=set(expected.expected_chunk_ids or []),
        expected_source_uris=set(expected.expected_source_uris or []),
        k=expected.retrieval_k or 5,
    )
    metrics = [
        _threshold_metric("recall_at_k", quality.recall_at_k, expected.min_recall_at_k),
        _threshold_metric(
            "precision_at_k",
            quality.precision_at_k,
            expected.min_precision_at_k,
        ),
        _threshold_metric("mrr", quality.mrr, expected.min_mrr),
        _threshold_metric(
            "source_coverage",
            quality.source_coverage,
            expected.min_source_coverage,
        ),
    ]
    if expected.expected_chunk_ids:
        found = sum(quality.expected_chunk_retrieval.values())
        expected_count = len(quality.expected_chunk_retrieval)
        expected_ratio = found / expected_count if expected_count else 1.0
        metrics.append(
            MetricResult(
                name="expected_chunk_retrieval",
                value=round(expected_ratio, 6),
                threshold=1.0,
                comparison="gte",
                passed=found == expected_count,
                details={"expected_chunk_retrieval": quality.expected_chunk_retrieval},
            )
        )

    failed_names = [metric.name for metric in metrics if not metric.passed]
    failures = [f"retrieval metric failed: {name}" for name in failed_names]
    return CaseEvaluationResult(
        case_id=case.case_id,
        category=case.category,
        passed=not failures,
        metrics=metrics,
        failure_reasons=failures,
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
    )


def _threshold_metric(
    name: MetricName,
    value: float,
    threshold: float | None,
) -> MetricResult:
    if threshold is None:
        return MetricResult(name=name, value=value, passed=True)
    return MetricResult(
        name=name,
        value=value,
        threshold=threshold,
        comparison="gte",
        passed=value >= threshold,
    )


def _failed_fixture_result(case: EvaluationCase, started_at: float) -> CaseEvaluationResult:
    return CaseEvaluationResult(
        case_id=case.case_id,
        category=case.category,
        passed=False,
        metrics=[
            MetricResult(
                name="pydantic_validation_pass_rate",
                value=0.0,
                threshold=1.0,
                comparison="eq",
                passed=False,
            )
        ],
        failure_reasons=["retrieval fixture failed chunk validation"],
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
    )


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
