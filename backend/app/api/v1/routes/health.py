"""Health check routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_session
from app.schemas.common import HealthStatus
from app.services.health.checker import HealthChecker

router = APIRouter(tags=["health"])
_checker = HealthChecker()


@router.get("/health", response_model=HealthStatus)
async def health_check(
    session: AsyncSession = Depends(get_session),
) -> HealthStatus:
    return await _checker.full_check(session)
