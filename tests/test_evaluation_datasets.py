"""Focused tests for deterministic evaluation dataset loading."""

from pathlib import Path

import pytest

from saas_lead_agent.evaluation import DatasetKind, DatasetLoadError, load_evaluation_dataset

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EVALS_DIR = _REPO_ROOT / "evals"


@pytest.mark.parametrize(
    ("filename", "expected_kind", "expected_count"),
    [
        ("golden_dataset.json", "golden", 15),
        ("adversarial_dataset.json", "adversarial", 4),
        ("retrieval_dataset.json", "retrieval", 2),
    ],
)
def test_seed_dataset_loads(
    filename: str,
    expected_kind: DatasetKind,
    expected_count: int,
) -> None:
    dataset = load_evaluation_dataset(
        _EVALS_DIR / filename,
        expected_kind=expected_kind,
    )

    assert dataset.kind == expected_kind
    assert len(dataset.cases) == expected_count
    assert all(case.requires_external_provider is False for case in dataset.cases)


def test_loader_rejects_wrong_dataset_kind() -> None:
    with pytest.raises(DatasetLoadError, match="kind must be retrieval"):
        load_evaluation_dataset(
            _EVALS_DIR / "golden_dataset.json",
            expected_kind="retrieval",
        )


def test_loader_rejects_invalid_json_without_echoing_content(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"secret": "must-not-appear"', encoding="utf-8")

    with pytest.raises(DatasetLoadError, match="invalid JSON") as exc_info:
        load_evaluation_dataset(path)

    assert "must-not-appear" not in str(exc_info.value)


def test_loader_rejects_schema_invalid_dataset(tmp_path: Path) -> None:
    path = tmp_path / "invalid-schema.json"
    path.write_text('{"name": "missing-required-fields"}', encoding="utf-8")

    with pytest.raises(DatasetLoadError, match="schema validation"):
        load_evaluation_dataset(path)
