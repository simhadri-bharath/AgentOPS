"""Recover evaluation runs orphaned by a restart.

Runs execute in FastAPI BackgroundTasks, which die with the process. A run left
in `running` after a restart has no owner and will never finish, but the UI
shows it as in progress indefinitely -- which is why a manual retry endpoint
had to exist.

Not a queue. A queue is premature until there is more than one worker.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.evaluation_run import EvaluationRun

logger = get_logger(__name__)

ORPHANED_MESSAGE = (
    "Run was interrupted by a server restart. Background tasks do not survive "
    "the process, so this run was marked failed rather than left in progress. "
    "Use retry to run it again."
)


async def sweep_orphaned_runs(session: AsyncSession) -> int:
    """Fail runs still marked running past the timeout. Returns how many."""
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.orphaned_run_timeout_minutes
    )

    rows = (
        await session.execute(
            select(EvaluationRun).where(EvaluationRun.status.in_(["running", "queued"]))
        )
    ).scalars().all()

    swept = 0
    for run in rows:
        started = run.started_at or run.created_at
        if started and started.replace(tzinfo=timezone.utc) > cutoff:
            # Recent enough that it could belong to the process that just
            # started; leave it alone.
            continue
        run.status = "failed"
        run.error_message = ORPHANED_MESSAGE
        run.completed_at = datetime.now(timezone.utc)
        swept += 1

    if swept:
        await session.flush()
        logger.info(
            "Swept %s orphaned evaluation run(s)",
            swept,
            extra={"component": "sweeper"},
        )
    return swept
