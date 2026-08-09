"""In-process registry of running evaluations, so a run can be cancelled.

The invoker has supported cancellation since it was written, but nothing could
reach the instance doing the work. This is the missing handle.

In-process by design: runs execute in FastAPI BackgroundTasks, which live and
die with this process, so a cross-process registry would describe workers that
no longer exist. If runs ever move to a real queue, this goes with them.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from app.services.invokers.agent_engine import AgentEngineInvoker

logger = get_logger(__name__)

_running: dict[str, "AgentEngineInvoker"] = {}


def register(run_id: uuid.UUID, invoker: "AgentEngineInvoker") -> None:
    _running[str(run_id)] = invoker


def unregister(run_id: uuid.UUID) -> None:
    _running.pop(str(run_id), None)


def cancel(run_id: uuid.UUID) -> bool:
    """Signal a run to stop. Returns False if it is not running here."""
    invoker = _running.get(str(run_id))
    if invoker is None:
        return False
    invoker.cancel()
    logger.info(
        "Cancellation requested for evaluation %s",
        run_id,
        extra={"component": "evaluation_registry"},
    )
    return True


def is_running(run_id: uuid.UUID) -> bool:
    return str(run_id) in _running


def running_ids() -> list[str]:
    return list(_running)
