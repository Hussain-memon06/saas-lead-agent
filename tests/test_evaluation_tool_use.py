"""Focused tests for offline recorded tool-use evaluation."""

from pathlib import Path

from saas_lead_agent.evaluation import (
    EvaluationCase,
    evaluate_tool_use_case,
    load_evaluation_dataset,
)

_ADVERSARIAL_DATASET = Path(__file__).resolve().parents[1] / "evals" / "adversarial_dataset.json"


def _tool_cases() -> list[EvaluationCase]:
    dataset = load_evaluation_dataset(_ADVERSARIAL_DATASET, expected_kind="adversarial")
    return [case for case in dataset.cases if case.category == "tool_use"]


def test_tool_use_seed_cases_pass_recorded_outcomes() -> None:
    results = [evaluate_tool_use_case(case) for case in _tool_cases()]

    assert len(results) == 2
    assert all(result.passed for result in results)
    assert all(result.evaluator_version == "tool-use-v1" for result in results)
    assert {metric.name for result in results for metric in result.metrics} == {
        "correct_tool_selection",
        "graceful_failure_handling",
        "timeout_behavior",
        "retry_behavior",
        "safety_behavior",
    }


def test_tool_use_evaluator_fails_status_mismatch() -> None:
    case = next(case for case in _tool_cases() if case.case_id == "tool.sendgrid-misconfigured")
    event = {**case.input["tool_event"], "status": "completed"}

    result = evaluate_tool_use_case(
        case.model_copy(update={"input": {**case.input, "tool_event": event}})
    )

    assert result.passed is False
    assert "tool-use metric failed: graceful_failure_handling" in result.failure_reasons


def test_tool_use_evaluator_reports_invalid_attempt_budget() -> None:
    case = _tool_cases()[0]
    event = {**case.input["tool_event"], "attempt": 2, "max_attempts": 1}

    result = evaluate_tool_use_case(
        case.model_copy(update={"input": {**case.input, "tool_event": event}})
    )

    assert result.passed is False
    assert result.failure_reasons == ["tool-use fixture failed metadata validation"]
