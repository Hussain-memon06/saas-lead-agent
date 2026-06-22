"""Deterministic evaluator for scoring fixtures."""

from time import perf_counter

from pydantic import ValidationError

from saas_lead_agent.engine import ScoringEngine
from saas_lead_agent.evaluation.contracts import (
    CaseEvaluationResult,
    EvaluationCase,
    MetricResult,
)
from saas_lead_agent.schemas import CompanyProfile, CompanySignal, Contact, IcpContext

_EVALUATOR_VERSION = "scoring-v1"


def evaluate_scoring_case(case: EvaluationCase) -> CaseEvaluationResult:
    """Evaluate one provider-free scoring case against the Python engine."""
    if case.category != "scoring":
        raise ValueError("scoring evaluator requires a scoring case")
    started_at = perf_counter()
    try:
        profile_raw = case.input.get("profile")
        contact_raw = case.input.get("contact")
        profile = None if profile_raw is None else CompanyProfile.model_validate(profile_raw)
        contact = None if contact_raw is None else Contact.model_validate(contact_raw)
        signals = [CompanySignal.model_validate(item) for item in case.input.get("signals", [])]
        icp_raw = case.input.get("icp")
        icp = None if icp_raw is None else IcpContext.model_validate(icp_raw)
    except (TypeError, ValidationError):
        return _failed_fixture_result(case, started_at)

    result = ScoringEngine().calculate_score(
        profile=profile,
        contact=contact,
        signals=signals,
        icp=icp,
    )
    metrics: list[MetricResult] = []
    failures: list[str] = []
    expected = case.expected

    if expected.expected_fit_level is not None:
        passed = result.fit_level == expected.expected_fit_level
        metrics.append(
            MetricResult(
                name="classification_accuracy",
                value=1.0 if passed else 0.0,
                threshold=1.0,
                comparison="eq",
                passed=passed,
                details={
                    "actual_fit_level": result.fit_level,
                    "expected_fit_level": expected.expected_fit_level,
                },
            )
        )
        if not passed:
            failures.append("fit classification did not match expectation")

    deviation = _score_deviation(
        result.fit_score,
        minimum=expected.min_score,
        maximum=expected.max_score,
    )
    if expected.min_score is not None or expected.max_score is not None:
        passed = deviation == 0
        metrics.append(
            MetricResult(
                name="score_deviation",
                value=float(deviation),
                threshold=0.0,
                comparison="lte",
                passed=passed,
                details={"actual_score": result.fit_score},
            )
        )
        if not passed:
            failures.append("fit score fell outside the expected range")

    if expected.requires_human_approval is not None:
        passed = result.needs_human_review == expected.requires_human_approval
        metrics.append(
            MetricResult(
                name="safety_behavior",
                value=1.0 if passed else 0.0,
                threshold=1.0,
                comparison="eq",
                passed=passed,
                details={"needs_human_review": result.needs_human_review},
            )
        )
        if not passed:
            failures.append("human-review decision did not match expectation")

    return CaseEvaluationResult(
        case_id=case.case_id,
        category=case.category,
        passed=all(metric.passed for metric in metrics),
        metrics=metrics,
        failure_reasons=failures,
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
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
        failure_reasons=["scoring fixture failed domain validation"],
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
    )


def _score_deviation(score: int, *, minimum: int | None, maximum: int | None) -> int:
    if minimum is not None and score < minimum:
        return minimum - score
    if maximum is not None and score > maximum:
        return score - maximum
    return 0


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
