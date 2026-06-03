"""Evaluation Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import ORMBase

MetricName = Literal[
    "exact_match",
    "contains_expected",
    "response_length",
    "response_nonempty",
    "latency_ms",
]

SUPPORTED_METRICS: list[str] = [
    "exact_match",
    "contains_expected",
    "response_length",
    "response_nonempty",
    "latency_ms",
]

DEFAULT_PROMPT_ONLY_METRICS: list[str] = [
    "response_nonempty",
    "response_length",
    "latency_ms",
]

JOB_STATUSES: list[str] = ["draft", "queued", "running", "completed", "failed"]

FRAMEWORKS: list[str] = ["vertex", "ragas", "deepeval"]

FRAMEWORK_METRICS: dict[str, list[str]] = {
    "vertex": [
        "groundedness", "relevance", "correctness", "fluency",
        "exact_match", "contains_expected", "response_length", "response_nonempty", "latency_ms",
        "agent_trajectory_exact_match", "agent_trajectory_in_order_match", "agent_trajectory_any_order_match",
        "agent_trajectory_precision", "agent_trajectory_recall",
        "final_response_quality", "hallucination", "tool_use_quality", "safety", "final_response_match", "final_response_ref_free",
        "agent_multi_turn_task_success", "agent_multi_turn_tool_use_quality", "agent_multi_turn_trajectory_quality",
        "custom_llm_metric", "custom_code_metric"
    ],
    "ragas": [
        "faithfulness", "answer_relevancy", "context_precision", "context_recall",
        "exact_match", "contains_expected", "response_length", "response_nonempty", "latency_ms",
        "agent_trajectory_exact_match", "agent_trajectory_in_order_match", "agent_trajectory_any_order_match",
        "agent_trajectory_precision", "agent_trajectory_recall",
        "final_response_quality", "hallucination", "tool_use_quality", "safety", "final_response_match", "final_response_ref_free",
        "agent_multi_turn_task_success", "agent_multi_turn_tool_use_quality", "agent_multi_turn_trajectory_quality",
        "custom_llm_metric", "custom_code_metric"
    ],
    "deepeval": [
        "hallucination", "answer_relevancy", "toxicity",
        "exact_match", "contains_expected", "response_length", "response_nonempty", "latency_ms",
        "agent_trajectory_exact_match", "agent_trajectory_in_order_match", "agent_trajectory_any_order_match",
        "agent_trajectory_precision", "agent_trajectory_recall",
        "final_response_quality", "tool_use_quality", "safety", "final_response_match", "final_response_ref_free",
        "agent_multi_turn_task_success", "agent_multi_turn_tool_use_quality", "agent_multi_turn_trajectory_quality",
        "custom_llm_metric", "custom_code_metric"
    ],
}

# Map UI framework metric names to executable backend metrics (Vertex MVP)
FRAMEWORK_METRIC_EXECUTION_MAP: dict[str, str] = {
    "groundedness": "contains_expected",
    "relevance": "response_nonempty",
    "correctness": "exact_match",
    "fluency": "response_length",
    "faithfulness": "contains_expected",
    "answer_relevancy": "response_nonempty",
    "context_precision": "exact_match",
    "context_recall": "contains_expected",
    "toxicity": "response_nonempty",

    # New Metric Maps to executable stubs
    "agent_trajectory_exact_match": "exact_match",
    "agent_trajectory_in_order_match": "exact_match",
    "agent_trajectory_any_order_match": "exact_match",
    "agent_trajectory_precision": "contains_expected",
    "agent_trajectory_recall": "contains_expected",
    "agent_multi_turn_task_success": "exact_match",
    "agent_multi_turn_tool_use_quality": "contains_expected",
    "agent_multi_turn_trajectory_quality": "contains_expected",
    "custom_llm_metric": "contains_expected",
    "custom_code_metric": "exact_match",
}


class EvaluationRunCreate(ORMBase):
    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    framework: str = "vertex"
    metrics: list[str] = Field(default_factory=list)
    name: str | None = None


class EvaluationJobCreate(ORMBase):
    """Create a draft evaluation job without running it."""

    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    framework: str = "vertex"
    metrics: list[str] = Field(default_factory=list)
    name: str | None = None


class EvaluationJobUpdate(ORMBase):
    """Update a draft evaluation job."""

    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    framework: str = "vertex"
    metrics: list[str] = Field(default_factory=list)


class EvaluationRunQueued(ORMBase):
    evaluation_id: uuid.UUID
    status: str = "queued"


class EvaluationJobRead(ORMBase):
    id: uuid.UUID
    name: str
    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    framework: str
    status: str
    metrics: list[str]
    aggregate_scores: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationRunRead(EvaluationJobRead):
    """Alias for backward compatibility."""


class EvaluationRunListResponse(ORMBase):
    items: list[EvaluationJobRead]
    total: int


class EvaluationResultRead(ORMBase):
    id: uuid.UUID
    evaluation_run_id: uuid.UUID
    sample_index: int
    input: str
    expected_output: str | None = None
    actual_output: str | None = None
    scores: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int | None = None
    created_at: datetime


class EvaluationResultsResponse(ORMBase):
    evaluation_id: uuid.UUID
    status: str
    aggregate_scores: dict[str, Any]
    items: list[EvaluationResultRead]
    total: int


VERTEX_MANAGED_METRICS = {
    "final_response_quality",
    "hallucination",
    "tool_use_quality",
    "safety",
    "final_response_match",
    "final_response_ref_free",
    "agent_multi_turn_task_success",        
    "agent_multi_turn_tool_use_quality",    
    "agent_multi_turn_trajectory_quality",
}


# ❌ REPLACE the entire resolve_executable_metrics function

def resolve_executable_metrics(framework: str, metrics: list[str]) -> list[str]:
    """Map framework-specific metric names to executable backend metrics."""
    if framework == "vertex_ai":
        framework = "vertex"

    allowed = set(FRAMEWORK_METRICS.get(framework, SUPPORTED_METRICS))
    selected = [m for m in metrics if m in allowed or m in SUPPORTED_METRICS]
    if not selected:
        return list(SUPPORTED_METRICS)

    executable: list[str] = []
    for metric in selected:
        # Vertex managed metrics pass through as-is — handled by google-genai SDK in runner
        if metric in VERTEX_MANAGED_METRICS:
            executable.append(metric)
        elif metric in SUPPORTED_METRICS:
            executable.append(metric)
        else:
            mapped = FRAMEWORK_METRIC_EXECUTION_MAP.get(metric)
            if mapped and mapped not in executable:
                executable.append(mapped)

    return executable or list(SUPPORTED_METRICS)


def evaluation_run_from_orm(run: Any) -> EvaluationJobRead:
    return EvaluationJobRead(
        id=run.id,
        name=run.name,
        agent_id=run.agent_id,
        dataset_id=run.dataset_id,
        framework=run.framework,
        status=run.status,
        metrics=list(run.metrics or []),
        aggregate_scores=dict(run.aggregate_scores or {}),
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def evaluation_result_from_orm(row: Any) -> EvaluationResultRead:
    return EvaluationResultRead(
        id=row.id,
        evaluation_run_id=row.evaluation_run_id,
        sample_index=row.sample_index,
        input=row.input,
        expected_output=row.expected_output,
        actual_output=row.actual_output,
        scores=dict(row.scores or {}),
        latency_ms=row.latency_ms,
        created_at=row.created_at,
    )
