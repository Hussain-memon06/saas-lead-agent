"""Deterministic adapter for evidence-grounding evaluation."""

from time import perf_counter

from pydantic import ValidationError

from saas_lead_agent.engine import GroundingEngine, ScoringEngine
from saas_lead_agent.evaluation.contracts import (
    CaseEvaluationResult,
    EvaluationCase,
    MetricName,
    MetricResult,
)
from saas_lead_agent.schemas import (
    CompanyProfile,
    CompanySignal,
    Contact,
    IcpContext,
    OutreachDraft,
)

_EVALUATOR_VERSION = "grounding-v1"


def evaluate_grounding_case(case: EvaluationCase) -> CaseEvaluationResult:
    """Evaluate grounding using validated fixtures and deterministic engines."""
    if case.category != "grounding":
        raise ValueError("grounding evaluator requires a grounding case")
    started_at = perf_counter()
    try:
        profile_raw = case.input.get("profile")
        contact_raw = case.input.get("contact")
        profile = None if profile_raw is None else CompanyProfile.model_validate(profile_raw)
        contact = None if contact_raw is None else Contact.model_validate(contact_raw)
        signals = [CompanySignal.model_validate(item) for item in case.input.get("signals", [])]
        draft = OutreachDraft.model_validate(case.input.get("draft"))
        icp_raw = case.input.get("icp")
        icp = None if icp_raw is None else IcpContext.model_validate(icp_raw)
    except (TypeError, ValidationError):
        return _failed_fixture_result(case, started_at)

    score = ScoringEngine().calculate_score(
        profile=profile,
        contact=contact,
        signals=signals,
        icp=icp,
    )
    report = GroundingEngine().validate(
        profile=profile,
        contact=contact,
        signals=signals,
        draft=draft,
        score=score,
    )
    claim_count = report.supported_claim_count + len(report.unsupported_claims)
    unsupported_rate = len(report.unsupported_claims) / claim_count if claim_count else 0.0
    missing_source_rate = (
        report.missing_source_count / report.supported_claim_count
        if report.supported_claim_count
        else 0.0
    )
    expected = case.expected
    metrics = [
        _bounded_metric(
            "unsupported_claim_rate",
            unsupported_rate,
            minimum=expected.min_unsupported_claim_rate,
            maximum=expected.max_unsupported_claim_rate,
        ),
        _bounded_metric(
            "evidence_coverage",
            report.evidence_coverage,
            minimum=expected.min_evidence_coverage,
            maximum=expected.max_evidence_coverage,
        ),
        _bounded_metric(
            "missing_source_rate",
            missing_source_rate,
            minimum=expected.min_missing_source_rate,
            maximum=expected.max_missing_source_rate,
        ),
    ]
    failures = [f"grounding metric failed: {metric.name}" for metric in metrics if not metric.passed]
    return CaseEvaluationResult(
        case_id=case.case_id,
        category=case.category,
        passed=not failures,
        metrics=metrics,
        failure_reasons=failures,
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
    )


def _bounded_metric(
    name: MetricName,
    value: float,
    *,
    minimum: float | None,
    maximum: float | None,
) -> MetricResult:
    rounded = round(value, 6)
    if minimum is not None:
        return MetricResult(
            name=name,
            value=rounded,
            threshold=minimum,
            comparison="gte",
            passed=rounded >= minimum,
        )
    if maximum is not None:
        return MetricResult(
            name=name,
            value=rounded,
            threshold=maximum,
            comparison="lte",
            passed=rounded <= maximum,
        )
    return MetricResult(name=name, value=rounded, passed=True)


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
        failure_reasons=["grounding fixture failed domain validation"],
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=_elapsed_ms(started_at),
    )


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
