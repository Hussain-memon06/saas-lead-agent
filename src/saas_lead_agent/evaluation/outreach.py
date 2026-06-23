"""Deterministic adapter for outreach-quality evaluation."""

from time import perf_counter

from pydantic import ValidationError

from saas_lead_agent.engine import OutreachQualityEngine
from saas_lead_agent.evaluation.contracts import (
    CaseEvaluationResult,
    EvaluationCase,
    MetricName,
    MetricResult,
)
from saas_lead_agent.schemas import CompanyProfile, CompanySignal, Contact, OutreachDraft

_EVALUATOR_VERSION = "outreach-v1"
_MAX_PERSONALIZATION_HOOKS = 6


def evaluate_outreach_case(case: EvaluationCase) -> CaseEvaluationResult:
    """Evaluate outreach using existing deterministic quality rules."""
    if case.category != "outreach":
        raise ValueError("outreach evaluator requires an outreach case")
    started_at = perf_counter()
    try:
        profile_raw = case.input.get("profile")
        contact_raw = case.input.get("contact")
        profile = None if profile_raw is None else CompanyProfile.model_validate(profile_raw)
        contact = None if contact_raw is None else Contact.model_validate(contact_raw)
        signals = [CompanySignal.model_validate(item) for item in case.input.get("signals", [])]
        draft = OutreachDraft.model_validate(case.input.get("draft"))
    except (TypeError, ValidationError):
        return _failed_fixture_result(case, started_at)

    quality = OutreachQualityEngine().evaluate(
        profile=profile,
        contact=contact,
        signals=signals,
        draft=draft,
    )
    expected = case.expected
    personalization_density = min(
        1.0,
        len(quality.personalization_hooks) / _MAX_PERSONALIZATION_HOOKS,
    )
    spamminess = 1.0 if quality.spam_terms else 0.0
    has_cta = "draft is missing a clear call to action" not in quality.issues
    has_no_placeholders = not quality.placeholder_terms
    metrics = [
        _bounded_metric(
            "personalization_density",
            personalization_density,
            minimum=expected.min_personalization_density,
            maximum=expected.max_personalization_density,
        ),
        _bounded_metric(
            "spamminess",
            spamminess,
            minimum=expected.min_spamminess,
            maximum=expected.max_spamminess,
        ),
        _bounded_metric(
            "outreach_quality_score",
            float(quality.quality_score),
            minimum=(
                float(expected.min_outreach_quality_score)
                if expected.min_outreach_quality_score is not None
                else None
            ),
            maximum=(
                float(expected.max_outreach_quality_score)
                if expected.max_outreach_quality_score is not None
                else None
            ),
        ),
        _expected_boolean_metric(
            "cta_clarity",
            actual=has_cta,
            expected=expected.expected_cta_present,
        ),
        _expected_boolean_metric(
            "prohibited_placeholder_detection",
            actual=not has_no_placeholders,
            expected=expected.expected_placeholders_present,
        ),
    ]
    if expected.requires_human_approval is not None:
        approval_required = case.input.get("human_approval_required") is True
        approval_passed = approval_required == expected.requires_human_approval
        metrics.append(
            MetricResult(
                name="safety_behavior",
                value=1.0 if approval_passed else 0.0,
                threshold=1.0,
                comparison="eq",
                passed=approval_passed,
            )
        )

    failures = [f"outreach metric failed: {metric.name}" for metric in metrics if not metric.passed]
    return CaseEvaluationResult(
        case_id=case.case_id,
        category=case.category,
        passed=not failures,
        metrics=metrics,
        failure_reasons=failures,
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
    )


def _minimum_metric(name: MetricName, value: float, threshold: float | None) -> MetricResult:
    if threshold is None:
        return MetricResult(name=name, value=round(value, 6), passed=True)
    return MetricResult(
        name=name,
        value=round(value, 6),
        threshold=threshold,
        comparison="gte",
        passed=value >= threshold,
    )


def _maximum_metric(name: MetricName, value: float, threshold: float | None) -> MetricResult:
    if threshold is None:
        return MetricResult(name=name, value=round(value, 6), passed=True)
    return MetricResult(
        name=name,
        value=round(value, 6),
        threshold=threshold,
        comparison="lte",
        passed=value <= threshold,
    )


def _bounded_metric(
    name: MetricName,
    value: float,
    *,
    minimum: float | None,
    maximum: float | None,
) -> MetricResult:
    if minimum is not None:
        return _minimum_metric(name, value, minimum)
    return _maximum_metric(name, value, maximum)


def _expected_boolean_metric(
    name: MetricName,
    *,
    actual: bool,
    expected: bool | None,
) -> MetricResult:
    if expected is None:
        return MetricResult(name=name, value=1.0 if actual else 0.0, passed=True)
    passed = actual == expected
    return MetricResult(
        name=name,
        value=1.0 if passed else 0.0,
        threshold=1.0,
        comparison="eq",
        passed=passed,
        details={"actual": actual, "expected": expected},
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
        failure_reasons=["outreach fixture failed domain validation"],
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
    )


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
