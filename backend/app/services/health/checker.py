"""Application health checks."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_engine
from app.core.logging import get_logger
from app.schemas.common import HealthStatus
from app.services.gcp.auth import validate_adc_credentials

logger = get_logger(__name__)


class HealthChecker:
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

    def check_gcp_auth(self) -> str:
        status = validate_adc_credentials()
        if status.available:
            return "ok"
        return f"error: {status.error}"

    async def full_check(self, session: AsyncSession | None = None) -> HealthStatus:
        db_status = await self.check_database(session)
        gcp_status = self.check_gcp_auth()

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
