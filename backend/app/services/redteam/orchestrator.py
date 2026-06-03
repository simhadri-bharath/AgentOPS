"""Red team run orchestration — collects cases and prepares execution plan."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.redteam_repository import RedTeamRepository
from app.services.redteam.case_plan import build_run_cases, validate_selected_ids
from app.services.redteam.strategies.base import AttackCase


class RedTeamOrchestrator:
    """Platform-owned orchestration (not delegated to DeepEval / external frameworks)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = RedTeamRepository(session)

    async def create_run(
        self,
        *,
        agent_id: uuid.UUID,
        categories: list[str],
        judge_model: str,
        use_llm_judge: bool = True,
        include_custom_cases: bool = True,
        selected_case_ids: list[str] | None = None,
    ) -> tuple[Any, list[AttackCase]]:
        all_cases = await build_run_cases(
            self._repo,
            categories=categories,
            include_custom_cases=include_custom_cases,
            selected_case_ids=selected_case_ids,
        )
        validate_selected_ids(all_cases, categories, selected_case_ids)

        config = {
            "use_llm_judge": use_llm_judge,
            "include_custom_cases": include_custom_cases,
            "selected_case_ids": selected_case_ids or [],
        }
        run = await self._repo.create_run(
            agent_id=agent_id,
            categories=categories,
            judge_model=judge_model,
            config=config,
            total_tests=len(all_cases),
        )
        return run, all_cases
