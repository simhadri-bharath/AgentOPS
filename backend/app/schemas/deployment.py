"""Deployment inventory schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field, field_validator

from app.schemas.agent import AGENT_TYPES, CAPABILITIES, ENVIRONMENTS
from app.schemas.common import ORMBase


class DeploymentRead(ORMBase):
    engine_id: str
    resource_name: str
    display_name: str
    region: str
    framework: str | None = None
    description: str | None = None
    class_methods: list[str] = Field(default_factory=list)
    custom_methods: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    session_count: int = 0
    session_count_capped: bool = False
    sessions_inspected: int = 0
    last_activity_at: str | None = None
    observed_tools: list[str] = Field(default_factory=list)
    observed_authors: list[str] = Field(default_factory=list)
    agent_type_guess: str = "unknown"
    capabilities_guess: list[str] = Field(default_factory=list)
    purpose_guess: str | None = None
    onboarded_agent_id: uuid.UUID | None = None
    probe_error: str | None = None


class DeploymentListResponse(ORMBase):
    items: list[DeploymentRead]
    total: int
    project: str | None = None
    regions: list[str] = Field(default_factory=list)


class DeploymentDetail(DeploymentRead):
    spec: dict[str, Any] = Field(default_factory=dict)
    recent_sessions: list[dict[str, Any]] = Field(default_factory=list)


class DeploymentOnboardRequest(ORMBase):
    engine_id: str
    region: str | None = None
    # No default: the caller must state whether this is production before the
    # platform will start sending traffic at it.
    environment: str
    agent_type: str | None = None
    capabilities: list[str] | None = None
    purpose: str | None = None
    display_name: str | None = None

    @field_validator("environment")
    @classmethod
    def _valid_environment(cls, value: str) -> str:
        if value not in ENVIRONMENTS:
            raise ValueError(f"environment must be one of {ENVIRONMENTS}")
        return value

    @field_validator("agent_type")
    @classmethod
    def _valid_agent_type(cls, value: str | None) -> str | None:
        if value is not None and value not in AGENT_TYPES:
            raise ValueError(f"agent_type must be one of {AGENT_TYPES}")
        return value

    @field_validator("capabilities")
    @classmethod
    def _valid_capabilities(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        unknown = [c for c in value if c not in CAPABILITIES]
        if unknown:
            raise ValueError(f"unknown capabilities {unknown}; valid: {CAPABILITIES}")
        return value
