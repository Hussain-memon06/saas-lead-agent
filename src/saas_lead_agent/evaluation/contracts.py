"""Typed contracts for deterministic and opt-in agent evaluations."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from saas_lead_agent.engine.scoring import FitLevel
from saas_lead_agent.schemas.base import StrictBaseModel

DatasetKind = Literal["golden", "adversarial", "retrieval"]
EvaluationCategory = Literal[
    "scoring",
    "retrieval",
    "structured_output",
    "grounding",
    "tool_use",
    "outreach",
    "safety",
]
MetricComparison = Literal["gte", "lte", "eq"]
OutputSchemaName = Literal["qualify_response", "lead_report"]
MetricName = Literal[
    "classification_accuracy",
    "score_deviation",
    "false_positive_rate",
    "false_negative_rate",
    "recall_at_k",
    "precision_at_k",
    "mrr",
    "source_coverage",
    "expected_chunk_retrieval",
    "json_validity",
    "pydantic_validation_pass_rate",
    "missing_required_fields",
    "invalid_enum_values",
    "unsupported_claim_rate",
    "evidence_coverage",
    "missing_source_rate",
    "correct_tool_selection",
    "graceful_failure_handling",
    "timeout_behavior",
    "retry_behavior",
    "personalization_density",
    "specificity",
    "spamminess",
    "cta_clarity",
    "prohibited_placeholder_detection",
    "tone_match",
    "outreach_quality_score",
    "safety_behavior",
]


class EvaluationExpectation(StrictBaseModel):
    """Expected behavior for one evaluation case."""

    expected_fit_level: FitLevel | None = None
    min_score: int | None = Field(default=None, ge=1, le=10)
    max_score: int | None = Field(default=None, ge=1, le=10)
    expected_chunk_ids: list[str] | None = Field(default=None, min_length=1)
    expected_source_uris: list[str] | None = Field(default=None, min_length=1)
    retrieval_k: int | None = Field(default=None, ge=1, le=100)
    min_recall_at_k: float | None = Field(default=None, ge=0, le=1)
    min_precision_at_k: float | None = Field(default=None, ge=0, le=1)
    min_mrr: float | None = Field(default=None, ge=0, le=1)
    min_source_coverage: float | None = Field(default=None, ge=0, le=1)
    output_schema: OutputSchemaName | None = None
    expected_json_valid: bool | None = None
    expected_schema_valid: bool | None = None
    min_invalid_enum_values: int | None = Field(default=None, ge=0)
    required_fields: list[str] | None = Field(default=None, min_length=1)
    expected_missing_fields: list[str] | None = Field(default=None, min_length=1)
    expected_tool_name: str | None = Field(default=None, min_length=1, max_length=100)
    expected_tool_status: (
        Literal[
            "completed",
            "failed",
            "skipped",
            "timeout",
            "rate_limited",
            "stubbed",
        ]
        | None
    ) = None
    expected_graceful_failure: bool | None = None
    min_unsupported_claim_rate: float | None = Field(default=None, ge=0, le=1)
    max_unsupported_claim_rate: float | None = Field(default=None, ge=0, le=1)
    min_evidence_coverage: float | None = Field(default=None, ge=0, le=1)
    max_evidence_coverage: float | None = Field(default=None, ge=0, le=1)
    min_missing_source_rate: float | None = Field(default=None, ge=0, le=1)
    max_missing_source_rate: float | None = Field(default=None, ge=0, le=1)
    min_personalization_density: float | None = Field(default=None, ge=0, le=1)
    max_personalization_density: float | None = Field(default=None, ge=0, le=1)
    min_spamminess: float | None = Field(default=None, ge=0, le=1)
    max_spamminess: float | None = Field(default=None, ge=0, le=1)
    min_outreach_quality_score: int | None = Field(default=None, ge=0, le=100)
    max_outreach_quality_score: int | None = Field(default=None, ge=0, le=100)
    expected_cta_present: bool | None = None
    expected_placeholders_present: bool | None = None
    requires_human_approval: bool | None = None

    @model_validator(mode="after")
    def validate_expectation(self) -> "EvaluationExpectation":
        values = self.model_dump()
        if not any(value is not None for value in values.values()):
            raise ValueError("evaluation expectation must define at least one expected behavior")
        if self.min_score is not None and self.max_score is not None:
            if self.min_score > self.max_score:
                raise ValueError("min_score cannot exceed max_score")
        bounded_pairs = (
            (
                self.min_unsupported_claim_rate,
                self.max_unsupported_claim_rate,
                "unsupported claim rate",
            ),
            (self.min_evidence_coverage, self.max_evidence_coverage, "evidence coverage"),
            (self.min_missing_source_rate, self.max_missing_source_rate, "missing source rate"),
            (self.min_spamminess, self.max_spamminess, "spamminess"),
            (
                self.min_personalization_density,
                self.max_personalization_density,
                "personalization density",
            ),
            (
                self.min_outreach_quality_score,
                self.max_outreach_quality_score,
                "outreach quality score",
            ),
        )
        for minimum, maximum, label in bounded_pairs:
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"minimum {label} cannot exceed maximum")
        if self.expected_chunk_ids is not None and self.retrieval_k is None:
            raise ValueError("retrieval_k is required when expected_chunk_ids are defined")
        if self.output_schema is None and (
            self.expected_schema_valid is not None or self.min_invalid_enum_values is not None
        ):
            raise ValueError("output_schema is required for schema-validity expectations")
        if self.expected_missing_fields is not None:
            if self.required_fields is None:
                raise ValueError("required_fields are required for missing-field expectations")
            if not set(self.expected_missing_fields).issubset(self.required_fields):
                raise ValueError("expected missing fields must be listed in required_fields")
        return self


class EvaluationCase(StrictBaseModel):
    """One versioned, provider-free-by-default evaluation fixture."""

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,99}$")
    category: EvaluationCategory
    description: str = Field(min_length=1, max_length=500)
    input: dict[str, Any]
    expected: EvaluationExpectation
    tags: list[str] = Field(default_factory=list, max_length=30)
    requires_external_provider: bool = False

    @model_validator(mode="after")
    def validate_category_expectation(self) -> "EvaluationCase":
        expected = self.expected
        if self.category == "scoring" and not any(
            value is not None
            for value in (expected.expected_fit_level, expected.min_score, expected.max_score)
        ):
            raise ValueError("scoring cases require fit-level or score expectations")
        if self.category == "retrieval" and not any(
            value is not None
            for value in (expected.expected_chunk_ids, expected.expected_source_uris)
        ):
            raise ValueError("retrieval cases require chunk or source expectations")
        if self.category == "structured_output" and not any(
            value is not None
            for value in (
                expected.output_schema,
                expected.expected_json_valid,
                expected.expected_schema_valid,
                expected.required_fields,
                expected.expected_missing_fields,
            )
        ):
            raise ValueError("structured-output cases require schema or field expectations")
        if self.category == "grounding" and not any(
            value is not None
            for value in (
                expected.max_unsupported_claim_rate,
                expected.min_unsupported_claim_rate,
                expected.min_evidence_coverage,
                expected.max_evidence_coverage,
                expected.min_missing_source_rate,
                expected.max_missing_source_rate,
            )
        ):
            raise ValueError("grounding cases require grounding metric expectations")
        if self.category == "outreach" and not any(
            value is not None
            for value in (
                expected.min_personalization_density,
                expected.max_personalization_density,
                expected.min_spamminess,
                expected.max_spamminess,
                expected.min_outreach_quality_score,
                expected.max_outreach_quality_score,
                expected.expected_cta_present,
                expected.expected_placeholders_present,
            )
        ):
            raise ValueError("outreach cases require outreach-quality expectations")
        if self.category == "tool_use" and not any(
            value is not None
            for value in (expected.expected_tool_name, expected.expected_tool_status)
        ):
            raise ValueError("tool-use cases require tool name or status expectations")
        if self.category == "safety" and expected.expected_graceful_failure is None:
            raise ValueError("safety cases require an expected safety outcome")
        return self


class EvaluationDataset(StrictBaseModel):
    """Versioned collection of evaluation fixtures."""

    schema_version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    kind: DatasetKind
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> "EvaluationDataset":
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation dataset case IDs must be unique")
        return self


class DatasetCoverageReport(StrictBaseModel):
    """Inspectable category/tag/provider coverage for one dataset version."""

    dataset_name: str
    dataset_version: str
    total_cases: int = Field(ge=0)
    target_cases: int = Field(ge=0)
    target_gap: int = Field(ge=0)
    category_counts: dict[EvaluationCategory, int]
    tag_counts: dict[str, int]
    provider_free_cases: int = Field(ge=0)
    provider_required_cases: int = Field(ge=0)
    missing_required_categories: list[EvaluationCategory] = Field(default_factory=list)


class MetricResult(StrictBaseModel):
    """One inspectable metric and its acceptance decision."""

    name: MetricName
    value: float
    threshold: float | None = None
    comparison: MetricComparison | None = None
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_threshold_pair(self) -> "MetricResult":
        if (self.threshold is None) != (self.comparison is None):
            raise ValueError("metric threshold and comparison must be defined together")
        return self


class CaseEvaluationResult(StrictBaseModel):
    """Sanitized result for one evaluation case."""

    case_id: str
    category: EvaluationCategory
    passed: bool
    metrics: list[MetricResult] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    evaluator_version: str = Field(min_length=1, max_length=50)
    duration_ms: float = Field(ge=0)


class EvaluationRunResult(StrictBaseModel):
    """Reproducible summary emitted by a future local eval runner."""

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1, max_length=100)
    dataset_name: str
    dataset_version: str
    started_at: datetime
    completed_at: datetime
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    results: list[CaseEvaluationResult] = Field(default_factory=list)
    aggregate_metrics: list[MetricResult] = Field(default_factory=list)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "EvaluationRunResult":
        if self.passed_cases + self.failed_cases != self.total_cases:
            raise ValueError("passed_cases plus failed_cases must equal total_cases")
        if len(self.results) != self.total_cases:
            raise ValueError("result count must equal total_cases")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self
