"""Focused tests for deterministic retrieval evaluation."""

from pathlib import Path

from saas_lead_agent.evaluation import (
    EvaluationCase,
    EvaluationExpectation,
    evaluate_retrieval_case,
    load_evaluation_dataset,
)

_RETRIEVAL_DATASET = Path(__file__).resolve().parents[1] / "evals" / "retrieval_dataset.json"


def test_retrieval_seed_cases_pass_declared_thresholds() -> None:
    dataset = load_evaluation_dataset(_RETRIEVAL_DATASET, expected_kind="retrieval")

    results = [evaluate_retrieval_case(case) for case in dataset.cases]

    assert len(results) == 2
    assert all(result.passed for result in results)
    assert all(result.evaluator_version == "retrieval-v1" for result in results)
    assert {metric.name for result in results for metric in result.metrics} == {
        "recall_at_k",
        "precision_at_k",
        "mrr",
        "source_coverage",
        "expected_chunk_retrieval",
    }


def test_retrieval_evaluator_reports_failed_thresholds() -> None:
    case = EvaluationCase(
        case_id="retrieval.missing-expected",
        category="retrieval",
        description="Missing the expected chunk should fail recall and exact retrieval.",
        input={
            "retrieved_chunks": [
                {
                    "chunk_id": "unexpected",
                    "document_id": "doc-unexpected",
                    "document_type": "icp",
                    "trust_label": "trusted_user",
                    "text": "Unrelated fixture text.",
                    "token_count": 3,
                    "score": 0.5,
                }
            ]
        },
        expected=EvaluationExpectation(
            expected_chunk_ids=["expected"],
            retrieval_k=1,
            min_recall_at_k=1.0,
        ),
    )

    result = evaluate_retrieval_case(case)

    assert result.passed is False
    assert "retrieval metric failed: recall_at_k" in result.failure_reasons
    assert "retrieval metric failed: expected_chunk_retrieval" in result.failure_reasons


def test_retrieval_evaluator_reports_invalid_chunk_fixture() -> None:
    case = EvaluationCase(
        case_id="retrieval.invalid-chunk",
        category="retrieval",
        description="Schema-invalid chunks should fail safely.",
        input={"retrieved_chunks": [{"chunk_id": "missing-fields"}]},
        expected=EvaluationExpectation(
            expected_chunk_ids=["expected"],
            retrieval_k=1,
        ),
    )

    result = evaluate_retrieval_case(case)

    assert result.passed is False
    assert result.failure_reasons == ["retrieval fixture failed chunk validation"]
    assert result.metrics[0].name == "pydantic_validation_pass_rate"
