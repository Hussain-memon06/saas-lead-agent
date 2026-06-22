"""Focused tests for deterministic outreach-quality evaluation."""

from pathlib import Path

from saas_lead_agent.evaluation import (
    EvaluationCase,
    evaluate_outreach_case,
    load_evaluation_dataset,
)

_GOLDEN_DATASET = Path(__file__).resolve().parents[1] / "evals" / "golden_dataset.json"


def _outreach_case() -> EvaluationCase:
    dataset = load_evaluation_dataset(_GOLDEN_DATASET, expected_kind="golden")
    return next(case for case in dataset.cases if case.category == "outreach")


def test_outreach_seed_case_passes() -> None:
    result = evaluate_outreach_case(_outreach_case())

    assert result.passed is True
    assert result.evaluator_version == "outreach-v1"
    assert {metric.name for metric in result.metrics} == {
        "personalization_density",
        "spamminess",
        "outreach_quality_score",
        "cta_clarity",
        "prohibited_placeholder_detection",
        "safety_behavior",
    }
    assert all(metric.passed for metric in result.metrics)


def test_outreach_evaluator_fails_spam_and_placeholders() -> None:
    case = _outreach_case()
    modified_input = {
        **case.input,
        "draft": {
            "email_subject": "Quick question for [company]",
            "email_body": (
                "Hi {{name}}, this is a risk-free, 100% guaranteed offer for your company. "
                "Act now and call next week."
            ),
        },
    }

    result = evaluate_outreach_case(case.model_copy(update={"input": modified_input}))
    metrics = {metric.name: metric for metric in result.metrics}

    assert result.passed is False
    assert metrics["spamminess"].passed is False
    assert metrics["prohibited_placeholder_detection"].passed is False
    assert metrics["outreach_quality_score"].passed is False


def test_outreach_evaluator_reports_invalid_fixture() -> None:
    case = _outreach_case()
    result = evaluate_outreach_case(
        case.model_copy(update={"input": {**case.input, "draft": {"email_subject": "missing"}}})
    )

    assert result.passed is False
    assert result.failure_reasons == ["outreach fixture failed domain validation"]
