"""Dataset Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMBase


class DatasetCreate(ORMBase):
    name: str
    description: str | None = None


class DatasetRead(ORMBase):
    id: uuid.UUID
    name: str
    description: str | None = None
    file_path: str
    format: str
    row_count: int
    created_at: datetime


class DatasetListResponse(ORMBase):
    items: list[DatasetRead]
    total: int


class DatasetUploadResponse(ORMBase):
    dataset: DatasetRead
    message: str = "Dataset uploaded successfully"
