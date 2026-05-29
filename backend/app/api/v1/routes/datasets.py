"""Dataset upload and management routes."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies import get_session
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset import DatasetListResponse, DatasetRead, DatasetUploadResponse
from app.services.datasets.parser import DatasetValidationError, detect_format, parse_dataset_file

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
    )

    return DatasetUploadResponse(dataset=_to_read(dataset))


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
