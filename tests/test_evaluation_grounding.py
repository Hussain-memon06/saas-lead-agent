"""Focused tests for deterministic grounding evaluation."""

from pathlib import Path

from saas_lead_agent.evaluation import (
    EvaluationCase,
    evaluate_grounding_case,
    load_evaluation_dataset,
)

_GOLDEN_DATASET = Path(__file__).resolve().parents[1] / "evals" / "golden_dataset.json"


def _grounding_case() -> EvaluationCase:
    dataset = load_evaluation_dataset(_GOLDEN_DATASET, expected_kind="golden")
    return next(case for case in dataset.cases if case.category == "grounding")


def test_grounding_seed_case_passes() -> None:
    result = evaluate_grounding_case(_grounding_case())

    assert result.passed is True
    assert result.evaluator_version == "grounding-v1"
    assert {metric.name for metric in result.metrics} == {
        "unsupported_claim_rate",
        "evidence_coverage",
        "missing_source_rate",
    }
    assert all(metric.passed for metric in result.metrics)


def test_grounding_evaluator_fails_uncited_claim_threshold() -> None:
    case = _grounding_case()
    modified_input = {
        **case.input,
        "draft": {
            "email_subject": "Quick question about Acme Corp",
            "email_body": (
                "Hi Alex, Acme Corp's funding looks timely. Could we discuss this next week? "
                "https://competitor.example.com"
            ),
        },
    }

    result = evaluate_grounding_case(case.model_copy(update={"input": modified_input}))

    assert result.passed is False
    assert "grounding metric failed: unsupported_claim_rate" in result.failure_reasons


def test_grounding_evaluator_reports_invalid_fixture() -> None:
    case = _grounding_case()
    result = evaluate_grounding_case(
        case.model_copy(update={"input": {**case.input, "profile": {"unexpected": "field"}}})
    )

    assert result.passed is False
    assert result.failure_reasons == ["grounding fixture failed domain validation"]
