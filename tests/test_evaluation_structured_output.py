"""Focused tests for deterministic structured-output evaluation."""

from pathlib import Path

from saas_lead_agent.evaluation import (
    EvaluationCase,
    EvaluationExpectation,
    evaluate_structured_output_case,
    load_evaluation_dataset,
)

_GOLDEN_DATASET = Path(__file__).resolve().parents[1] / "evals" / "golden_dataset.json"


def test_structured_output_seed_case_passes() -> None:
    dataset = load_evaluation_dataset(_GOLDEN_DATASET, expected_kind="golden")
    case = next(case for case in dataset.cases if case.category == "structured_output")

    result = evaluate_structured_output_case(case)

    assert result.passed is True
    assert result.failure_reasons == []
    assert {metric.name for metric in result.metrics} == {
        "json_validity",
        "missing_required_fields",
        "pydantic_validation_pass_rate",
        "invalid_enum_values",
    }


def test_structured_output_evaluator_reports_invalid_json() -> None:
    case = EvaluationCase(
        case_id="structured.invalid-json",
        category="structured_output",
        description="Malformed JSON should fail without leaking its contents.",
        input={"output": '{"secret": "do-not-echo"'},
        expected=EvaluationExpectation(required_fields=["thread_id"]),
    )

    result = evaluate_structured_output_case(case)

    assert result.passed is False
    assert result.failure_reasons == ["output is not a valid JSON object"]
    assert "do-not-echo" not in str(result)


def test_structured_output_evaluator_counts_invalid_enum_values() -> None:
    case = EvaluationCase(
        case_id="structured.invalid-send-result",
        category="structured_output",
        description="Invalid delivery states should fail LeadReport validation.",
        input={"output": {"send_result": "delivered"}},
        expected=EvaluationExpectation(output_schema="lead_report"),
    )

    result = evaluate_structured_output_case(case)
    metrics = {metric.name: metric for metric in result.metrics}

    assert result.passed is False
    assert metrics["pydantic_validation_pass_rate"].value == 0.0
    assert metrics["invalid_enum_values"].value == 1.0
