"""Offline evaluator for sanitized recorded tool metadata."""

from time import perf_counter

from pydantic import ValidationError

from saas_lead_agent.evaluation.contracts import (
    CaseEvaluationResult,
    EvaluationCase,
    MetricName,
    MetricResult,
)
from saas_lead_agent.tools.contracts import ToolExecutionMetadata

_EVALUATOR_VERSION = "tool-use-v1"


def evaluate_tool_use_case(case: EvaluationCase) -> CaseEvaluationResult:
    """Evaluate a recorded tool outcome without executing the tool."""
    if case.category != "tool_use":
        raise ValueError("tool-use evaluator requires a tool-use case")
    started_at = perf_counter()
    try:
        metadata = ToolExecutionMetadata.model_validate(case.input.get("tool_event"))
    except ValidationError:
        return _failed_fixture_result(case, started_at)

    expected = case.expected
    tool_matches = (
        expected.expected_tool_name is None or metadata.tool_name == expected.expected_tool_name
    )
    status_matches = (
        expected.expected_tool_status is None or metadata.status == expected.expected_tool_status
    )
    observed_graceful = case.input.get("observed_graceful_failure") is True
    graceful_matches = (
        expected.expected_graceful_failure is None
        or observed_graceful == expected.expected_graceful_failure
    )
    approval_matches = (
        expected.requires_human_approval is None
        or (case.input.get("human_approval_required") is True) == expected.requires_human_approval
    )
    metrics = [
        _boolean_metric("correct_tool_selection", tool_matches),
        _boolean_metric("graceful_failure_handling", status_matches and graceful_matches),
        _boolean_metric("timeout_behavior", metadata.status != "timeout" or status_matches),
        _boolean_metric("retry_behavior", metadata.attempt <= metadata.max_attempts),
    ]
    if expected.requires_human_approval is not None:
        metrics.append(_boolean_metric("safety_behavior", approval_matches))

    failures = [f"tool-use metric failed: {metric.name}" for metric in metrics if not metric.passed]
    return CaseEvaluationResult(
        case_id=case.case_id,
        category=case.category,
        passed=not failures,
        metrics=metrics,
        failure_reasons=failures,
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
    )


def _boolean_metric(name: MetricName, passed: bool) -> MetricResult:
    return MetricResult(
        name=name,
        value=1.0 if passed else 0.0,
        threshold=1.0,
        comparison="eq",
        passed=passed,
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
        failure_reasons=["tool-use fixture failed metadata validation"],
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
    )


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
