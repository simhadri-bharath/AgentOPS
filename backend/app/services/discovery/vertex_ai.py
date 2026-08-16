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


def agent_uuid_for_resource(resource_name: str) -> uuid.UUID:
    """Deterministic agent ID for a GCP resource, so re-discovery is idempotent."""
    return uuid.uuid5(_AGENTOPS_NAMESPACE, resource_name)


def slugify(name: str) -> str:
    slug = name.lower().strip().replace(" ", "-")
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in slug)[:255]


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
        self._regions: list[str] = []

    async def initialize(self) -> None:
        auth = require_adc()
        self._project_id = self._settings.gcp_project_id or auth.project_id
        
        # Support a comma-separated list of regions
        raw_regions = self._settings.gcp_region or "us-central1"
        self._regions = [r.strip() for r in raw_regions.split(",") if r.strip()]

        if not self._project_id:
            raise RuntimeError(
                "GCP project ID is required. Set GCP_PROJECT_ID in .env or "
                "configure your gcloud default project."
            )

        # Pre-verify credentials by initializing once in the first region
        if self._regions:
            await asyncio.to_thread(self._init_vertex_sdk, self._project_id, self._regions[0])
        self._initialized = True
        logger.info(
            "Vertex AI SDK initialized for multi-region scanning",
            extra={
                "component": "vertex_discovery",
                "project_id": self._project_id,
                "regions": self._regions,
            },
        )

    @staticmethod
    def _init_vertex_sdk(project_id: str, location: str) -> None:
        import vertexai

        vertexai.init(project=project_id, location=location)

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("VertexAIDiscoveryService not initialized. Call initialize() first.")

    async def list_reasoning_engines(self) -> list[tuple[Any, str]]:
        self._ensure_initialized()
        
        # If the user specified explicit regions (with comma), respect it.
        # Otherwise, scan ALL major globally supported Vertex AI Reasoning Engine regions automatically!
        raw_region = self._settings.gcp_region or ""
        if "," in raw_region:
            regions = [r.strip() for r in raw_region.split(",") if r.strip()]
        elif raw_region and raw_region != "us-central1":
            # Respect custom non-default region but also include common ones
            regions = list(set([raw_region, "us-central1", "us-west1"]))
        else:
            # Complete list of common globally supported Vertex AI Reasoning Engine / Agent Runtime regions
            regions = [
                "us-central1",
                "us-west1",
                "us-east1",
                "us-east4",
                "europe-west1",
                "europe-west3",
                "europe-west9",
                "asia-east1",
                "asia-northeast1",
                "asia-southeast1",
            ]

        # Execute all regional queries concurrently in parallel
        tasks = [
            asyncio.to_thread(self._list_engines_sync_in_region, self._project_id, region)
            for region in regions
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_engines: list[tuple[Any, str]] = []
        for region, result in zip(regions, results):
            if isinstance(result, Exception):
                logger.warning(
                    "Skipped region %s during discovery (either unsupported or not enabled in your project): %s",
                    region,
                    result,
                    extra={"component": "vertex_discovery", "region": region},
                )
                continue
            for engine in result:
                all_engines.append((engine, region))
                
        return all_engines

    @staticmethod
    def _list_engines_sync_in_region(project_id: str, region: str) -> list[Any]:
        import vertexai
        from vertexai.preview import reasoning_engines

        try:
            vertexai.init(project=project_id, location=region)
            deployed = reasoning_engines.ReasoningEngine.list()
            if deployed is None:
                engines: list[Any] = []
            elif isinstance(deployed, list):
                engines = deployed
            else:
                engines = list(deployed)

            logger.info(
                "Listed reasoning engines",
                extra={"component": "vertex_discovery", "region": region, "count": len(engines)},
            )
            return engines
        except Exception as exc:
            # Raise exception so asyncio.gather can gracefully catch it per region
            raise RuntimeError(f"Region {region} check failed: {exc}") from exc

    def parse_reasoning_engine(self, engine: Any, region: str | None = None) -> AgentCreate:
        resource_name = getattr(engine, "resource_name", None) or str(engine)
        engine_id = resource_name.split("/")[-1]
        agent_uuid = agent_uuid_for_resource(resource_name)

        display_name = getattr(engine, "display_name", None) or f"agent-{engine_id[:8]}"

        create_time: datetime | None = None
        if hasattr(engine, "gca_resource") and hasattr(engine.gca_resource, "create_time"):
            gca = engine.gca_resource
            raw_time = getattr(gca, "create_time", None)
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

        # Fallback if region is not supplied
        engine_region = region or (self._regions[0] if self._regions else "us-central1")

        return AgentCreate(
            id=agent_uuid,
            name=self._slugify(display_name),
            display_name=display_name,
            deployment_type="vertex_ai",
            endpoint_url=resource_name,
            model_name=model_name,
            region=engine_region,
            gcp_project=self._project_id,
            status="healthy",
            source="vertex_ai",
            metadata=metadata,
        )

    @staticmethod
    def _slugify(name: str) -> str:
        return slugify(name)

    async def sync_to_database(self) -> DiscoverySyncSummary:
        await self.initialize()

        summary = DiscoverySyncSummary(
            discovered=0, created=0, updated=0, unchanged=0
        )
        active_endpoints: set[str] = set()
        scanned_regions: set[str] = set()

        try:
            engines = await self.list_reasoning_engines()
        except Exception as exc:
            logger.exception("Failed to list reasoning engines", extra={"component": "vertex_discovery"})
            summary.errors.append(str(exc))
            return summary

        summary.discovered = len(engines)

        for engine, region in engines:
            scanned_regions.add(region)
            try:
                agent_data = self.parse_reasoning_engine(engine, region)
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

        stale = await self._repository.mark_stale_agents_in_regions(
            active_endpoints, "vertex_ai", scanned_regions
        )
        if stale:
            logger.info(
                "Marked stale agents inactive",
                extra={"component": "vertex_discovery", "count": stale},
            )

        # Agents discovered while GCP_PROJECT_ID pointed at a different project
        # stay in the table after the setting changes, and there is no way to
        # reach them any more. Mark them so they are visibly out of scope rather
        # than sitting in the list looking evaluable.
        orphaned = await self._repository.mark_agents_outside_project(self._project_id)
        if orphaned:
            logger.warning(
                "Marked %s agent(s) inactive: they belong to a different GCP project "
                "than the configured %s",
                orphaned,
                self._project_id,
                extra={"component": "vertex_discovery"},
            )
            summary.errors.append(
                f"{orphaned} agent(s) from another project were marked inactive. "
                f"Configured project is {self._project_id}."
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
            for engine, region in engines[:5]:
                parsed = self.parse_reasoning_engine(engine, region)
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
                "region": ", ".join(self._regions),
                "engine_count": len(engines),
                "message": f"Successfully connected. Found {len(engines)} reasoning engine(s).",
                "sample_engines": samples,
            }
        except Exception as exc:
            logger.exception("Vertex AI test failed", extra={"component": "vertex_discovery"})
            return {
                "authenticated": False,
                "project_id": self._project_id,
                "region": ", ".join(self._regions) if hasattr(self, "_regions") else "us-central1",
                "engine_count": 0,
                "message": str(exc),
                "sample_engines": [],
            }
