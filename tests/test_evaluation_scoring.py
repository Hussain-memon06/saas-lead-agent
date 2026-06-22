"""Focused tests for the deterministic scoring evaluator."""

from pathlib import Path

from saas_lead_agent.evaluation import (
    EvaluationCase,
    EvaluationExpectation,
    evaluate_scoring_case,
    load_evaluation_dataset,
)

_GOLDEN_DATASET = Path(__file__).resolve().parents[1] / "evals" / "golden_dataset.json"


def test_scoring_seed_cases_pass_deterministically() -> None:
    dataset = load_evaluation_dataset(_GOLDEN_DATASET, expected_kind="golden")
    scoring_cases = [case for case in dataset.cases if case.category == "scoring"]

    results = [evaluate_scoring_case(case) for case in scoring_cases]

    assert len(results) == 5
    assert all(result.passed for result in results)
    assert all(result.evaluator_version == "scoring-v1" for result in results)
    assert {metric.name for result in results for metric in result.metrics} == {
        "classification_accuracy",
        "score_deviation",
        "safety_behavior",
    }


def test_scoring_evaluator_reports_invalid_fixture_without_raising() -> None:
    case = EvaluationCase(
        case_id="scoring.invalid-profile",
        category="scoring",
        description="Invalid profile fixtures should fail safely.",
        input={"profile": {"unexpected": "field"}, "signals": []},
        expected=EvaluationExpectation(expected_fit_level="low"),
    )

    result = evaluate_scoring_case(case)

    assert result.passed is False
    assert result.failure_reasons == ["scoring fixture failed domain validation"]
    assert result.metrics[0].name == "pydantic_validation_pass_rate"
    assert result.metrics[0].value == 0.0
