"""Focused tests for provider-free evaluation aggregation and dispatch."""

from pathlib import Path

import pytest

from saas_lead_agent.evaluation import (
    CaseEvaluationResult,
    EvaluationCase,
    EvaluationDataset,
    EvaluationExpectation,
    ExternalProviderCaseError,
    MetricResult,
    load_evaluation_dataset,
    run_evaluation_dataset,
)
from saas_lead_agent.evaluation.aggregate import aggregate_scoring_metrics

_EVALS_DIR = Path(__file__).resolve().parents[1] / "evals"


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("golden_dataset.json", 15),
        ("adversarial_dataset.json", 4),
        ("retrieval_dataset.json", 2),
    ],
)
def test_runner_dispatches_provider_free_seed_datasets(
    filename: str,
    expected_count: int,
) -> None:
    dataset = load_evaluation_dataset(_EVALS_DIR / filename)

    result = run_evaluation_dataset(dataset, run_id=f"test-{dataset.name}")

    assert result.total_cases == expected_count
    assert result.passed_cases == expected_count
    assert result.failed_cases == 0
    assert len(result.results) == expected_count
    assert result.total_tokens == 0
    assert result.estimated_cost_usd == 0.0


def test_runner_filters_categories_and_aggregates_scoring() -> None:
    dataset = load_evaluation_dataset(_EVALS_DIR / "golden_dataset.json")

    result = run_evaluation_dataset(dataset, categories={"scoring"}, run_id="scoring-only")

    assert result.total_cases == 5
    assert {metric.name for metric in result.aggregate_metrics} == {
        "classification_accuracy",
        "score_deviation",
        "false_positive_rate",
        "false_negative_rate",
    }
    assert all(metric.passed for metric in result.aggregate_metrics)


def test_runner_refuses_external_provider_cases() -> None:
    case = EvaluationCase(
        case_id="safety.external-provider",
        category="safety",
        description="External cases require a separate opt-in runner.",
        input={"url": "https://public.example.com"},
        expected=EvaluationExpectation(expected_graceful_failure=False),
        requires_external_provider=True,
    )
    dataset = EvaluationDataset(
        name="external",
        version="1",
        kind="adversarial",
        cases=[case],
    )

    with pytest.raises(ExternalProviderCaseError, match="safety.external-provider"):
        run_evaluation_dataset(dataset)


def test_scoring_aggregate_reports_false_positive_and_false_negative_rates() -> None:
    results = [
        _classification_result("score-fp", actual="high", expected="low"),
        _classification_result("score-fn", actual="medium", expected="high"),
    ]

    metrics = {metric.name: metric for metric in aggregate_scoring_metrics(results)}

    assert metrics["classification_accuracy"].value == 0.0
    assert metrics["false_positive_rate"].value == 1.0
    assert metrics["false_negative_rate"].value == 1.0
    assert metrics["false_positive_rate"].passed is False
    assert metrics["false_negative_rate"].passed is False


def _classification_result(
    case_id: str,
    *,
    actual: str,
    expected: str,
) -> CaseEvaluationResult:
    return CaseEvaluationResult(
        case_id=case_id,
        category="scoring",
        passed=False,
        evaluator_version="test",
        duration_ms=0,
        metrics=[
            MetricResult(
                name="classification_accuracy",
                value=0,
                threshold=1,
                comparison="eq",
                passed=False,
                details={"actual_fit_level": actual, "expected_fit_level": expected},
            ),
            MetricResult(name="score_deviation", value=1, passed=True),
        ],
    )
