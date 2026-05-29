"""Background evaluation task entrypoints."""

import uuid

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.repositories.evaluation_repository import EvaluationRepository
from app.services.evaluation.runner import EvaluationRunner

logger = get_logger(__name__)


async def run_evaluation_async(evaluation_id: uuid.UUID) -> None:
    factory = get_session_factory()
    async with factory() as session:
        runner = EvaluationRunner(session)
        await runner.run(evaluation_id)


async def run_evaluation_background(evaluation_id: str) -> None:
    """
    Async background task — must run on the app's event loop (not asyncio.run
    in a thread) so SQLAlchemy asyncpg connections work correctly.
    """
    eval_uuid = uuid.UUID(evaluation_id)
    logger.info(
        "Background evaluation task starting",
        extra={"component": "evaluation_tasks", "evaluation_id": evaluation_id},
    )
    try:
        await run_evaluation_async(eval_uuid)
    except Exception as exc:
        logger.exception(
            "Background evaluation task crashed: %s",
            exc,
            extra={"component": "evaluation_tasks", "evaluation_id": evaluation_id},
        )
        await _mark_failed(eval_uuid, str(exc))


async def _mark_failed(evaluation_id: uuid.UUID, error_message: str) -> None:
    factory = get_session_factory()
    async with factory() as session:
        repo = EvaluationRepository(session)
        run = await repo.get_run(evaluation_id)
        if run and run.status in ("queued", "running"):
            await repo.update_run_status(
                run,
                "failed",
                error_message=error_message,
                mark_completed=True,
            )
            await session.commit()
