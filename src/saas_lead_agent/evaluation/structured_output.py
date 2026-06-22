"""Deterministic JSON and Pydantic structured-output evaluator."""

import json
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from saas_lead_agent.api.schemas import QualifyResponse
from saas_lead_agent.evaluation.contracts import (
    CaseEvaluationResult,
    EvaluationCase,
    MetricResult,
    OutputSchemaName,
)
from saas_lead_agent.schemas import LeadReport

_EVALUATOR_VERSION = "structured-output-v1"
_SCHEMAS: dict[OutputSchemaName, type[BaseModel]] = {
    "qualify_response": QualifyResponse,
    "lead_report": LeadReport,
}


def evaluate_structured_output_case(case: EvaluationCase) -> CaseEvaluationResult:
    """Evaluate JSON validity, required fields, and an existing Pydantic schema."""
    if case.category != "structured_output":
        raise ValueError("structured-output evaluator requires a structured-output case")
    started_at = perf_counter()
    payload, json_valid = _parse_payload(case.input.get("output"))
    metrics = [
        MetricResult(
            name="json_validity",
            value=1.0 if json_valid else 0.0,
            threshold=1.0,
            comparison="eq",
            passed=json_valid,
        )
    ]
    failures: list[str] = []
    if not json_valid or not isinstance(payload, dict):
        failures.append("output is not a valid JSON object")
        return _result(case, metrics, failures, started_at)

    required_fields = case.expected.required_fields or []
    missing_fields = [field for field in required_fields if field not in payload]
    if required_fields:
        metrics.append(
            MetricResult(
                name="missing_required_fields",
                value=float(len(missing_fields)),
                threshold=0.0,
                comparison="eq",
                passed=not missing_fields,
                details={"missing_fields": missing_fields},
            )
        )
        if missing_fields:
            failures.append("output is missing required fields")

    schema_name = case.expected.output_schema
    if schema_name is not None:
        schema_passed, invalid_enums = _validate_schema(schema_name, payload)
        metrics.extend(
            [
                MetricResult(
                    name="pydantic_validation_pass_rate",
                    value=1.0 if schema_passed else 0.0,
                    threshold=1.0,
                    comparison="eq",
                    passed=schema_passed,
                ),
                MetricResult(
                    name="invalid_enum_values",
                    value=float(invalid_enums),
                    threshold=0.0,
                    comparison="eq",
                    passed=invalid_enums == 0,
                ),
            ]
        )
        if not schema_passed:
            failures.append("output failed Pydantic schema validation")

    return _result(case, metrics, failures, started_at)


def _parse_payload(raw: Any) -> tuple[Any, bool]:
    if isinstance(raw, str):
        try:
            return json.loads(raw), True
        except json.JSONDecodeError:
            return None, False
    if isinstance(raw, (dict, list, int, float, bool)) or raw is None:
        return raw, True
    return None, False


def _validate_schema(schema_name: OutputSchemaName, payload: dict[str, Any]) -> tuple[bool, int]:
    try:
        _SCHEMAS[schema_name].model_validate(payload)
    except ValidationError as exc:
        invalid_enums = sum(error["type"] == "literal_error" for error in exc.errors())
        return False, invalid_enums
    return True, 0


def _result(
    case: EvaluationCase,
    metrics: list[MetricResult],
    failures: list[str],
    started_at: float,
) -> CaseEvaluationResult:
    return CaseEvaluationResult(
        case_id=case.case_id,
        category=case.category,
        passed=all(metric.passed for metric in metrics),
        metrics=metrics,
        failure_reasons=failures,
        evaluator_version=_EVALUATOR_VERSION,
        duration_ms=round((perf_counter() - started_at) * 1000, 3),
    )
