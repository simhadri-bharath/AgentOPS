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

# Align with notebook: only prompts required; agent generates responses
DEFAULT_PROMPT_ONLY_METRICS: list[str] = [
    "response_nonempty",
    "response_length",
    "latency_ms",
]


class EvaluationRunCreate(ORMBase):
    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    framework: str = "vertex_ai"
    metrics: list[str] = Field(
        default_factory=lambda: ["exact_match", "contains_expected", "response_length"]
    )


class EvaluationRunQueued(ORMBase):
    evaluation_id: uuid.UUID
    status: str = "queued"


class EvaluationRunRead(ORMBase):
    id: uuid.UUID
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


class EvaluationRunListResponse(ORMBase):
    items: list[EvaluationRunRead]
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


def evaluation_run_from_orm(run: Any) -> EvaluationRunRead:
    return EvaluationRunRead(
        id=run.id,
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
