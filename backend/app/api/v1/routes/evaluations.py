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
    SUPPORTED_METRICS,
    EvaluationResultsResponse,
    EvaluationRunCreate,
    EvaluationRunListResponse,
    EvaluationRunQueued,
    EvaluationRunRead,
    evaluation_result_from_orm,
    evaluation_run_from_orm,
)
from app.services.datasets.parser import parse_dataset_file
from app.tasks.evaluation_tasks import run_evaluation_background

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def _evaluation_not_found_detail(evaluation_id: uuid.UUID) -> str:
    return (
        f"Evaluation {evaluation_id} not found. "
        "Use the evaluation_id returned by POST /api/v1/evaluations/run "
        "(not the Swagger placeholder UUID). "
        "List existing runs: GET /api/v1/evaluations"
    )


@router.post("/run", response_model=EvaluationRunQueued, status_code=202)
async def start_evaluation(
    body: EvaluationRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunQueued:
    invalid_metrics = [m for m in body.metrics if m not in SUPPORTED_METRICS]
    if invalid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported metrics: {invalid_metrics}. Supported: {SUPPORTED_METRICS}",
        )

    agent = await AgentRepository(session).get_agent(body.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    dataset = await DatasetRepository(session).get(body.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    metrics = list(body.metrics)
    try:
        validated = parse_dataset_file(dataset.file_path)
        has_expected = any((r.get("expected_output") or "").strip() for r in validated.rows)
        if not has_expected:
            # Notebook pattern: questions only — use prompt-only metrics by default
            if set(metrics) <= {"exact_match", "contains_expected"}:
                metrics = list(DEFAULT_PROMPT_ONLY_METRICS)
    except Exception:
        pass

    eval_repo = EvaluationRepository(session)
    run = await eval_repo.create_run(
        agent_id=body.agent_id,
        dataset_id=body.dataset_id,
        framework=body.framework,
        metrics=metrics,
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
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunListResponse:
    repo = EvaluationRepository(session)
    items, total = await repo.list_runs(agent_id=agent_id, limit=limit, offset=offset)

    # Helpful hint when user passes an evaluation_id as agent_id by mistake
    if total == 0 and agent_id is not None:
        maybe_run = await repo.get_run(agent_id)
        if maybe_run:
            items, total = [maybe_run], 1

    return EvaluationRunListResponse(
        items=[evaluation_run_from_orm(r) for r in items],
        total=total,
    )


@router.get("/{evaluation_id}", response_model=EvaluationRunRead)
async def get_evaluation(
    evaluation_id: uuid.UUID = Path(
        ...,
        description="UUID from POST /api/v1/evaluations/run response field evaluation_id",
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
        description="UUID from POST /api/v1/evaluations/run response field evaluation_id",
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
