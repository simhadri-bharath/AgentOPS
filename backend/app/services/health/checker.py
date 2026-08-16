"""Application health checks."""

import asyncio
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_engine
from app.core.logging import get_logger
from app.schemas.common import HealthStatus
from app.services.gcp.auth import validate_adc_credentials

logger = get_logger(__name__)


# ADC validation is a network round-trip and the frontend polls health, so the
# result is shared across requests for a short window.
_AUTH_CACHE_TTL_S = 30.0


class HealthChecker:
    _auth_cache: tuple[float, str] | None = None
    _auth_lock = asyncio.Lock()

    async def check_database(self, session: AsyncSession | None = None) -> str:
        try:
            if session is not None:
                await session.execute(text("SELECT 1"))
            else:
                engine = get_engine()
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            return "ok"
        except Exception as exc:
            logger.error("Database health check failed: %s", exc, extra={"component": "health"})
            return f"error: {exc}"

    async def check_gcp_auth(self) -> str:
        """Validate ADC without blocking the event loop.

        validate_adc_credentials() refreshes the token, which is network I/O.
        Calling it synchronously from an async handler stalls every other
        request on the worker, and the frontend polls /health -- one slow
        refresh was enough to make the whole app appear hung.

        Cached briefly for the same reason: nothing useful changes second to
        second, and each check is a round-trip to Google.
        """
        now = time.monotonic()
        cached = self._auth_cache
        if cached and (now - cached[0]) < _AUTH_CACHE_TTL_S:
            return cached[1]

        async with self._auth_lock:
            cached = self._auth_cache
            if cached and (time.monotonic() - cached[0]) < _AUTH_CACHE_TTL_S:
                return cached[1]
            status = await asyncio.to_thread(validate_adc_credentials)
            result = "ok" if status.available else f"error: {status.error}"
            HealthChecker._auth_cache = (time.monotonic(), result)
            return result

    async def full_check(self, session: AsyncSession | None = None) -> HealthStatus:
        db_status = await self.check_database(session)
        gcp_status = await self.check_gcp_auth()

        overall = "healthy" if db_status == "ok" and gcp_status == "ok" else "degraded"
        if db_status != "ok":
            overall = "unhealthy"

        return HealthStatus(
            status=overall,
            database=db_status,
            gcp_auth=gcp_status,
            details={
                "database": db_status,
                "gcp_auth": gcp_status,
                # Which project the platform is pointed at -- the UI shows this,
                # and "wrong project" is the most common reason nothing appears.
                "gcp_project": get_settings().gcp_project_id or None,
                "gcp_region": get_settings().gcp_region or None,
            },
        )
