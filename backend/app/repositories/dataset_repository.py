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
        source: str = "upload",
        review_status: str = "human_reviewed",
        created_by: str | None = None,
        agent_id: uuid.UUID | None = None,
        category_distribution: dict[str, int] | None = None,
    ) -> Dataset:
        dataset = Dataset(
            name=name,
            description=description,
            file_path=file_path,
            format=format,
            row_count=row_count,
            source=source,
            review_status=review_status,
            created_by=created_by,
            agent_id=agent_id,
            category_distribution=category_distribution or {},
        )
        self._session.add(dataset)
        await self._session.flush()
        await self._session.refresh(dataset)
        return dataset

    async def record_edit(
        self,
        dataset: Dataset,
        *,
        file_path: str | None = None,
        category_distribution: dict[str, int] | None = None,
    ) -> Dataset:
        """Bump the version after a content change.

        A run snapshots dataset_version, so edited content must not be silently
        comparable to a run made against the previous rows.
        """
        dataset.version = (dataset.version or 1) + 1
        if file_path:
            dataset.file_path = file_path
        if category_distribution is not None:
            dataset.category_distribution = category_distribution
        # Editing rows invalidates a golden promotion made against older content.
        if dataset.review_status == "golden":
            dataset.review_status = "human_reviewed"
        await self._session.flush()
        await self._session.refresh(dataset)
        return dataset

    async def set_review_status(self, dataset: Dataset, review_status: str) -> Dataset:
        dataset.review_status = review_status
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
