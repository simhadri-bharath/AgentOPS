"""Vertex AI Reasoning Engine discovery service."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.repositories.agent_repository import AgentRepository
from app.schemas.agent import AgentCreate, AgentRead, DiscoverySyncSummary
from app.services.discovery.base import BaseDiscoveryService
from app.services.gcp.auth import require_adc

logger = get_logger(__name__)

# Stable namespace for UUID5 derived from GCP resource names
_AGENTOPS_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


class VertexAIDiscoveryService(BaseDiscoveryService):
    """
    Discovers Vertex AI Reasoning Engines using the preview SDK
    (reasoning_engines.ReasoningEngine.list) and syncs to PostgreSQL.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._repository = AgentRepository(session)
        self._initialized = False
        self._project_id: str | None = None
        self._region: str | None = None

    async def initialize(self) -> None:
        auth = require_adc()
        self._project_id = self._settings.gcp_project_id or auth.project_id
        self._region = self._settings.gcp_region

        if not self._project_id:
            raise RuntimeError(
                "GCP project ID is required. Set GCP_PROJECT_ID in .env or "
                "configure your gcloud default project."
            )

        await asyncio.to_thread(self._init_vertex_sdk, self._project_id, self._region)
        self._initialized = True
        logger.info(
            "Vertex AI SDK initialized",
            extra={
                "component": "vertex_discovery",
                "project_id": self._project_id,
                "region": self._region,
            },
        )

    @staticmethod
    def _init_vertex_sdk(project_id: str, location: str) -> None:
        import vertexai

        vertexai.init(project=project_id, location=location)

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("VertexAIDiscoveryService not initialized. Call initialize() first.")

    async def list_reasoning_engines(self) -> list[Any]:
        self._ensure_initialized()
        return await asyncio.to_thread(self._list_engines_sync)

    @staticmethod
    def _list_engines_sync() -> list[Any]:
        from vertexai.preview import reasoning_engines

        deployed = reasoning_engines.ReasoningEngine.list()
        if deployed is None:
            engines: list[Any] = []
        elif isinstance(deployed, list):
            engines = deployed
        else:
            engines = list(deployed)

        logger.info(
            "Listed reasoning engines",
            extra={"component": "vertex_discovery", "count": len(engines)},
        )
        return engines

    def parse_reasoning_engine(self, engine: Any) -> AgentCreate:
        resource_name = getattr(engine, "resource_name", None) or str(engine)
        engine_id = resource_name.split("/")[-1]
        agent_uuid = uuid.uuid5(_AGENTOPS_NAMESPACE, resource_name)

        display_name = getattr(engine, "display_name", None) or f"agent-{engine_id[:8]}"

        create_time: datetime | None = None
        if hasattr(engine, "gca_resource") and hasattr(engine.gca_resource, "create_time"):
            raw_time = engine.gca_resource.create_time
            if raw_time:
                if isinstance(raw_time, datetime):
                    create_time = raw_time
                else:
                    create_time_str = str(raw_time).replace("Z", "+00:00")
                    try:
                        create_time = datetime.fromisoformat(create_time_str)
                    except ValueError:
                        create_time = None

        labels = dict(getattr(engine, "labels", {}) or {})
        model_name = labels.get("model") or labels.get("model_name") or "gemini-1.5-pro"

        metadata: dict[str, Any] = {
            "gcp_engine_id": engine_id,
            "resource_name": resource_name,
            "labels": labels,
        }
        if create_time:
            metadata["gcp_create_time"] = create_time.isoformat()

        return AgentCreate(
            id=agent_uuid,
            name=self._slugify(display_name),
            display_name=display_name,
            deployment_type="vertex_ai",
            endpoint_url=resource_name,
            model_name=model_name,
            region=self._region,
            gcp_project=self._project_id,
            status="healthy",
            source="vertex_ai",
            metadata=metadata,
        )

    @staticmethod
    def _slugify(name: str) -> str:
        slug = name.lower().strip().replace(" ", "-")
        return "".join(c if c.isalnum() or c in "-_" else "-" for c in slug)[:255]

    async def sync_to_database(self) -> DiscoverySyncSummary:
        await self.initialize()

        summary = DiscoverySyncSummary(
            discovered=0, created=0, updated=0, unchanged=0
        )
        active_endpoints: set[str] = set()

        try:
            engines = await self.list_reasoning_engines()
        except Exception as exc:
            logger.exception("Failed to list reasoning engines", extra={"component": "vertex_discovery"})
            summary.errors.append(str(exc))
            return summary

        summary.discovered = len(engines)

        for engine in engines:
            try:
                agent_data = self.parse_reasoning_engine(engine)
                if agent_data.endpoint_url:
                    active_endpoints.add(agent_data.endpoint_url)

                existing = None
                if agent_data.endpoint_url:
                    existing = await self._repository.get_agent_by_endpoint(
                        agent_data.endpoint_url
                    )

                agent, created = await self._repository.upsert_agent(agent_data)

                if created:
                    summary.created += 1
                elif existing and self._agent_changed(existing, agent_data):
                    summary.updated += 1
                else:
                    summary.unchanged += 1

                summary.agents.append(AgentRead.from_orm_agent(agent))
            except Exception as exc:
                logger.error(
                    "Failed to sync engine: %s",
                    exc,
                    extra={"component": "vertex_discovery"},
                )
                summary.errors.append(str(exc))

        stale = await self._repository.mark_stale_agents(active_endpoints, "vertex_ai")
        if stale:
            logger.info(
                "Marked stale agents inactive",
                extra={"component": "vertex_discovery", "count": stale},
            )

        logger.info(
            "Vertex AI sync complete: discovered=%s created=%s updated=%s unchanged=%s",
            summary.discovered,
            summary.created,
            summary.updated,
            summary.unchanged,
            extra={"component": "vertex_discovery"},
        )
        return summary

    @staticmethod
    def _agent_changed(existing: Any, incoming: AgentCreate) -> bool:
        return (
            existing.display_name != incoming.display_name
            or existing.status != incoming.status
            or existing.model_name != incoming.model_name
        )

    def parse_resource(self, raw: Any) -> AgentCreate:
        return self.parse_reasoning_engine(raw)

    async def test_connection(self) -> dict[str, Any]:
        """Lightweight connectivity test without DB writes."""
        await self.initialize()
        try:
            engines = await self.list_reasoning_engines()
            samples = []
            for engine in engines[:5]:
                parsed = self.parse_reasoning_engine(engine)
                samples.append(
                    {
                        "name": parsed.display_name,
                        "endpoint_url": parsed.endpoint_url,
                        "status": parsed.status,
                    }
                )
            return {
                "authenticated": True,
                "project_id": self._project_id,
                "region": self._region,
                "engine_count": len(engines),
                "message": f"Successfully connected. Found {len(engines)} reasoning engine(s).",
                "sample_engines": samples,
            }
        except Exception as exc:
            logger.exception("Vertex AI test failed", extra={"component": "vertex_discovery"})
            return {
                "authenticated": False,
                "project_id": self._project_id,
                "region": self._region,
                "engine_count": 0,
                "message": str(exc),
                "sample_engines": [],
            }
