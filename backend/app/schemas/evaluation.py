"""Evaluation Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import ORMBase
from app.services.evaluation.metric_registry import (
    METRIC_REGISTRY,
    UnknownMetricError,
    validate_metrics,
)

# The old FRAMEWORK_METRIC_EXECUTION_MAP is gone. It rewrote every named metric
# into a string comparison before the run was queued -- faithfulness became
# contains_expected, toxicity became response_nonempty -- so users read real
# metric names over str.__contains__ results. Metrics now come from
# METRIC_REGISTRY, and an unknown one is rejected rather than degraded.

SUPPORTED_METRICS: list[str] = sorted(METRIC_REGISTRY)

DEFAULT_PROMPT_ONLY_METRICS: list[str] = [
    "response_nonempty",
    "answer_relevancy",
    "trace_answered",
    "trace_tool_success_rate",
]

JOB_STATUSES: list[str] = [
    "draft",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]

# RAGAS is deliberately absent: it is not installed and has no code, and
# offering it as a selectable framework was the same lie as the metric map.
FRAMEWORKS: list[str] = ["deepeval", "deterministic"]


# Existing rows store "vertex"/"vertex_ai" from before the rename; those runs did
# execute, so they stay readable and re-runnable. "ragas" is deliberately absent:
# it was selectable while uninstalled with zero code, so it must be rejected
# rather than quietly treated as DeepEval.
LEGACY_FRAMEWORK_ALIASES = {"vertex": "deepeval", "vertex_ai": "deepeval"}


def normalize_framework(framework: str) -> str:
    return LEGACY_FRAMEWORK_ALIASES.get((framework or "").lower(), (framework or "").lower())


def resolve_metrics(metrics: list[str]) -> list[str]:
    """Validate a metric selection. Raises UnknownMetricError on anything unknown."""
    return validate_metrics(metrics)


class EvaluationRunCreate(ORMBase):
    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    framework: str = "deepeval"
    metrics: list[str] = Field(default_factory=list)
    name: str | None = None


class EvaluationJobCreate(ORMBase):
    """Create a draft evaluation job without running it."""

    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    framework: str = "deepeval"
    metrics: list[str] = Field(default_factory=list)
    name: str | None = None


class EvaluationJobUpdate(ORMBase):
    """Update a draft evaluation job."""

    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    framework: str = "deepeval"
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
    # What produced these numbers, snapshotted at queue time so a score from
    # months ago is still interpretable.
    run_config: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
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
    # Why a metric has no score. "Unavailable, and here is what is missing" is a
    # different answer from "the judge errored", and neither is a score of zero.
    metric_explanations: dict[str, Any] = Field(default_factory=dict)
    metric_unavailable: dict[str, Any] = Field(default_factory=dict)
    metric_errors: dict[str, Any] = Field(default_factory=dict)
    # Per-sub-agent scores: which component dragged the sample down.
    span_scores: list[Any] = Field(default_factory=list)
    trace: dict[str, Any] = Field(default_factory=dict)
    state: str = "SUCCESS"
    error_message: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: datetime


class EvaluationResultsResponse(ORMBase):
    evaluation_id: uuid.UUID
    status: str
    aggregate_scores: dict[str, Any]
    items: list[EvaluationResultRead]
    total: int


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
        run_config=dict(getattr(run, "run_config", None) or {}),
        usage=dict(getattr(run, "usage", None) or {}),
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
        metric_explanations=dict(row.metric_explanations or {}),
        metric_unavailable=dict(row.metric_unavailable or {}),
        metric_errors=dict(row.metric_errors or {}),
        span_scores=list(row.span_scores or []),
        trace=dict(row.trace or {}),
        state=row.state or "SUCCESS",
        error_message=row.error_message,
        tokens_in=row.tokens_in or 0,
        tokens_out=row.tokens_out or 0,
        created_at=row.created_at,
    )


class RunComparison(ORMBase):
    """Two runs, metric by metric, plus whether they are actually comparable."""

    evaluation_id: uuid.UUID
    baseline_id: uuid.UUID
    # False when the harness moved between the runs, in which case a delta is
    # not evidence about the agent.
    comparable: bool
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    metric_deltas: list[dict[str, Any]] = Field(default_factory=list)
    regressed_samples: list[dict[str, Any]] = Field(default_factory=list)
    span_deltas: list[dict[str, Any]] = Field(default_factory=list)
