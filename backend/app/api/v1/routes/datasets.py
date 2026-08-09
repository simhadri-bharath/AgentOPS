"""Dataset upload and management routes."""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies import get_session
from app.repositories.agent_repository import AgentRepository
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset import (
    DatasetListResponse,
    DatasetRead,
    DatasetReviewUpdate,
    DatasetUploadResponse,
    HarvestedCase,
    SessionDatasetCreate,
    SessionHarvestPreview,
    SessionHarvestRequest,
)
from app.services.datasets.from_sessions import build_cases_from_sessions
from app.services.datasets.parser import DatasetValidationError, detect_format, parse_dataset_file
from app.services.datasets.validator import category_distribution

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _to_read(dataset) -> DatasetRead:
    return DatasetRead.model_validate(dataset)


@router.post("/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> DatasetUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    try:
        fmt = detect_format(file.filename)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    settings = get_settings()
    storage_dir = Path(settings.dataset_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    dataset_id = uuid.uuid4()
    dest = storage_dir / f"{dataset_id}_{file.filename}"
    content = await file.read()
    dest.write_bytes(content)

    try:
        validated = parse_dataset_file(dest)
    except DatasetValidationError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo = DatasetRepository(session)
    dataset = await repo.create(
        name=name or file.filename,
        description=description,
        file_path=str(dest.resolve()),
        format=validated.format,
        row_count=validated.row_count,
        category_distribution=category_distribution(validated.rows),
    )

    return DatasetUploadResponse(dataset=_to_read(dataset), warnings=validated.warnings)


@router.post("/from-sessions/preview", response_model=SessionHarvestPreview)
async def preview_dataset_from_sessions(
    body: SessionHarvestRequest,
    session: AsyncSession = Depends(get_session),
) -> SessionHarvestPreview:
    """Extract candidate evaluation cases from an agent's production sessions.

    Read-only. Nothing is stored until the reviewed cases are posted back.
    """
    agent = await AgentRepository(session).get_agent(body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {body.agent_id} not found")
    if not agent.endpoint_url:
        raise HTTPException(status_code=400, detail="Agent has no endpoint_url")

    cases, errors = await build_cases_from_sessions(
        agent.endpoint_url,
        limit_sessions=body.limit_sessions,
        max_cases=body.max_cases,
        tool_overrides=(agent.invocation_config or {}).get("tool_overrides"),
    )

    if body.exclude_agentops_traffic:
        # Our own eval and red-team runs are not production traffic and would
        # otherwise feed the platform's own output back into its test set.
        before = len(cases)
        cases = [c for c in cases if not c.input.startswith("Reply with")]
        if before != len(cases):
            errors.append(f"Excluded {before - len(cases)} AgentOps-generated case(s)")

    distribution: dict[str, int] = {}
    for case in cases:
        distribution[case.category] = distribution.get(case.category, 0) + 1

    return SessionHarvestPreview(
        agent_id=body.agent_id,
        total=len(cases),
        category_distribution=distribution,
        preview=[HarvestedCase(**c.to_dict()) for c in cases],
        errors=errors,
    )


@router.post("/from-sessions", response_model=DatasetUploadResponse, status_code=201)
async def create_dataset_from_sessions(
    body: SessionDatasetCreate,
    session: AsyncSession = Depends(get_session),
) -> DatasetUploadResponse:
    """Persist reviewed cases as a dataset.

    Always lands in needs_review: a captured trajectory is evidence of what
    happened, not a decision about what should have happened.
    """
    if not body.cases:
        raise HTTPException(status_code=400, detail="No cases supplied")

    agent = await AgentRepository(session).get_agent(body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {body.agent_id} not found")

    rows = [
        {
            "input": c.input,
            "expected_output": c.expected_output,
            "retrieval_context": c.retrieval_context,
            "reference_trajectory": c.reference_trajectory,
            "conversation": c.conversation,
            "category": c.category,
        }
        for c in body.cases
    ]

    settings = get_settings()
    storage_dir = Path(settings.dataset_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    dataset_id = uuid.uuid4()
    dest = storage_dir / f"{dataset_id}_from_sessions.json"
    dest.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    repo = DatasetRepository(session)
    dataset = await repo.create(
        name=body.name,
        description=body.description
        or f"Bootstrapped from {agent.display_name or agent.name} sessions",
        file_path=str(dest.resolve()),
        format="json",
        row_count=len(rows),
        source="bootstrapped",
        review_status="needs_review",
        created_by=body.created_by,
        agent_id=body.agent_id,
        category_distribution=category_distribution(rows),
    )

    warnings = [
        "reference_trajectory rows were seeded from what the agent actually did. "
        "Review each row before promoting to golden, or a captured bug becomes "
        "the regression baseline.",
    ]
    unreviewed = sum(1 for r in rows if not (r.get("expected_output") or "").strip())
    if unreviewed:
        warnings.append(f"{unreviewed} of {len(rows)} rows have no expected_output yet.")

    return DatasetUploadResponse(dataset=_to_read(dataset), warnings=warnings)


@router.patch("/{dataset_id}/review", response_model=DatasetRead)
async def update_review_status(
    dataset_id: uuid.UUID,
    body: DatasetReviewUpdate,
    session: AsyncSession = Depends(get_session),
) -> DatasetRead:
    repo = DatasetRepository(session)
    dataset = await repo.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if body.review_status == "golden":
        unreviewed = _rows_without_expected_output(dataset)
        if unreviewed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot promote to golden: {unreviewed} row(s) have no "
                    "expected_output. A bootstrapped trajectory records what the "
                    "agent did, not what it should have done."
                ),
            )

    return _to_read(await repo.set_review_status(dataset, body.review_status))


def _rows_without_expected_output(dataset) -> int:
    path = Path(dataset.file_path)
    if not path.exists():
        return 0
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(rows, list):
        return 0
    return sum(
        1 for r in rows if isinstance(r, dict) and not str(r.get("expected_output") or "").strip()
    )


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> DatasetListResponse:
    repo = DatasetRepository(session)
    items, total = await repo.list_all(limit=limit, offset=offset)
    return DatasetListResponse(items=[_to_read(d) for d in items], total=total)


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(
    dataset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DatasetRead:
    repo = DatasetRepository(session)
    dataset = await repo.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return _to_read(dataset)


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    repo = DatasetRepository(session)
    dataset = await repo.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = Path(dataset.file_path)
    await repo.delete(dataset_id)
    file_path.unlink(missing_ok=True)
    return {"message": "Dataset deleted", "id": str(dataset_id)}
