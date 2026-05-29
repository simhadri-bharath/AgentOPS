"""Base discovery service interface."""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.agent import AgentCreate, DiscoverySyncSummary


class BaseDiscoveryService(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        ...

    @abstractmethod
    async def sync_to_database(self) -> DiscoverySyncSummary:
        ...

    @abstractmethod
    def parse_resource(self, raw: Any) -> AgentCreate:
        ...
