"""Red team Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import ORMBase, PaginatedResponse

RedTeamCategory = Literal[
    "prompt_injection",
    "jailbreak",
    "pii_extraction",
    "boundary",
]

RedTeamClassification = Literal["PASS", "FAIL", "UNCERTAIN"]

SUPPORTED_CATEGORIES: list[str] = [
    "prompt_injection",
    "jailbreak",
    "pii_extraction",
    "boundary",
]

DEFAULT_JUDGE_MODELS: list[str] = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]


class RedTeamRunCreate(ORMBase):
    agent_id: uuid.UUID
    categories: list[str] = Field(
        default_factory=lambda: list(SUPPORTED_CATEGORIES),
        min_length=1,
    )
    judge_model: str = "gemini-2.5-flash"
    use_llm_judge: bool = True
    include_custom_cases: bool = True
    selected_case_ids: list[str] | None = Field(
        default=None,
        description=(
            "Optional attack prompt ids to run (library external_id e.g. pi-01, "
            "or custom test case UUID). Omit or null to run all prompts in each category."
        ),
    )


class RedTeamRunQueued(ORMBase):
    run_id: uuid.UUID
    status: str = "queued"


class RedTeamRunRead(ORMBase):
    id: uuid.UUID
    agent_id: uuid.UUID
    status: str
    categories: list[str]
    judge_model: str
    total_tests: int
    passed: int
    failed: int
    uncertain: int
    report: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class RedTeamRunListResponse(ORMBase):
    items: list[RedTeamRunRead]
    total: int
    limit: int
    offset: int


class RedTeamResultRead(ORMBase):
    id: uuid.UUID
    run_id: uuid.UUID
    test_case_id: uuid.UUID | None = None
    category: str
    severity: str
    prompt: str
    response: str | None = None
    classification: str
    score: float | None = None
    reason: str | None = None
    trace_id: str | None = None
    latency_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    # Populated from metadata when present (semantic evaluation layer)
    confidence_score: float | None = None
    severity_reason: str | None = None
    semantic_reasoning: str | None = None
    toxicity_score: float | None = None
    hallucination_score: float | None = None
    safety_score: float | None = None
    tool_calling_score: float | None = None
    heuristic_flags: list[str] = Field(default_factory=list)


class RedTeamResultsResponse(ORMBase):
    run_id: uuid.UUID
    status: str
    report: dict[str, Any]
    items: list[RedTeamResultRead]
    total: int
    limit: int
    offset: int


class RedTeamTestCaseCreate(ORMBase):
    category: str
    severity: str = "medium"
    prompt: str
    expected_behavior: str
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class RedTeamTestCaseRead(ORMBase):
    id: uuid.UUID | None = None
    external_id: str | None = None
    category: str
    severity: str
    prompt: str
    expected_behavior: str
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    source: str = "library"
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class RedTeamTestCaseListResponse(PaginatedResponse[RedTeamTestCaseRead]):
    pass


class RedTeamDashboardStats(ORMBase):
    total_runs: int
    total_vulnerabilities: int
    recent_failure_count: int
    pass_rate_trend: list[dict[str, Any]] = Field(default_factory=list)
    category_breakdown: dict[str, int] = Field(default_factory=dict)


def redteam_run_from_orm(run: Any) -> RedTeamRunRead:
    return RedTeamRunRead(
        id=run.id,
        agent_id=run.agent_id,
        status=run.status,
        categories=list(run.categories or []),
        judge_model=run.judge_model,
        total_tests=run.total_tests or 0,
        passed=run.passed or 0,
        failed=run.failed or 0,
        uncertain=run.uncertain or 0,
        report=dict(run.report or {}),
        config=dict(run.config or {}),
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
    )


def redteam_result_from_orm(row: Any) -> RedTeamResultRead:
    meta = dict(row.metadata_ or {})
    return RedTeamResultRead(
        id=row.id,
        run_id=row.run_id,
        test_case_id=row.test_case_id,
        category=row.category,
        severity=row.severity,
        prompt=row.prompt,
        response=row.response,
        classification=row.classification,
        score=row.score,
        reason=row.reason,
        trace_id=row.trace_id,
        latency_ms=row.latency_ms,
        metadata=meta,
        created_at=row.created_at,
        confidence_score=meta.get("confidence_score", row.score),
        severity_reason=meta.get("severity_reason"),
        semantic_reasoning=meta.get("semantic_reasoning"),
        toxicity_score=meta.get("toxicity_score"),
        hallucination_score=meta.get("hallucination_score"),
        safety_score=meta.get("safety_score"),
        tool_calling_score=meta.get("tool_calling_score"),
        heuristic_flags=list(meta.get("heuristic_flags") or []),
    )


def redteam_test_case_from_orm(row: Any) -> RedTeamTestCaseRead:
    return RedTeamTestCaseRead(
        id=row.id,
        external_id=row.external_id,
        category=row.category,
        severity=row.severity,
        prompt=row.prompt,
        expected_behavior=row.expected_behavior,
        tags=list(row.tags or []),
        enabled=row.enabled,
        source=row.source,
        extra=dict(row.extra or {}),
        created_at=row.created_at,
    )
