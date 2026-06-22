"""Focused tests for provider-free adversarial safety evaluation."""

from pathlib import Path

from saas_lead_agent.evaluation import (
    EvaluationCase,
    evaluate_safety_case,
    load_evaluation_dataset,
)

_ADVERSARIAL_DATASET = Path(__file__).resolve().parents[1] / "evals" / "adversarial_dataset.json"


def _safety_cases() -> list[EvaluationCase]:
    dataset = load_evaluation_dataset(_ADVERSARIAL_DATASET, expected_kind="adversarial")
    return [case for case in dataset.cases if case.category == "safety"]


def test_safety_seed_cases_pass_offline_policy_checks() -> None:
    results = [evaluate_safety_case(case) for case in _safety_cases()]

    assert len(results) == 2
    assert all(result.passed for result in results)
    assert all(result.evaluator_version == "safety-v1" for result in results)


def test_safety_evaluator_fails_untrusted_text_without_recorded_boundary() -> None:
    case = next(case for case in _safety_cases() if "prompt-injection" in case.tags)
    modified = {**case.input, "observed_instruction_boundary": "followed_as_instruction"}

    result = evaluate_safety_case(case.model_copy(update={"input": modified}))

    assert result.passed is False
    assert result.failure_reasons == [
        "adversarial safety behavior did not match expectation"
    ]


def test_safety_evaluator_fails_public_url_when_denial_is_expected() -> None:
    case = next(case for case in _safety_cases() if "malicious-url" in case.tags)

    result = evaluate_safety_case(
        case.model_copy(update={"input": {"url": "https://public.example.com"}})
    )

    assert result.passed is False
