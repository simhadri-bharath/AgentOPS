"""Extract observability correlation IDs from agent invocation payloads."""

from __future__ import annotations

import uuid
from typing import Any


_TRACE_KEYS = (
    "trace_id",
    "traceId",
    "trace",
    "span_id",
    "spanId",
    "x_trace_id",
    "otel_trace_id",
)


def extract_trace_id(raw: Any | None, *, fallback_prefix: str = "redteam") -> str | None:
    """Walk raw invoke payload for trace identifiers; generate correlation id if missing."""
    if raw is None:
        return None

    found = _search_dict(raw, _TRACE_KEYS)
    if found:
        return str(found)[:256]

    if isinstance(raw, list):
        for item in raw:
            found = _search_dict(item, _TRACE_KEYS)
            if found:
                return str(found)[:256]

    return None


def correlation_trace_id(run_id: str, case_id: str) -> str:
    """Deterministic correlation id for logs/traces when platform trace unavailable."""
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, f"agentops-redteam:{run_id}:{case_id}")
    return f"redteam-{ns.hex[:24]}"


def _search_dict(obj: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and v:
                return str(v)
            nested = _search_dict(v, keys)
            if nested:
                return nested
    elif isinstance(obj, list):
        for item in obj:
            nested = _search_dict(item, keys)
            if nested:
                return nested
    return None
