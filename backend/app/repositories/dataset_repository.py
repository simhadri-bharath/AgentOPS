"""Dataset data access."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset


class DatasetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        file_path: str,
        format: str,
        row_count: int,
        description: str | None = None,
    ) -> Dataset:
        dataset = Dataset(
            name=name,
            description=description,
            file_path=file_path,
            format=format,
            row_count=row_count,
        )
        self._session.add(dataset)
        await self._session.flush()
        await self._session.refresh(dataset)
        return dataset

    async def get(self, dataset_id: uuid.UUID) -> Dataset | None:
        result = await self._session.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> tuple[list[Dataset], int]:
        query = select(Dataset).order_by(Dataset.created_at.desc()).limit(limit).offset(offset)
        count_q = select(func.count()).select_from(Dataset)
        items = list((await self._session.execute(query)).scalars().all())
        total = int((await self._session.execute(count_q)).scalar_one())
        return items, total

    async def delete(self, dataset_id: uuid.UUID) -> bool:
        dataset = await self.get(dataset_id)
        if not dataset:
            return False
        await self._session.delete(dataset)
        await self._session.flush()
        return True
