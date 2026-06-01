"""Evaluation run and result data access."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.evaluation_result import EvaluationResult
from app.models.evaluation_run import EvaluationRun


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self,
        *,
        agent_id: uuid.UUID,
        dataset_id: uuid.UUID,
        framework: str,
        metrics: list[str],
        status: str = "queued",
        name: str | None = None,
    ) -> EvaluationRun:
        if not name:
            name = await self._generate_job_name()
        run = EvaluationRun(
            agent_id=agent_id,
            dataset_id=dataset_id,
            framework=framework,
            status=status,
            metrics=metrics,
            name=name,
        )
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def create_draft(
        self,
        *,
        agent_id: uuid.UUID,
        dataset_id: uuid.UUID,
        framework: str,
        metrics: list[str],
        name: str | None = None,
    ) -> EvaluationRun:
        return await self.create_run(
            agent_id=agent_id,
            dataset_id=dataset_id,
            framework=framework,
            metrics=metrics,
            status="draft",
            name=name,
        )

    async def _generate_job_name(self) -> str:
        total = int(
            (await self._session.execute(select(func.count()).select_from(EvaluationRun))).scalar_one()
        )
        return f"Eval-{total + 1:03d}"

    async def get_run(self, run_id: uuid.UUID) -> EvaluationRun | None:
        result = await self._session.execute(
            select(EvaluationRun).where(EvaluationRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        *,
        agent_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[EvaluationRun], int]:
        query = select(EvaluationRun)
        count_q = select(func.count()).select_from(EvaluationRun)
        if agent_id:
            query = query.where(EvaluationRun.agent_id == agent_id)
            count_q = count_q.where(EvaluationRun.agent_id == agent_id)
        if status:
            query = query.where(EvaluationRun.status == status)
            count_q = count_q.where(EvaluationRun.status == status)
        query = query.order_by(EvaluationRun.created_at.desc()).limit(limit).offset(offset)
        items = list((await self._session.execute(query)).scalars().all())
        total = int((await self._session.execute(count_q)).scalar_one())
        return items, total

    async def update_draft(
        self,
        run: EvaluationRun,
        *,
        agent_id: uuid.UUID,
        dataset_id: uuid.UUID,
        framework: str,
        metrics: list[str],
    ) -> EvaluationRun:
        if run.status != "draft":
            raise ValueError("Only draft jobs can be updated")
        run.agent_id = agent_id
        run.dataset_id = dataset_id
        run.framework = framework
        run.metrics = metrics
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def update_run_status(
        self,
        run: EvaluationRun,
        status: str,
        *,
        error_message: str | None = None,
        aggregate_scores: dict[str, Any] | None = None,
        mark_started: bool = False,
        mark_completed: bool = False,
    ) -> EvaluationRun:
        run.status = status
        if error_message is not None:
            run.error_message = error_message
        if aggregate_scores is not None:
            run.aggregate_scores = aggregate_scores
        now = datetime.now(timezone.utc)
        if mark_started and run.started_at is None:
            run.started_at = now
        if mark_completed:
            run.completed_at = now
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def add_result(
        self,
        *,
        evaluation_run_id: uuid.UUID,
        sample_index: int,
        input_text: str,
        expected_output: str | None,
        actual_output: str | None,
        scores: dict[str, Any],
        latency_ms: int | None,
    ) -> EvaluationResult:
        row = EvaluationResult(
            evaluation_run_id=evaluation_run_id,
            sample_index=sample_index,
            input=input_text,
            expected_output=expected_output,
            actual_output=actual_output,
            scores=scores,
            latency_ms=latency_ms,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def list_results(
        self, run_id: uuid.UUID, *, limit: int = 500, offset: int = 0
    ) -> tuple[list[EvaluationResult], int]:
        query = (
            select(EvaluationResult)
            .where(EvaluationResult.evaluation_run_id == run_id)
            .order_by(EvaluationResult.sample_index)
            .limit(limit)
            .offset(offset)
        )
        count_q = (
            select(func.count())
            .select_from(EvaluationResult)
            .where(EvaluationResult.evaluation_run_id == run_id)
        )
        items = list((await self._session.execute(query)).scalars().all())
        total = int((await self._session.execute(count_q)).scalar_one())
        return items, total

    async def delete_results_for_run(self, run_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(EvaluationResult).where(
                EvaluationResult.evaluation_run_id == run_id
            )
        )
        await self._session.flush()

    async def get_run_with_results(self, run_id: uuid.UUID) -> EvaluationRun | None:
        result = await self._session.execute(
            select(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .options(selectinload(EvaluationRun.results))
        )
        return result.scalar_one_or_none()
