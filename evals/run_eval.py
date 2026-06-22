"""Run deterministic local evaluations without external providers."""

import argparse
from pathlib import Path
from typing import cast

from saas_lead_agent.evaluation import (
    EvaluationCategory,
    load_evaluation_dataset,
    run_evaluation_dataset,
)

_CATEGORY_CHOICES = (
    "scoring",
    "retrieval",
    "structured_output",
    "grounding",
    "tool_use",
    "outreach",
    "safety",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--category", action="append", choices=_CATEGORY_CHOICES)
    args = parser.parse_args()

    dataset = load_evaluation_dataset(args.dataset)
    categories = (
        {cast(EvaluationCategory, category) for category in args.category}
        if args.category
        else None
    )
    result = run_evaluation_dataset(dataset, categories=categories)
    output_path = args.output or Path("evals/results") / f"{dataset.name}-{result.run_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    aggregate_passed = all(metric.passed for metric in result.aggregate_metrics)
    print(
        f"dataset={dataset.name} total={result.total_cases} "
        f"passed={result.passed_cases} failed={result.failed_cases} output={output_path}"
    )
    return 0 if result.failed_cases == 0 and aggregate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
