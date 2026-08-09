"""Agent Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import ORMBase


AGENT_TYPES: list[str] = [
    "rag",
    "tool_calling",
    "conversational",
    "task",
    "multi_agent",
    "unknown",
]

CAPABILITIES: list[str] = [
    "retrieval",
    "tool_use",
    "reasoning",
    "code_execution",
    "external_api",
    "memory",
    "multi_agent",
]

ENVIRONMENTS: list[str] = ["development", "staging", "production", "unknown"]


class AgentBase(ORMBase):
    name: str
    display_name: str | None = None
    deployment_type: str
    endpoint_url: str | None = None
    model_name: str | None = None
    region: str | None = None
    gcp_project: str | None = None
    status: str = "unknown"
    source: str = "manual"
    agent_type: str = "unknown"
    capabilities: list[str] = Field(default_factory=list)
    purpose: str | None = None
    environment: str = "unknown"
    invocation_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentCreate(AgentBase):
    id: uuid.UUID | None = None


class AgentUpdate(ORMBase):
    name: str | None = None
    display_name: str | None = None
    deployment_type: str | None = None
    endpoint_url: str | None = None
    model_name: str | None = None
    region: str | None = None
    gcp_project: str | None = None
    status: str | None = None
    source: str | None = None
    agent_type: str | None = None
    capabilities: list[str] | None = None
    purpose: str | None = None
    environment: str | None = None
    invocation_config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    discovered_at: datetime | None = None
    last_seen_at: datetime | None = None


class AgentPatch(ORMBase):
    """User-editable agent profile fields."""

    display_name: str | None = None
    agent_type: str | None = None
    capabilities: list[str] | None = None
    purpose: str | None = None
    environment: str | None = None
    invocation_config: dict[str, Any] | None = None


class AgentRead(AgentBase):
    id: uuid.UUID
    discovered_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_agent(cls, agent: Any) -> "AgentRead":
        return cls(
            id=agent.id,
            name=agent.name,
            display_name=agent.display_name,
            deployment_type=agent.deployment_type,
            endpoint_url=agent.endpoint_url,
            model_name=agent.model_name,
            region=agent.region,
            gcp_project=agent.gcp_project,
            status=agent.status,
            source=agent.source,
            agent_type=agent.agent_type or "unknown",
            capabilities=list(agent.capabilities or []),
            purpose=agent.purpose,
            environment=agent.environment or "unknown",
            invocation_config=dict(agent.invocation_config or {}),
            metadata=agent.extra_metadata or {},
            discovered_at=agent.discovered_at,
            last_seen_at=agent.last_seen_at,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )


class AgentListResponse(ORMBase):
    items: list[AgentRead]
    total: int


class DiscoverySyncSummary(ORMBase):
    discovered: int
    created: int
    updated: int
    unchanged: int
    errors: list[str] = Field(default_factory=list)
    agents: list[AgentRead] = Field(default_factory=list)


class VertexAITestResponse(ORMBase):
    authenticated: bool
    project_id: str | None = None
    region: str | None = None
    engine_count: int = 0
    message: str
    sample_engines: list[dict[str, Any]] = Field(default_factory=list)


class AgentInvokeTestRequest(ORMBase):
    prompt: str = Field(min_length=1, max_length=8000)
    context: str | None = None


class AgentInvokeTestResponse(ORMBase):
    output: str
    latency_ms: int
    error: str | None = None
    via: str
    events_preview: str | None = None
