"""Call async code from a synchronous callback, safely.

DeepTeam's `model_callback` must be synchronous, but the invoker is async. The
obvious bridge -- `asyncio.run(...)` -- breaks depending on where DeepTeam calls
the callback from: with `async_mode=True` it may already be inside a running
loop, and `asyncio.run` raises there. Whether a loop is running is not something
the callback can rely on.

So the coroutine is submitted to a dedicated loop on its own daemon thread,
which is correct from any caller: a running loop, a worker thread with none, or
the main thread.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    with _lock:
        if _loop is not None and not _loop.is_closed():
            return _loop
        loop = asyncio.new_event_loop()

        def _run() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(
            target=_run, name="agentops-sync-bridge", daemon=True
        )
        thread.start()
        _loop, _thread = loop, thread
        logger.debug("Started sync bridge loop", extra={"component": "sync_bridge"})
        return loop


def run_sync(coro: Coroutine[Any, Any, T], *, timeout: float | None = None) -> T:
    """Run a coroutine from synchronous code and return its result."""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)


def shutdown() -> None:
    """Stop the bridge loop. Only needed in tests."""
    global _loop, _thread
    with _lock:
        if _loop is None:
            return
        _loop.call_soon_threadsafe(_loop.stop)
        if _thread is not None:
            _thread.join(timeout=5)
        _loop = None
        _thread = None
