"""Database initialization utilities."""

from app.core.database import Base, get_engine
from app.core.logging import get_logger

logger = get_logger(__name__)


async def init_models() -> None:
    """Create tables if they do not exist (dev convenience; prefer Alembic in prod)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured", extra={"component": "db_init"})
