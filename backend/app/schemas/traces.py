"""Trace & span Pydantic schemas for Cloud Trace API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import ORMBase


class SpanRead(ORMBase):
    """A single span within a trace."""

    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: str = "INTERNAL"
    start_time: datetime
    end_time: datetime
    duration_ms: float = 0.0
    status: str = "OK"
    labels: dict[str, str] = Field(default_factory=dict)

    # Extracted convenience fields (parsed from labels)
    agent_name: str | None = None
    operation: str | None = None
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    session_id: str | None = None
    conversation_id: str | None = None


class TraceRead(ORMBase):
    """A single trace containing multiple spans."""

    trace_id: str
    project_id: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_ms: float = 0.0
    span_count: int = 0
    status: str = "OK"
    root_span_name: str | None = None
    agent_name: str | None = None
    session_id: str | None = None
    spans: list[SpanRead] = Field(default_factory=list)


class TraceListResponse(ORMBase):
    """Paginated list of traces."""

    items: list[TraceRead]
    total: int
    has_more: bool = False


class TraceDetailResponse(ORMBase):
    """Full trace detail with all spans."""

    trace: TraceRead
    span_tree: list[SpanNode] = Field(default_factory=list)


class SpanNode(ORMBase):
    """Span with nested children for building a tree/DAG view."""

    span: SpanRead
    children: list[SpanNode] = Field(default_factory=list)
    depth: int = 0


# Fix forward reference
TraceDetailResponse.model_rebuild()
