"""Red team run, test case, and result data access."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.redteam_result import RedTeamResult
from app.models.redteam_run import RedTeamRun
from app.models.redteam_test_case import RedTeamTestCase


class RedTeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self,
        *,
        agent_id: uuid.UUID,
        categories: list[str],
        judge_model: str,
        config: dict[str, Any] | None = None,
        total_tests: int = 0,
    ) -> RedTeamRun:
        run = RedTeamRun(
            agent_id=agent_id,
            status="queued",
            categories=categories,
            judge_model=judge_model,
            config=config or {},
            total_tests=total_tests,
        )
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def get_run(self, run_id: uuid.UUID) -> RedTeamRun | None:
        result = await self._session.execute(
            select(RedTeamRun).where(RedTeamRun.id == run_id).options(joinedload(RedTeamRun.agent))
        )
        return result.scalar_one_or_none()

    async def get_run_with_results(self, run_id: uuid.UUID) -> RedTeamRun | None:
        result = await self._session.execute(
            select(RedTeamRun)
            .where(RedTeamRun.id == run_id)
            .options(selectinload(RedTeamRun.results), joinedload(RedTeamRun.agent))
        )
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        *,
        agent_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[RedTeamRun], int]:
        query = select(RedTeamRun).options(joinedload(RedTeamRun.agent))
        count_q = select(func.count()).select_from(RedTeamRun)
        if agent_id:
            query = query.where(RedTeamRun.agent_id == agent_id)
            count_q = count_q.where(RedTeamRun.agent_id == agent_id)
        if status:
            query = query.where(RedTeamRun.status == status)
            count_q = count_q.where(RedTeamRun.status == status)
        query = query.order_by(RedTeamRun.created_at.desc()).limit(limit).offset(offset)
        items = list((await self._session.execute(query)).scalars().all())
        total = int((await self._session.execute(count_q)).scalar_one())
        return items, total

    async def update_run(
        self,
        run: RedTeamRun,
        *,
        status: str | None = None,
        total_tests: int | None = None,
        passed: int | None = None,
        failed: int | None = None,
        uncertain: int | None = None,
        report: dict[str, Any] | None = None,
        error_message: str | None = None,
        mark_started: bool = False,
        mark_completed: bool = False,
    ) -> RedTeamRun:
        if status is not None:
            run.status = status
        if total_tests is not None:
            run.total_tests = total_tests
        if passed is not None:
            run.passed = passed
        if failed is not None:
            run.failed = failed
        if uncertain is not None:
            run.uncertain = uncertain
        if report is not None:
            run.report = report
        if error_message is not None:
            run.error_message = error_message
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
        run_id: uuid.UUID,
        test_case_id: uuid.UUID | None,
        category: str,
        severity: str,
        prompt: str,
        response: str | None,
        classification: str,
        score: float | None,
        reason: str | None,
        trace_id: str | None,
        latency_ms: int | None,
        metadata: dict[str, Any] | None = None,
    ) -> RedTeamResult:
        row = RedTeamResult(
            run_id=run_id,
            test_case_id=test_case_id,
            category=category,
            severity=severity,
            prompt=prompt,
            response=response,
            classification=classification,
            score=score,
            reason=reason,
            trace_id=trace_id,
            latency_ms=latency_ms,
            metadata_=metadata or {},
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def list_results(
        self,
        run_id: uuid.UUID,
        *,
        classification: str | None = None,
        category: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[RedTeamResult], int]:
        query = select(RedTeamResult).where(RedTeamResult.run_id == run_id)
        count_q = (
            select(func.count())
            .select_from(RedTeamResult)
            .where(RedTeamResult.run_id == run_id)
        )
        if classification:
            query = query.where(RedTeamResult.classification == classification)
            count_q = count_q.where(RedTeamResult.classification == classification)
        if category:
            query = query.where(RedTeamResult.category == category)
            count_q = count_q.where(RedTeamResult.category == category)
        query = query.order_by(RedTeamResult.created_at).limit(limit).offset(offset)
        items = list((await self._session.execute(query)).scalars().all())
        total = int((await self._session.execute(count_q)).scalar_one())
        return items, total

    async def get_result(self, result_id: uuid.UUID) -> RedTeamResult | None:
        result = await self._session.execute(
            select(RedTeamResult).where(RedTeamResult.id == result_id)
        )
        return result.scalar_one_or_none()

    async def dashboard_stats(self) -> dict[str, Any]:
        total_runs = int(
            (await self._session.execute(select(func.count()).select_from(RedTeamRun))).scalar_one()
        )
        failed_results = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(RedTeamResult)
                    .where(RedTeamResult.classification == "FAIL")
                )
            ).scalar_one()
        )
        recent_failures = list(
            (
                await self._session.execute(
                    select(RedTeamResult)
                    .where(RedTeamResult.classification == "FAIL")
                    .order_by(RedTeamResult.created_at.desc())
                    .limit(10)
                )
            ).scalars().all()
        )
        return {
            "total_runs": total_runs,
            "total_vulnerabilities": failed_results,
            "recent_failures": recent_failures,
        }

    async def create_test_case(
        self,
        *,
        category: str,
        severity: str,
        prompt: str,
        expected_behavior: str,
        tags: list[str] | None = None,
        external_id: str | None = None,
        enabled: bool = True,
        source: str = "custom",
        extra: dict[str, Any] | None = None,
    ) -> RedTeamTestCase:
        row = RedTeamTestCase(
            category=category,
            severity=severity,
            prompt=prompt,
            expected_behavior=expected_behavior,
            tags=tags or [],
            external_id=external_id,
            enabled=enabled,
            source=source,
            extra=extra or {},
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def list_test_cases(
        self,
        *,
        category: str | None = None,
        enabled_only: bool = False,
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[RedTeamTestCase], int]:
        query = select(RedTeamTestCase)
        count_q = select(func.count()).select_from(RedTeamTestCase)
        if category:
            query = query.where(RedTeamTestCase.category == category)
            count_q = count_q.where(RedTeamTestCase.category == category)
        if enabled_only:
            query = query.where(RedTeamTestCase.enabled.is_(True))
            count_q = count_q.where(RedTeamTestCase.enabled.is_(True))
        query = query.order_by(RedTeamTestCase.created_at.desc()).limit(limit).offset(offset)
        items = list((await self._session.execute(query)).scalars().all())
        total = int((await self._session.execute(count_q)).scalar_one())
        return items, total

    async def get_test_case(self, case_id: uuid.UUID) -> RedTeamTestCase | None:
        result = await self._session.execute(
            select(RedTeamTestCase).where(RedTeamTestCase.id == case_id)
        )
        return result.scalar_one_or_none()

    async def delete_results_for_run(self, run_id: uuid.UUID) -> None:
        await self._session.execute(delete(RedTeamResult).where(RedTeamResult.run_id == run_id))
        await self._session.flush()
