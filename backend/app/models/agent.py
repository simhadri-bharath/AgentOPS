"""Agent SQLAlchemy model."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    deployment_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gcp_project: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")

    # What the agent is for. agent_type and capabilities are deliberately
    # separate: an agent can be multi_agent AND retrieval-backed, and type alone
    # would recommend the wrong metrics for it.
    agent_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", index=True
    )
    capabilities: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]", default=list
    )
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Enforcement hook for red-team gating; recorded now to avoid a backfill later.
    environment: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown", index=True
    )
    invocation_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}", default=dict
    )
    discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
        default=dict,
    )
