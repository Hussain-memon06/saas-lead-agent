"""Focused tests for deterministic evaluation coverage reporting."""

from pathlib import Path

import pytest

from saas_lead_agent.evaluation import analyze_dataset_coverage, load_evaluation_dataset

_EVALS_DIR = Path(__file__).resolve().parents[1] / "evals"


def test_golden_coverage_reports_remaining_target_gap() -> None:
    dataset = load_evaluation_dataset(_EVALS_DIR / "golden_dataset.json")

    coverage = analyze_dataset_coverage(dataset)

    assert coverage.total_cases == 15
    assert coverage.target_cases == 30
    assert coverage.target_gap == 15
    assert coverage.missing_required_categories == []
    assert coverage.category_counts == {
        "grounding": 3,
        "outreach": 4,
        "scoring": 5,
        "structured_output": 3,
    }


@pytest.mark.parametrize(
    "filename",
    ["golden_dataset.json", "adversarial_dataset.json", "retrieval_dataset.json"],
)
def test_seed_coverage_is_provider_free_and_has_required_categories(filename: str) -> None:
    dataset = load_evaluation_dataset(_EVALS_DIR / filename)

    coverage = analyze_dataset_coverage(dataset)

    assert coverage.provider_free_cases == coverage.total_cases
    assert coverage.provider_required_cases == 0
    assert coverage.missing_required_categories == []


def test_coverage_supports_explicit_target_override() -> None:
    dataset = load_evaluation_dataset(_EVALS_DIR / "golden_dataset.json")

    coverage = analyze_dataset_coverage(dataset, target_cases=15)

    assert coverage.target_gap == 0
