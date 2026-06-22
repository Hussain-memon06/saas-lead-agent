"""Evaluation contracts and deterministic metric adapters."""

from saas_lead_agent.evaluation.contracts import (
    CaseEvaluationResult,
    DatasetCoverageReport,
    DatasetKind,
    EvaluationCase,
    EvaluationCategory,
    EvaluationDataset,
    EvaluationExpectation,
    EvaluationRunResult,
    MetricName,
    MetricResult,
    OutputSchemaName,
)
from saas_lead_agent.evaluation.datasets import DatasetLoadError, load_evaluation_dataset
from saas_lead_agent.evaluation.coverage import analyze_dataset_coverage
from saas_lead_agent.evaluation.grounding import evaluate_grounding_case
from saas_lead_agent.evaluation.outreach import evaluate_outreach_case
from saas_lead_agent.evaluation.retrieval import evaluate_retrieval_case
from saas_lead_agent.evaluation.runner import (
    ExternalProviderCaseError,
    run_evaluation_dataset,
)
from saas_lead_agent.evaluation.scoring import evaluate_scoring_case
from saas_lead_agent.evaluation.safety import evaluate_safety_case
from saas_lead_agent.evaluation.structured_output import evaluate_structured_output_case
from saas_lead_agent.evaluation.tool_use import evaluate_tool_use_case

__all__ = [
    "CaseEvaluationResult",
    "DatasetCoverageReport",
    "DatasetKind",
    "DatasetLoadError",
    "EvaluationCase",
    "EvaluationCategory",
    "EvaluationDataset",
    "EvaluationExpectation",
    "EvaluationRunResult",
    "MetricName",
    "MetricResult",
    "OutputSchemaName",
    "load_evaluation_dataset",
    "evaluate_scoring_case",
    "evaluate_structured_output_case",
    "evaluate_retrieval_case",
    "evaluate_grounding_case",
    "evaluate_outreach_case",
    "evaluate_safety_case",
    "evaluate_tool_use_case",
    "ExternalProviderCaseError",
    "run_evaluation_dataset",
    "analyze_dataset_coverage",
]
