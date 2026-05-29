"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.repositories.agent_repository import AgentRepository


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_agent_repository(
    session: AsyncSession = Depends(get_session),
) -> AgentRepository:
    return AgentRepository(session)
