"""Aggregate deterministic metrics across provider-free case results."""

from saas_lead_agent.evaluation.contracts import CaseEvaluationResult, MetricResult


def aggregate_scoring_metrics(
    results: list[CaseEvaluationResult],
    *,
    min_accuracy: float = 0.8,
    max_false_positive_rate: float = 0.2,
    max_false_negative_rate: float = 0.2,
) -> list[MetricResult]:
    """Aggregate scoring classification metrics, treating high fit as positive."""
    classifications: list[tuple[str, str]] = []
    deviations: list[float] = []
    for result in results:
        if result.category != "scoring":
            continue
        for metric in result.metrics:
            if metric.name == "classification_accuracy":
                actual = metric.details.get("actual_fit_level")
                expected = metric.details.get("expected_fit_level")
                if isinstance(actual, str) and isinstance(expected, str):
                    classifications.append((actual, expected))
            elif metric.name == "score_deviation":
                deviations.append(metric.value)

    if not classifications:
        return []

    correct = sum(actual == expected for actual, expected in classifications)
    expected_positives = sum(expected == "high" for _, expected in classifications)
    expected_negatives = len(classifications) - expected_positives
    false_positives = sum(
        actual == "high" and expected != "high" for actual, expected in classifications
    )
    false_negatives = sum(
        actual != "high" and expected == "high" for actual, expected in classifications
    )
    accuracy = correct / len(classifications)
    false_positive_rate = false_positives / expected_negatives if expected_negatives else 0.0
    false_negative_rate = false_negatives / expected_positives if expected_positives else 0.0
    average_deviation = sum(deviations) / len(deviations) if deviations else 0.0

    return [
        MetricResult(
            name="classification_accuracy",
            value=round(accuracy, 6),
            threshold=min_accuracy,
            comparison="gte",
            passed=accuracy >= min_accuracy,
            details={"case_count": len(classifications)},
        ),
        MetricResult(
            name="score_deviation",
            value=round(average_deviation, 6),
            passed=True,
            details={"case_count": len(deviations)},
        ),
        MetricResult(
            name="false_positive_rate",
            value=round(false_positive_rate, 6),
            threshold=max_false_positive_rate,
            comparison="lte",
            passed=false_positive_rate <= max_false_positive_rate,
            details={
                "false_positives": false_positives,
                "expected_negatives": expected_negatives,
            },
        ),
        MetricResult(
            name="false_negative_rate",
            value=round(false_negative_rate, 6),
            threshold=max_false_negative_rate,
            comparison="lte",
            passed=false_negative_rate <= max_false_negative_rate,
            details={
                "false_negatives": false_negatives,
                "expected_positives": expected_positives,
            },
        ),
    ]
