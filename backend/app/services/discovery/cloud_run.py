"""Cloud Run discovery stub for future implementation."""

from app.core.logging import get_logger
from app.schemas.agent import DiscoverySyncSummary
from app.services.discovery.base import BaseDiscoveryService

logger = get_logger(__name__)


class CloudRunDiscoveryService(BaseDiscoveryService):
    """Placeholder for Cloud Run agent discovery."""

    async def initialize(self) -> None:
        logger.info("Cloud Run discovery not yet implemented", extra={"component": "discovery"})

    async def sync_to_database(self) -> DiscoverySyncSummary:
        return DiscoverySyncSummary(
            discovered=0, created=0, updated=0, unchanged=0, errors=["Not implemented"]
        )

    def parse_resource(self, raw: object):
        raise NotImplementedError("Cloud Run discovery not implemented")
