"""Provider-free local evaluation dispatcher."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from saas_lead_agent.evaluation.aggregate import aggregate_scoring_metrics
from saas_lead_agent.evaluation.contracts import (
    CaseEvaluationResult,
    EvaluationCase,
    EvaluationCategory,
    EvaluationDataset,
    EvaluationRunResult,
)
from saas_lead_agent.evaluation.grounding import evaluate_grounding_case
from saas_lead_agent.evaluation.outreach import evaluate_outreach_case
from saas_lead_agent.evaluation.retrieval import evaluate_retrieval_case
from saas_lead_agent.evaluation.safety import evaluate_safety_case
from saas_lead_agent.evaluation.scoring import evaluate_scoring_case
from saas_lead_agent.evaluation.structured_output import evaluate_structured_output_case
from saas_lead_agent.evaluation.tool_use import evaluate_tool_use_case

Evaluator = Callable[[EvaluationCase], CaseEvaluationResult]

_EVALUATORS: dict[EvaluationCategory, Evaluator] = {
    "scoring": evaluate_scoring_case,
    "retrieval": evaluate_retrieval_case,
    "structured_output": evaluate_structured_output_case,
    "grounding": evaluate_grounding_case,
    "tool_use": evaluate_tool_use_case,
    "outreach": evaluate_outreach_case,
    "safety": evaluate_safety_case,
}


class ExternalProviderCaseError(ValueError):
    """Raised when the local runner encounters an opt-in provider case."""


def run_evaluation_dataset(
    dataset: EvaluationDataset,
    *,
    categories: set[EvaluationCategory] | None = None,
    run_id: str | None = None,
) -> EvaluationRunResult:
    """Run selected provider-free cases and return a sanitized result model."""
    started_at = datetime.now(UTC)
    selected = [
        case for case in dataset.cases if categories is None or case.category in categories
    ]
    if not selected:
        raise ValueError("no evaluation cases matched the selected categories")
    provider_cases = [case.case_id for case in selected if case.requires_external_provider]
    if provider_cases:
        raise ExternalProviderCaseError(
            f"external-provider cases require an opt-in runner: {', '.join(provider_cases)}"
        )

    results = [_EVALUATORS[case.category](case) for case in selected]
    passed_cases = sum(result.passed for result in results)
    completed_at = datetime.now(UTC)
    return EvaluationRunResult(
        run_id=run_id or f"eval-{uuid4()}",
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        started_at=started_at,
        completed_at=completed_at,
        total_cases=len(results),
        passed_cases=passed_cases,
        failed_cases=len(results) - passed_cases,
        results=results,
        aggregate_metrics=aggregate_scoring_metrics(results),
    )
