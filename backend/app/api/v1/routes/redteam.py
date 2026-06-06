"""Red team security scanning API routes."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_session
from app.repositories.agent_repository import AgentRepository
from app.repositories.redteam_repository import RedTeamRepository
from app.schemas.redteam import (
    DEFAULT_JUDGE_MODELS,
    SUPPORTED_CATEGORIES,
    RedTeamDashboardStats,
    RedTeamResultRead,
    RedTeamResultsResponse,
    RedTeamRunCreate,
    RedTeamRunListResponse,
    RedTeamRunQueued,
    RedTeamRunRead,
    RedTeamTestCaseCreate,
    RedTeamTestCaseListResponse,
    RedTeamTestCaseRead,
    redteam_result_from_orm,
    redteam_run_from_orm,
    redteam_test_case_from_orm,
)
from app.services.redteam.library_loader import library_to_attack_cases
from app.services.redteam.orchestrator import RedTeamOrchestrator
from app.tasks.redteam_tasks import run_redteam_background

router = APIRouter(prefix="/redteam", tags=["redteam"])


def _run_not_found(run_id: uuid.UUID) -> str:
    return f"Red team run {run_id} not found."


@router.post("/runs", response_model=RedTeamRunQueued, status_code=202)
async def create_redteam_run(
    body: RedTeamRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> RedTeamRunQueued:
    agent = await AgentRepository(session).get_agent(body.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    scan_mode = body.scan_mode or "custom"

    if scan_mode == "dynamic":
        # ---------- Dynamic mode (DeepTeam) ----------
        if not body.vulnerabilities:
            raise HTTPException(status_code=400, detail="Dynamic mode requires at least one vulnerability.")
        if not body.attacks:
            raise HTTPException(status_code=400, detail="Dynamic mode requires at least one attack strategy.")

        config = {
            "scan_mode": "dynamic",
            "target_purpose": body.target_purpose or f"A {agent.name} assistant.",
            "target_system_prompt": body.target_system_prompt or "You are a helpful AI assistant.",
            "vulnerabilities": body.vulnerabilities,
            "attacks": body.attacks,
            "judge_model": body.judge_model,
        }
        repo = RedTeamRepository(session)
        run = await repo.create_run(
            agent_id=body.agent_id,
            categories=[v.get("name") or v.get("id") for v in body.vulnerabilities],
            judge_model=body.judge_model,
            config=config,
            total_tests=0,
        )
        await session.commit()
        background_tasks.add_task(run_redteam_background, str(run.id))
        return RedTeamRunQueued(run_id=run.id, status="queued")

    else:
        # ---------- Custom mode (heuristic library) ----------
        invalid = [c for c in body.categories if c not in SUPPORTED_CATEGORIES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported categories: {invalid}. Supported: {SUPPORTED_CATEGORIES}",
            )

        orchestrator = RedTeamOrchestrator(session)
        try:
            run, cases = await orchestrator.create_run(
                agent_id=body.agent_id,
                categories=body.categories,
                judge_model=body.judge_model,
                use_llm_judge=body.use_llm_judge,
                include_custom_cases=body.include_custom_cases,
                selected_case_ids=body.selected_case_ids,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not cases:
            raise HTTPException(
                status_code=400,
                detail="No test cases found for selected categories and prompts.",
            )

        # Tag config with scan_mode for task routing
        run_config = dict(run.config or {})
        run_config["scan_mode"] = "custom"
        await RedTeamRepository(session).update_run(run, config=run_config)

        await session.commit()
        background_tasks.add_task(run_redteam_background, str(run.id))
        return RedTeamRunQueued(run_id=run.id, status="queued")


@router.get("/runs", response_model=RedTeamRunListResponse)
async def list_redteam_runs(
    agent_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> RedTeamRunListResponse:
    repo = RedTeamRepository(session)
    items, total = await repo.list_runs(
        agent_id=agent_id, status=status, limit=limit, offset=offset
    )
    return RedTeamRunListResponse(
        items=[redteam_run_from_orm(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=RedTeamRunRead)
async def get_redteam_run(
    run_id: uuid.UUID = Path(...),
    session: AsyncSession = Depends(get_session),
) -> RedTeamRunRead:
    run = await RedTeamRepository(session).get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=_run_not_found(run_id))
    return redteam_run_from_orm(run)


@router.get("/runs/{run_id}/results", response_model=RedTeamResultsResponse)
async def get_redteam_results(
    run_id: uuid.UUID = Path(...),
    classification: str | None = None,
    category: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> RedTeamResultsResponse:
    repo = RedTeamRepository(session)
    run = await repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=_run_not_found(run_id))

    items, total = await repo.list_results(
        run_id,
        classification=classification,
        category=category,
        limit=limit,
        offset=offset,
    )
    return RedTeamResultsResponse(
        run_id=run.id,
        status=run.status,
        report=dict(run.report or {}),
        items=[redteam_result_from_orm(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}/results/{result_id}", response_model=RedTeamResultRead)
async def get_redteam_result(
    run_id: uuid.UUID = Path(...),
    result_id: uuid.UUID = Path(...),
    session: AsyncSession = Depends(get_session),
) -> RedTeamResultRead:
    repo = RedTeamRepository(session)
    run = await repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=_run_not_found(run_id))
    row = await repo.get_result(result_id)
    if not row or row.run_id != run_id:
        raise HTTPException(status_code=404, detail="Result not found")
    return redteam_result_from_orm(row)


@router.get("/test-cases", response_model=RedTeamTestCaseListResponse)
async def list_test_cases(
    category: str | None = None,
    source: str | None = Query(default=None, description="library | custom | all"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> RedTeamTestCaseListResponse:
    items: list[RedTeamTestCaseRead] = []

    if source in (None, "all", "library"):
        cats = [category] if category else SUPPORTED_CATEGORIES
        for cat in cats:
            if cat not in SUPPORTED_CATEGORIES:
                continue
            for case in library_to_attack_cases(cat):
                items.append(
                    RedTeamTestCaseRead(
                        id=None,
                        external_id=case.id,
                        category=case.category,
                        severity=case.severity,
                        prompt=case.prompt,
                        expected_behavior=case.expected_behavior,
                        tags=case.tags,
                        enabled=True,
                        source="library",
                    )
                )

    if source in (None, "all", "custom"):
        db_rows, _ = await RedTeamRepository(session).list_test_cases(
            category=category, enabled_only=False, limit=limit, offset=offset
        )
        for row in db_rows:
            items.append(redteam_test_case_from_orm(row))

    if category:
        items = [i for i in items if i.category == category]

    total = len(items)
    page = items[offset : offset + limit]
    return RedTeamTestCaseListResponse(items=page, total=total, limit=limit, offset=offset)


@router.post("/test-cases", response_model=RedTeamTestCaseRead, status_code=201)
async def create_test_case(
    body: RedTeamTestCaseCreate,
    session: AsyncSession = Depends(get_session),
) -> RedTeamTestCaseRead:
    if body.category not in SUPPORTED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Supported: {SUPPORTED_CATEGORIES}",
        )
    row = await RedTeamRepository(session).create_test_case(
        category=body.category,
        severity=body.severity,
        prompt=body.prompt,
        expected_behavior=body.expected_behavior,
        tags=body.tags,
        enabled=body.enabled,
        source="custom",
    )
    await session.commit()
    return redteam_test_case_from_orm(row)


@router.get("/dashboard", response_model=RedTeamDashboardStats)
async def redteam_dashboard(
    session: AsyncSession = Depends(get_session),
) -> RedTeamDashboardStats:
    repo = RedTeamRepository(session)
    runs, _ = await repo.list_runs(limit=30, offset=0)
    trend: list[dict] = []
    category_breakdown: dict[str, int] = {}
    for run in reversed(runs):
        if run.status != "completed":
            continue
        total = run.total_tests or 1
        trend.append(
            {
                "run_id": str(run.id),
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "pass_rate": round((run.passed / total) * 100, 1),
                "failed": run.failed,
            }
        )
        for cat in run.categories or []:
            category_breakdown[cat] = category_breakdown.get(cat, 0) + (run.failed or 0)

    stats = await repo.dashboard_stats()
    return RedTeamDashboardStats(
        total_runs=stats["total_runs"],
        total_vulnerabilities=stats["total_vulnerabilities"],
        recent_failure_count=len(stats["recent_failures"]),
        pass_rate_trend=trend,
        category_breakdown=category_breakdown,
    )


@router.get("/meta/judge-models")
async def list_judge_models() -> dict:
    return {"models": DEFAULT_JUDGE_MODELS, "categories": SUPPORTED_CATEGORIES}


@router.get("/deepteam/vulnerabilities")
async def list_deepteam_vulnerabilities() -> dict:
    from app.services.redteam.deepteam_service import VULNERABILITY_CATALOG

    # Group by category for the frontend
    grouped: dict[str, list] = {}
    for v in VULNERABILITY_CATALOG:
        cat = v["category"]
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(v)
    return {"vulnerabilities": VULNERABILITY_CATALOG, "grouped": grouped}


@router.get("/deepteam/attacks")
async def list_deepteam_attacks() -> dict:
    from app.services.redteam.deepteam_service import ATTACK_CATALOG

    single_turn = [a for a in ATTACK_CATALOG if a["type"] == "single_turn"]
    multi_turn = [a for a in ATTACK_CATALOG if a["type"] == "multi_turn"]
    return {
        "attacks": ATTACK_CATALOG,
        "single_turn": single_turn,
        "multi_turn": multi_turn,
    }
