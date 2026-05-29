"""Direct Reasoning Engine stream_query (SDK-aligned fallback when run_inference is empty)."""

from __future__ import annotations

import json
import time
from typing import Any

from app.core.logging import get_logger
from app.services.evaluation.inference_dataset import (
    _extract_text_from_event_dict,
    collect_text_from_events,
)

logger = get_logger(__name__)


def stream_query_prompt(
    *,
    project_id: str,
    region: str,
    resource_name: str,
    prompt: str,
    user_id: str = "agentops_eval_user",
) -> tuple[str, list[dict[str, Any]], str | None]:
    """
    Invoke deployed agent via Client.agent_engines (same path as Vertex evals SDK).
    Returns (text, raw_events, error).
    """
    import vertexai
    from vertexai import Client

    vertexai.init(project=project_id, location=region)
    client = Client(project=project_id, location=region)
    agent_engine = client.agent_engines.get(name=resource_name)

    session_id = _create_session(agent_engine, user_id=user_id)
    events: list[dict[str, Any]] = []

    start = time.perf_counter()
    try:
        for event in agent_engine.stream_query(  # type: ignore[attr-defined]
            user_id=user_id,
            session_id=session_id,
            message=prompt,
        ):
            if isinstance(event, dict):
                events.append(event)
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.warning(
            "stream_query failed after %sms: %s",
            elapsed_ms,
            exc,
            extra={"component": "reasoning_engine_direct"},
        )
        return "", events, str(exc)

    text = collect_text_from_events(events)
    if not text and events:
        # SDK uses last event parts[0].text only — mirror that, then scan all parts
        last = events[-1]
        try:
            parts = last.get("content", {}).get("parts", [])
            for part in parts:
                if isinstance(part, dict) and part.get("text"):
                    text = str(part["text"]).strip()
                    break
        except (AttributeError, TypeError, KeyError):
            pass

    if not text:
        return (
            "",
            events,
            "Agent stream_query returned no text in events (check Vertex agent logs)",
        )
    return text, events, None


def _create_session(agent_engine: Any, *, user_id: str) -> str:
    try:
        session = agent_engine.create_session(user_id=user_id)  # type: ignore[attr-defined]
        return session["id"]
    except AttributeError:
        if agent_engine.api_resource is None or agent_engine.api_client is None:
            raise RuntimeError("Cannot create session: agent engine API resource missing") from None
        from vertexai import types

        operation = agent_engine.api_client.sessions.create(
            name=agent_engine.api_resource.name,
            user_id=user_id,
            config=types.CreateAgentEngineSessionConfig(),
        )
        if operation.response and operation.response.name:
            return operation.response.name.split("/")[-1]
        raise RuntimeError(f"Session create failed: {operation.error}")


def events_preview(events: list[dict[str, Any]], max_len: int = 500) -> str:
    try:
        return json.dumps(events[:5], default=str)[:max_len]
    except TypeError:
        return str(events)[:max_len]
