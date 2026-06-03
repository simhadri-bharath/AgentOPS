"""Agent data access layer."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentUpdate


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_agent(self, data: AgentCreate) -> Agent:
        agent = Agent(
            id=data.id or uuid.uuid4(),
            name=data.name,
            display_name=data.display_name,
            deployment_type=data.deployment_type,
            endpoint_url=data.endpoint_url,
            model_name=data.model_name,
            region=data.region,
            gcp_project=data.gcp_project,
            status=data.status,
            source=data.source,
            extra_metadata=data.metadata,
            discovered_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        self._session.add(agent)
        await self._session.flush()
        await self._session.refresh(agent)
        return agent

    async def get_agent(self, agent_id: uuid.UUID) -> Agent | None:
        result = await self._session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_agent_by_endpoint(self, endpoint_url: str) -> Agent | None:
        result = await self._session.execute(
            select(Agent).where(Agent.endpoint_url == endpoint_url)
        )
        return result.scalar_one_or_none()

    async def list_agents(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        deployment_type: str | None = None,
    ) -> tuple[list[Agent], int]:
        query = select(Agent)
        count_query = select(func.count()).select_from(Agent)

        if deployment_type:
            query = query.where(Agent.deployment_type == deployment_type)
            count_query = count_query.where(Agent.deployment_type == deployment_type)

        query = query.order_by(Agent.updated_at.desc()).limit(limit).offset(offset)

        items_result = await self._session.execute(query)
        count_result = await self._session.execute(count_query)

        return list(items_result.scalars().all()), int(count_result.scalar_one())

    async def update_agent(self, agent: Agent, data: AgentUpdate) -> Agent:
        update_data = data.model_dump(exclude_unset=True)
        metadata = update_data.pop("metadata", None)

        for field, value in update_data.items():
            setattr(agent, field, value)

        if metadata is not None:
            agent.extra_metadata = metadata

        agent.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(agent)
        return agent

    async def upsert_agent(self, data: AgentCreate) -> tuple[Agent, bool]:
        """Insert or update by endpoint_url. Returns (agent, created)."""
        existing: Agent | None = None
        if data.endpoint_url:
            existing = await self.get_agent_by_endpoint(data.endpoint_url)
        if existing is None and data.id:
            existing = await self.get_agent(data.id)

        now = datetime.now(timezone.utc)

        if existing:
            existing.name = data.name
            existing.display_name = data.display_name
            existing.deployment_type = data.deployment_type
            existing.endpoint_url = data.endpoint_url
            existing.model_name = data.model_name
            existing.region = data.region
            existing.gcp_project = data.gcp_project
            existing.status = data.status
            existing.source = data.source
            existing.extra_metadata = {**(existing.extra_metadata or {}), **data.metadata}
            existing.last_seen_at = now
            existing.updated_at = now
            if existing.discovered_at is None:
                existing.discovered_at = now
            await self._session.flush()
            await self._session.refresh(existing)
            return existing, False

        agent = Agent(
            id=data.id or uuid.uuid4(),
            name=data.name,
            display_name=data.display_name,
            deployment_type=data.deployment_type,
            endpoint_url=data.endpoint_url,
            model_name=data.model_name,
            region=data.region,
            gcp_project=data.gcp_project,
            status=data.status,
            source=data.source,
            extra_metadata=data.metadata,
            discovered_at=now,
            last_seen_at=now,
        )
        self._session.add(agent)
        await self._session.flush()
        await self._session.refresh(agent)
        return agent, True

    async def delete_agent(self, agent_id: uuid.UUID) -> bool:
        agent = await self.get_agent(agent_id)
        if agent is None:
            return False
        await self._session.delete(agent)
        await self._session.flush()
        return True

    async def mark_stale_agents(
        self,
        active_endpoint_urls: set[str],
        source: str,
    ) -> int:
        """Mark agents not seen in latest sync as inactive."""
        result = await self._session.execute(
            select(Agent).where(Agent.source == source)
        )
        count = 0
        for agent in result.scalars().all():
            if agent.endpoint_url and agent.endpoint_url not in active_endpoint_urls:
                if agent.status != "inactive":
                    agent.status = "inactive"
                    count += 1
        await self._session.flush()
        return count

    async def mark_stale_agents_in_regions(
        self,
        active_endpoint_urls: set[str],
        source: str,
        scanned_regions: set[str],
    ) -> int:
        """Mark agents as inactive only if they're from regions that were scanned but not found.
        
        This prevents marking agents as stale just because a region wasn't included in this sync.
        """
        result = await self._session.execute(
            select(Agent).where(Agent.source == source)
        )
        count = 0
        for agent in result.scalars().all():
            # Only mark as inactive if:
            # 1. Agent has an endpoint_url
            # 2. The endpoint_url is NOT in the active set
            # 3. Agent's region WAS scanned (so absence means truly gone)
            if (
                agent.endpoint_url 
                and agent.endpoint_url not in active_endpoint_urls
                and agent.region in scanned_regions
            ):
                if agent.status != "inactive":
                    agent.status = "inactive"
                    count += 1
        await self._session.flush()
        return count
