"""Deterministic dataset coverage reporting."""

from collections import Counter

from saas_lead_agent.evaluation.contracts import (
    DatasetCoverageReport,
    EvaluationCategory,
    EvaluationDataset,
)

_REQUIRED_CATEGORIES: dict[str, set[EvaluationCategory]] = {
    "golden": {"scoring", "structured_output", "grounding", "outreach"},
    "adversarial": {"tool_use", "safety"},
    "retrieval": {"retrieval"},
}


def analyze_dataset_coverage(
    dataset: EvaluationDataset,
    *,
    target_cases: int | None = None,
) -> DatasetCoverageReport:
    """Summarize coverage without running any evaluator."""
    target = target_cases if target_cases is not None else (30 if dataset.kind == "golden" else 0)
    category_counts = Counter(case.category for case in dataset.cases)
    tag_counts = Counter(tag for case in dataset.cases for tag in case.tags)
    required = _REQUIRED_CATEGORIES[dataset.kind]
    provider_required = sum(case.requires_external_provider for case in dataset.cases)
    return DatasetCoverageReport(
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        total_cases=len(dataset.cases),
        target_cases=target,
        target_gap=max(0, target - len(dataset.cases)),
        category_counts=dict(sorted(category_counts.items())),
        tag_counts=dict(sorted(tag_counts.items())),
        provider_free_cases=len(dataset.cases) - provider_required,
        provider_required_cases=provider_required,
        missing_required_categories=sorted(required - set(category_counts)),
    )
