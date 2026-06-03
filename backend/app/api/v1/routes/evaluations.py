"""Evaluation run routes."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_session
from app.repositories.agent_repository import AgentRepository
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.schemas.evaluation import (
    DEFAULT_PROMPT_ONLY_METRICS,
    FRAMEWORK_METRICS,
    FRAMEWORKS,
    EvaluationJobCreate,
    EvaluationJobUpdate,
    EvaluationResultsResponse,
    EvaluationRunCreate,
    EvaluationRunListResponse,
    EvaluationRunQueued,
    EvaluationRunRead,
    evaluation_result_from_orm,
    evaluation_run_from_orm,
    resolve_executable_metrics,
    VERTEX_MANAGED_METRICS,
)
from app.services.datasets.parser import parse_dataset_file
from app.tasks.evaluation_tasks import run_evaluation_background

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def _evaluation_not_found_detail(evaluation_id: uuid.UUID) -> str:
    return (
        f"Evaluation {evaluation_id} not found. "
        "Use the evaluation_id returned by POST /api/v1/evaluations/jobs "
        "(not the Swagger placeholder UUID). "
        "List existing runs: GET /api/v1/evaluations"
    )


def _validate_framework_metrics(framework: str, metrics: list[str]) -> None:
    if framework not in FRAMEWORKS and framework != "vertex_ai":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported framework: {framework}. Supported: {FRAMEWORKS}",
        )
    normalized = "vertex" if framework == "vertex_ai" else framework
    allowed = set(FRAMEWORK_METRICS.get(normalized, []))
    invalid = [m for m in metrics if m not in allowed]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported metrics for {framework}: {invalid}. Allowed: {sorted(allowed)}",
        )


def _validate_reference_column(metrics: list[str], dataset_path: str) -> None:
    if "final_response_match" in metrics:
        try:
            validated = parse_dataset_file(dataset_path)
            if not any("reference" in r for r in validated.rows):
                raise HTTPException(
                    status_code=400,
                    detail="Dataset must contain a 'reference' column if 'final_response_match' is selected.",
                )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(status_code=400, detail=str(exc))


async def _prepare_metrics_for_dataset(
    session: AsyncSession, dataset_id: uuid.UUID, framework: str, metrics: list[str]
) -> list[str]:
    dataset = await DatasetRepository(session).get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    executable = resolve_executable_metrics(framework, metrics)
    try:
        validated = parse_dataset_file(dataset.file_path)
        has_expected = any((r.get("expected_output") or "").strip() for r in validated.rows)
        if not has_expected:
            managed = [m for m in executable if m in VERTEX_MANAGED_METRICS]
            local_only = [m for m in executable if m not in VERTEX_MANAGED_METRICS]
            if set(local_only) <= {"exact_match", "contains_expected"}:
                executable = managed + list(DEFAULT_PROMPT_ONLY_METRICS)
    except Exception:
        pass
    return executable


@router.post("/jobs", response_model=EvaluationRunRead, status_code=201)
async def create_evaluation_job(
    body: EvaluationJobCreate,
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunRead:
    """Create a draft evaluation job without running it."""
    if not body.metrics:
        raise HTTPException(status_code=400, detail="Select at least one metric")

    _validate_framework_metrics(body.framework, body.metrics)

    agent = await AgentRepository(session).get_agent(body.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    dataset = await DatasetRepository(session).get(body.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    _validate_reference_column(body.metrics, dataset.file_path)

    eval_repo = EvaluationRepository(session)
    run = await eval_repo.create_draft(
        agent_id=body.agent_id,
        dataset_id=body.dataset_id,
        framework=body.framework,
        metrics=list(body.metrics),
        name=body.name,
    )
    await session.commit()
    return evaluation_run_from_orm(run)


@router.patch("/{evaluation_id}", response_model=EvaluationRunRead)
async def update_evaluation_job(
    body: EvaluationJobUpdate,
    evaluation_id: uuid.UUID = Path(..., description="Draft evaluation job id"),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunRead:
    """Update a draft evaluation job configuration."""
    if not body.metrics:
        raise HTTPException(status_code=400, detail="Select at least one metric")

    _validate_framework_metrics(body.framework, body.metrics)

    repo = EvaluationRepository(session)
    run = await repo.get_run(evaluation_id)
    if not run:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(evaluation_id))

    if run.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update job with status '{run.status}'. Only draft jobs can be edited.",
        )

    agent = await AgentRepository(session).get_agent(body.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    dataset = await DatasetRepository(session).get(body.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    _validate_reference_column(body.metrics, dataset.file_path)

    framework = body.framework if body.framework != "vertex_ai" else "vertex"
    run = await repo.update_draft(
        run,
        agent_id=body.agent_id,
        dataset_id=body.dataset_id,
        framework=framework,
        metrics=list(body.metrics),
    )
    await session.commit()
    return evaluation_run_from_orm(run)


@router.post("/{evaluation_id}/run", response_model=EvaluationRunQueued, status_code=202)
async def run_evaluation_job(
    background_tasks: BackgroundTasks,
    evaluation_id: uuid.UUID = Path(..., description="Draft evaluation job id"),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunQueued:
    """Run a draft evaluation job."""
    repo = EvaluationRepository(session)
    run = await repo.get_run(evaluation_id)
    if not run:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(evaluation_id))

    if run.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot run job with status '{run.status}'. Only draft jobs can be run.",
        )

    dataset = await DatasetRepository(session).get(run.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    _validate_reference_column(list(run.metrics or []), dataset.file_path)

    executable = await _prepare_metrics_for_dataset(
        session, run.dataset_id, run.framework, list(run.metrics or [])
    )

    run.metrics = executable
    await repo.update_run_status(run, "queued")
    await session.commit()

    background_tasks.add_task(run_evaluation_background, str(run.id))
    return EvaluationRunQueued(evaluation_id=run.id, status="queued")


@router.post("/run", response_model=EvaluationRunQueued, status_code=202)
async def start_evaluation(
    body: EvaluationRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunQueued:
    """Create and immediately queue an evaluation (legacy shortcut)."""
    if not body.metrics:
        raise HTTPException(status_code=400, detail="Select at least one metric")

    _validate_framework_metrics(body.framework, body.metrics)

    agent = await AgentRepository(session).get_agent(body.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    dataset = await DatasetRepository(session).get(body.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    _validate_reference_column(body.metrics, dataset.file_path)

    executable = await _prepare_metrics_for_dataset(
        session, body.dataset_id, body.framework, list(body.metrics)
    )

    eval_repo = EvaluationRepository(session)
    run = await eval_repo.create_run(
        agent_id=body.agent_id,
        dataset_id=body.dataset_id,
        framework=body.framework,
        metrics=executable,
        status="queued",
        name=body.name,
    )
    await session.commit()

    background_tasks.add_task(run_evaluation_background, str(run.id))
    return EvaluationRunQueued(evaluation_id=run.id, status="queued")


@router.post("/{evaluation_id}/retry", response_model=EvaluationRunQueued)
async def retry_evaluation(
    background_tasks: BackgroundTasks,
    evaluation_id: uuid.UUID = Path(
        ...,
        description="Re-queue a stuck queued/failed evaluation",
    ),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunQueued:
    """Re-run background processing for evaluations stuck in queued or failed."""
    repo = EvaluationRepository(session)
    run = await repo.get_run(evaluation_id)
    if not run:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(evaluation_id))

    if run.status not in ("queued", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry evaluation with status '{run.status}'. Only queued or failed.",
        )

    await repo.delete_results_for_run(evaluation_id)
    await repo.update_run_status(
        run,
        "queued",
        error_message=None,
        aggregate_scores={},
    )
    run.started_at = None
    run.completed_at = None
    await session.commit()

    background_tasks.add_task(run_evaluation_background, str(run.id))
    return EvaluationRunQueued(evaluation_id=run.id, status="queued")


@router.get("", response_model=EvaluationRunListResponse)
async def list_evaluations(
    agent_id: uuid.UUID | None = Query(
        default=None,
        description=(
            "Filter by agent UUID (from GET /api/v1/agents). "
            "This is NOT the evaluation run id — use GET /api/v1/evaluations/{evaluation_id} for a single run."
        ),
    ),
    status: str | None = Query(default=None, description="Filter by job status (draft, queued, running, ...)"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunListResponse:
    repo = EvaluationRepository(session)
    items, total = await repo.list_runs(agent_id=agent_id, status=status, limit=limit, offset=offset)

    if total == 0 and agent_id is not None:
        maybe_run = await repo.get_run(agent_id)
        if maybe_run:
            items, total = [maybe_run], 1

    return EvaluationRunListResponse(
        items=[evaluation_run_from_orm(r) for r in items],
        total=total,
    )


@router.get("/jobs", response_model=EvaluationRunListResponse)
async def list_evaluation_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunListResponse:
    """List evaluation jobs (alias for GET /evaluations)."""
    repo = EvaluationRepository(session)
    items, total = await repo.list_runs(status=status, limit=limit, offset=offset)
    return EvaluationRunListResponse(
        items=[evaluation_run_from_orm(r) for r in items],
        total=total,
    )


@router.get("/{evaluation_id}", response_model=EvaluationRunRead)
async def get_evaluation(
    evaluation_id: uuid.UUID = Path(
        ...,
        description="UUID from POST /api/v1/evaluations/jobs response field id",
    ),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunRead:
    run = await EvaluationRepository(session).get_run(evaluation_id)
    if not run:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(evaluation_id))
    return evaluation_run_from_orm(run)


@router.get("/{evaluation_id}/results", response_model=EvaluationResultsResponse)
async def get_evaluation_results(
    evaluation_id: uuid.UUID = Path(
        ...,
        description="UUID from POST /api/v1/evaluations/jobs response field id",
    ),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> EvaluationResultsResponse:
    repo = EvaluationRepository(session)
    run = await repo.get_run(evaluation_id)
    if not run:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(evaluation_id))

    items, total = await repo.list_results(evaluation_id, limit=limit, offset=offset)
    return EvaluationResultsResponse(
        evaluation_id=run.id,
        status=run.status,
        aggregate_scores=dict(run.aggregate_scores or {}),
        items=[evaluation_result_from_orm(r) for r in items],
        total=total,
    )
