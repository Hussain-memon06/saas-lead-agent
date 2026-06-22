"""Focused tests for Phase 7 evaluation contracts."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from saas_lead_agent.evaluation import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationExpectation,
    EvaluationRunResult,
    MetricResult,
)


def _scoring_case(case_id: str = "score.high-fit") -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        category="scoring",
        description="A strongly matched lead should classify as high fit.",
        input={"profile": {"industry": "B2B SaaS"}},
        expected=EvaluationExpectation(
            expected_fit_level="high",
            min_score=8,
            max_score=10,
        ),
        tags=["scoring", "high-fit"],
    )


def test_evaluation_case_defaults_to_provider_free() -> None:
    case = _scoring_case()

    assert case.requires_external_provider is False
    assert case.expected.expected_fit_level == "high"


def test_expectation_requires_expected_behavior() -> None:
    with pytest.raises(ValidationError, match="at least one expected behavior"):
        EvaluationExpectation()


def test_retrieval_expectation_requires_k() -> None:
    with pytest.raises(ValidationError, match="retrieval_k"):
        EvaluationExpectation(expected_chunk_ids=["chunk-1"])


def test_dataset_rejects_duplicate_case_ids() -> None:
    with pytest.raises(ValidationError, match="case IDs must be unique"):
        EvaluationDataset(
            name="golden",
            version="1",
            kind="golden",
            cases=[_scoring_case(), _scoring_case()],
        )


def test_metric_threshold_requires_comparison() -> None:
    with pytest.raises(ValidationError, match="defined together"):
        MetricResult(
            name="classification_accuracy",
            value=0.9,
            threshold=0.8,
            passed=True,
        )


def test_run_result_rejects_inconsistent_counts() -> None:
    started_at = datetime.now(UTC)
    with pytest.raises(ValidationError, match="must equal total_cases"):
        EvaluationRunResult(
            run_id="eval-run-1",
            dataset_name="golden",
            dataset_version="1",
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=1),
            total_cases=1,
            passed_cases=1,
            failed_cases=0,
            results=[],
        )
