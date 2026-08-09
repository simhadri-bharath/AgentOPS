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
    FRAMEWORKS,
    EvaluationJobCreate,
    EvaluationJobUpdate,
    EvaluationResultRead,
    EvaluationResultsResponse,
    EvaluationRunCreate,
    EvaluationRunListResponse,
    EvaluationRunQueued,
    EvaluationRunRead,
    RunComparison,
    evaluation_result_from_orm,
    evaluation_run_from_orm,
    normalize_framework,
)
from app.services.datasets.parser import parse_dataset_file
from app.services.evaluation import registry
from app.services.evaluation.comparison import build_comparison
from app.services.evaluation.metric_registry import (
    METRIC_REGISTRY,
    UnknownMetricError,
    catalogue,
    validate_metrics,
)
from app.services.evaluation.profiles import recommend
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
    """Reject unknown frameworks and metrics by name, rather than rewriting them."""
    resolved = normalize_framework(framework)
    if resolved not in FRAMEWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported framework: {framework}. Supported: {FRAMEWORKS}",
        )
    try:
        validate_metrics(metrics)
    except UnknownMetricError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _prepare_metrics_for_dataset(
    session: AsyncSession, dataset_id: uuid.UUID, framework: str, metrics: list[str]
) -> list[str]:
    """Validate the selection and warn about metrics this dataset cannot support.

    Reference-based metrics are kept, not dropped: the run reports them as
    unavailable with a reason, which is more useful than quietly substituting
    something else.
    """
    dataset = await DatasetRepository(session).get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    try:
        selected = validate_metrics(metrics)
    except UnknownMetricError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not selected:
        return list(DEFAULT_PROMPT_ONLY_METRICS)
    return selected


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


@router.get(
    "/{evaluation_id}/results/{result_id}",
    response_model=EvaluationResultRead,
)
async def get_evaluation_result(
    evaluation_id: uuid.UUID = Path(...),
    result_id: uuid.UUID = Path(...),
    session: AsyncSession = Depends(get_session),
) -> EvaluationResultRead:
    repo = EvaluationRepository(session)
    run = await repo.get_run(evaluation_id)
    if not run:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(evaluation_id))

    row = await repo.get_result(result_id)
    if not row or row.evaluation_run_id != evaluation_id:
        raise HTTPException(status_code=404, detail="Evaluation result not found")
    return evaluation_result_from_orm(row)


@router.post("/{evaluation_id}/cancel", response_model=EvaluationRunRead)
async def cancel_evaluation(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunRead:
    """Stop a running evaluation.

    Signals the in-flight invoker to stop dispatching. Requests already in
    flight finish or time out; the run is then persisted with whatever it
    completed rather than being abandoned mid-way.
    """
    repo = EvaluationRepository(session)
    run = await repo.get_run(evaluation_id)
    if not run:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(evaluation_id))

    if run.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Run is already {run.status} and cannot be cancelled.",
        )

    signalled = registry.cancel(evaluation_id)
    if not signalled:
        # Queued but never started, or orphaned by a restart. Either way there
        # is nothing running to signal, so mark it terminal directly.
        run = await repo.update_run_status(
            run,
            "cancelled",
            error_message="Cancelled before execution started.",
            mark_completed=True,
        )
        await session.commit()
    return evaluation_run_from_orm(run)


@router.delete("/{evaluation_id}", response_model=dict)
async def delete_evaluation(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Delete a run and its results. Refuses while it is still executing."""
    repo = EvaluationRepository(session)
    run = await repo.get_run(evaluation_id)
    if not run:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(evaluation_id))
    if registry.is_running(evaluation_id):
        raise HTTPException(
            status_code=409,
            detail="Run is executing. Cancel it before deleting.",
        )
    await repo.delete_run(evaluation_id)
    await session.commit()
    return {"message": "Evaluation deleted", "id": str(evaluation_id)}


@router.get("/{evaluation_id}/compare", response_model=RunComparison)
async def compare_evaluations(
    evaluation_id: uuid.UUID,
    baseline: uuid.UUID = Query(..., description="Run id to compare against"),
    session: AsyncSession = Depends(get_session),
) -> RunComparison:
    """Compare two runs metric by metric, and say whether they are comparable.

    A score moving is only meaningful if the harness did not move with it, so
    differences in judge model, dataset version, metric config or invocation
    interface are reported as warnings alongside the deltas.
    """
    repo = EvaluationRepository(session)
    current = await repo.get_run(evaluation_id)
    base = await repo.get_run(baseline)
    if not current:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(evaluation_id))
    if not base:
        raise HTTPException(status_code=404, detail=_evaluation_not_found_detail(baseline))

    current_results, _ = await repo.list_results(evaluation_id, limit=1000)
    base_results, _ = await repo.list_results(baseline, limit=1000)
    return build_comparison(current, base, current_results, base_results)


@router.get("/meta/metrics")
async def list_metric_catalogue() -> dict[str, object]:
    """The metric catalogue, so the UI has one definition instead of its own copy."""
    return {"items": catalogue(), "total": len(METRIC_REGISTRY)}
