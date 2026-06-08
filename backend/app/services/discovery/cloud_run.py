"""Cloud Run agent discovery service."""

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

# Stable namespace for UUID5 derived from Cloud Run resource names
_AGENTOPS_CR_NAMESPACE = uuid.UUID("7c9e6679-7425-40de-944b-e07fc1f90ae7")


class CloudRunDiscoveryService(BaseDiscoveryService):
    """
    Discovers Cloud Run services using the Cloud Run Admin API
    and syncs agent-like services to PostgreSQL.
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

        self._initialized = True
        logger.info(
            "Cloud Run discovery initialized",
            extra={
                "component": "cloud_run_discovery",
                "project_id": self._project_id,
                "regions": self._regions,
            },
        )

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("CloudRunDiscoveryService not initialized. Call initialize() first.")

    async def list_cloud_run_services(self) -> list[tuple[Any, str]]:
        """List Cloud Run services across all configured regions."""
        self._ensure_initialized()

        raw_region = self._settings.gcp_region or ""
        if "," in raw_region:
            regions = [r.strip() for r in raw_region.split(",") if r.strip()]
        elif raw_region and raw_region != "us-central1":
            regions = list(set([raw_region, "us-central1"]))
        else:
            # Scan common Cloud Run regions
            regions = [
                "us-central1",
                "us-west1",
                "us-east1",
                "us-east4",
                "europe-west1",
                "europe-west3",
                "asia-east1",
                "asia-northeast1",
                "asia-southeast1",
            ]

        tasks = [
            asyncio.to_thread(self._list_services_sync_in_region, self._project_id, region)
            for region in regions
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_services: list[tuple[Any, str]] = []
        for region, result in zip(regions, results):
            if isinstance(result, Exception):
                logger.warning(
                    "Skipped region %s during Cloud Run discovery: %s",
                    region,
                    result,
                    extra={"component": "cloud_run_discovery", "region": region},
                )
                continue
            for service in result:
                all_services.append((service, region))

        return all_services

    @staticmethod
    def _list_services_sync_in_region(project_id: str, region: str) -> list[Any]:
        """Synchronously list Cloud Run services in a single region."""
        from google.cloud import run_v2

        try:
            client = run_v2.ServicesClient()
            parent = f"projects/{project_id}/locations/{region}"
            request = run_v2.ListServicesRequest(parent=parent)
            services = list(client.list_services(request=request))

            logger.info(
                "Listed Cloud Run services",
                extra={"component": "cloud_run_discovery", "region": region, "count": len(services)},
            )
            return services
        except Exception as exc:
            raise RuntimeError(f"Cloud Run region {region} check failed: {exc}") from exc

    def parse_cloud_run_service(self, service: Any, region: str | None = None) -> AgentCreate:
        """Parse a Cloud Run service into an AgentCreate schema."""
        resource_name = getattr(service, "name", "") or str(service)
        # Cloud Run name format: projects/{project}/locations/{region}/services/{name}
        service_name = resource_name.split("/")[-1] if "/" in resource_name else resource_name
        agent_uuid = uuid.uuid5(_AGENTOPS_CR_NAMESPACE, resource_name)

        # Get the service URL
        uri = getattr(service, "uri", None) or ""

        # Extract display name
        display_name = service_name

        # Extract labels for model/framework info
        labels = dict(getattr(service, "labels", {}) or {})
        annotations = dict(getattr(service, "annotations", {}) or {})

        # Try to detect model from labels or annotations
        model_name = (
            labels.get("model")
            or labels.get("model_name")
            or annotations.get("model")
            or "unknown"
        )

        # Extract description from annotations
        description = annotations.get("description", "") or ""

        # Determine if service is reachable / healthy
        conditions = getattr(service, "conditions", []) or []
        status = "unknown"
        for cond in conditions:
            cond_type = getattr(cond, "type_", None) or getattr(cond, "type", "")
            cond_state = getattr(cond, "state", None)
            if cond_type == "Ready":
                # state is an enum; check for CONDITION_SUCCEEDED
                state_name = getattr(cond_state, "name", str(cond_state)) if cond_state else ""
                if state_name == "CONDITION_SUCCEEDED" or str(cond_state) == "1":
                    status = "healthy"
                else:
                    status = "degraded"
                break

        # Determine service region from resource name
        service_region = region
        if not service_region and "/" in resource_name:
            parts = resource_name.split("/")
            loc_idx = parts.index("locations") if "locations" in parts else -1
            if loc_idx >= 0 and loc_idx + 1 < len(parts):
                service_region = parts[loc_idx + 1]
        service_region = service_region or (self._regions[0] if self._regions else "us-central1")

        # Build metadata
        create_time = getattr(service, "create_time", None)
        metadata: dict[str, Any] = {
            "cloud_run_service_name": service_name,
            "resource_name": resource_name,
            "service_url": uri,
            "labels": labels,
            "annotations": {k: v for k, v in annotations.items() if len(v) < 500},
            "description": description,
        }
        if create_time:
            if isinstance(create_time, datetime):
                metadata["gcp_create_time"] = create_time.isoformat()
            else:
                metadata["gcp_create_time"] = str(create_time)

        return AgentCreate(
            id=agent_uuid,
            name=self._slugify(display_name),
            display_name=display_name,
            deployment_type="cloud_run",
            endpoint_url=uri,
            model_name=model_name,
            region=service_region,
            gcp_project=self._project_id,
            status=status,
            source="cloud_run",
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
        scanned_regions: set[str] = set()

        try:
            services = await self.list_cloud_run_services()
        except Exception as exc:
            logger.exception("Failed to list Cloud Run services", extra={"component": "cloud_run_discovery"})
            summary.errors.append(str(exc))
            return summary

        summary.discovered = len(services)

        for service, region in services:
            scanned_regions.add(region)
            try:
                agent_data = self.parse_cloud_run_service(service, region)
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
                    "Failed to sync Cloud Run service: %s",
                    exc,
                    extra={"component": "cloud_run_discovery"},
                )
                summary.errors.append(str(exc))

        stale = await self._repository.mark_stale_agents_in_regions(
            active_endpoints, "cloud_run", scanned_regions
        )
        if stale:
            logger.info(
                "Marked stale Cloud Run agents inactive",
                extra={"component": "cloud_run_discovery", "count": stale},
            )

        logger.info(
            "Cloud Run sync complete: discovered=%s created=%s updated=%s unchanged=%s",
            summary.discovered,
            summary.created,
            summary.updated,
            summary.unchanged,
            extra={"component": "cloud_run_discovery"},
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
        return self.parse_cloud_run_service(raw)

    async def test_connection(self) -> dict[str, Any]:
        """Lightweight connectivity test without DB writes."""
        await self.initialize()
        try:
            services = await self.list_cloud_run_services()
            samples = []
            for service, region in services[:5]:
                parsed = self.parse_cloud_run_service(service, region)
                samples.append(
                    {
                        "name": parsed.display_name,
                        "endpoint_url": parsed.endpoint_url,
                        "status": parsed.status,
                        "region": region,
                    }
                )
            return {
                "authenticated": True,
                "project_id": self._project_id,
                "region": ", ".join(self._regions),
                "service_count": len(services),
                "message": f"Successfully connected. Found {len(services)} Cloud Run service(s).",
                "sample_services": samples,
            }
        except Exception as exc:
            logger.exception("Cloud Run test failed", extra={"component": "cloud_run_discovery"})
            return {
                "authenticated": False,
                "project_id": self._project_id,
                "region": ", ".join(self._regions) if hasattr(self, "_regions") else "us-central1",
                "service_count": 0,
                "message": str(exc),
                "sample_services": [],
            }
