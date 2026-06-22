"""Deterministic loading for versioned local evaluation datasets."""

import json
from pathlib import Path

from pydantic import ValidationError

from saas_lead_agent.evaluation.contracts import DatasetKind, EvaluationDataset

_MAX_DATASET_BYTES = 2_000_000


class DatasetLoadError(ValueError):
    """Raised when a local evaluation dataset cannot be safely validated."""


def load_evaluation_dataset(
    path: str | Path,
    *,
    expected_kind: DatasetKind | None = None,
) -> EvaluationDataset:
    """Load one UTF-8 JSON dataset through the strict evaluation contract."""
    dataset_path = Path(path)
    if dataset_path.suffix.lower() != ".json":
        raise DatasetLoadError("evaluation dataset must be a JSON file")
    try:
        size = dataset_path.stat().st_size
    except OSError as exc:
        raise DatasetLoadError(f"evaluation dataset is not readable: {dataset_path.name}") from exc
    if size > _MAX_DATASET_BYTES:
        raise DatasetLoadError("evaluation dataset exceeds the 2 MB limit")
    try:
        raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise DatasetLoadError(f"evaluation dataset is not readable: {dataset_path.name}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetLoadError(
            f"evaluation dataset contains invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    try:
        dataset = EvaluationDataset.model_validate(raw)
    except ValidationError as exc:
        raise DatasetLoadError("evaluation dataset failed schema validation") from exc
    if expected_kind is not None and dataset.kind != expected_kind:
        raise DatasetLoadError(
            f"evaluation dataset kind must be {expected_kind}, got {dataset.kind}"
        )
    return dataset
