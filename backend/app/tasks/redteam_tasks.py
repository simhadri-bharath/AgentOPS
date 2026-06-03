"""Background red team task entrypoints."""

import uuid

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.repositories.redteam_repository import RedTeamRepository
from app.services.redteam.runner import RedTeamRunner

logger = get_logger(__name__)


async def run_redteam_async(run_id: uuid.UUID) -> None:
    factory = get_session_factory()
    async with factory() as session:
        runner = RedTeamRunner(session)
        await runner.run(run_id)


async def run_redteam_background(run_id: str) -> None:
    run_uuid = uuid.UUID(run_id)
    logger.info(
        "Background red team task starting",
        extra={"component": "redteam_tasks", "run_id": run_id},
    )
    try:
        await run_redteam_async(run_uuid)
    except Exception as exc:
        logger.exception(
            "Background red team task crashed: %s",
            exc,
            extra={"component": "redteam_tasks", "run_id": run_id},
        )
        await _mark_failed(run_uuid, str(exc))


async def _mark_failed(run_id: uuid.UUID, error_message: str) -> None:
    factory = get_session_factory()
    async with factory() as session:
        repo = RedTeamRepository(session)
        run = await repo.get_run(run_id)
        if run and run.status in ("queued", "running"):
            await repo.update_run(
                run,
                status="failed",
                error_message=error_message,
                mark_completed=True,
            )
            await session.commit()
