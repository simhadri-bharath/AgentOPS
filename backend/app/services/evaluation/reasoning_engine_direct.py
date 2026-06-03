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
    Invoke deployed agent via Client.agent_engines service API.
    Returns (text, raw_events, error).

    Uses client.agent_engines._stream_query() which is the correct
    GenAI SDK method for querying agent engines. The AgentEngine object
    returned by .get() is a Pydantic data model without query methods.
    """
    import vertexai
    from vertexai import Client

    vertexai.init(project=project_id, location=region)
    client = Client(project=project_id, location=region)

    # Create a session via the service API
    session_id = _create_session(client, resource_name=resource_name, user_id=user_id)
    events: list[dict[str, Any]] = []

    start = time.perf_counter()
    try:
        # Use the service-level _stream_query (the AgentEngine pydantic model
        # returned by .get() does NOT have stream_query/query methods).
        for event in client.agent_engines._stream_query(
            name=resource_name,
            config={
                "class_method": "stream_query",
                "input": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": prompt,
                },
            },
        ):
            if isinstance(event, dict):
                events.append(event)
            else:
                # Some SDK versions return typed objects; convert to dict
                try:
                    events.append(event.to_json_dict() if hasattr(event, "to_json_dict") else {"raw": str(event)})
                except Exception:
                    events.append({"raw": str(event)})
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        err_str = str(exc)
        logger.warning(
            "stream_query failed after %sms: %s",
            elapsed_ms,
            exc,
            extra={"component": "reasoning_engine_direct"},
        )
        # If stream_query class method is not found, try plain query
        if "not found" in err_str or "not supported" in err_str.lower():
            logger.info(
                "stream_query not available, trying query fallback",
                extra={"component": "reasoning_engine_direct"},
            )
            return _query_fallback(client, resource_name, prompt, user_id, session_id)
        return "", events, err_str

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


def _query_fallback(
    client: Any,
    resource_name: str,
    prompt: str,
    user_id: str,
    session_id: str,
) -> tuple[str, list[dict[str, Any]], str | None]:
    """Fallback: try client.agent_engines._query() if stream_query is unavailable."""
    start = time.perf_counter()
    try:
        response = client.agent_engines._query(
            name=resource_name,
            config={
                "class_method": "query",
                "input": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": prompt,
                },
            },
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        # Extract text from the response
        text = ""
        events: list[dict[str, Any]] = []
        if response:
            resp_dict = response.to_json_dict() if hasattr(response, "to_json_dict") else {}
            events = [resp_dict] if resp_dict else []
            # Try to extract output text from response
            text = _extract_text_from_query_response(resp_dict)
        if text:
            return text, events, None
        return "", events, "Agent query returned no text (check Vertex agent logs)"
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.warning(
            "query fallback also failed after %sms: %s",
            elapsed_ms,
            exc,
            extra={"component": "reasoning_engine_direct"},
        )
        return "", [], str(exc)


def _extract_text_from_query_response(resp: dict[str, Any]) -> str:
    """Best-effort text extraction from a query response dict."""
    if not resp or not isinstance(resp, dict):
        return ""
    # Try common response shapes
    for key in ("output", "response", "text", "result"):
        if key in resp:
            val = resp[key]
            if isinstance(val, str) and val.strip():
                return val.strip()
            if isinstance(val, dict):
                for sub_key in ("text", "output", "content"):
                    if sub_key in val and isinstance(val[sub_key], str):
                        return val[sub_key].strip()
    # Try content.parts[].text
    try:
        parts = resp.get("content", {}).get("parts", [])
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                return str(part["text"]).strip()
    except (AttributeError, TypeError, KeyError):
        pass
    return ""


def _create_session(client: Any, *, resource_name: str, user_id: str) -> str:
    """Create a session using the service-level API (client.agent_engines)."""
    try:
        operation = client.agent_engines.create_session(
            name=resource_name,
            user_id=user_id,
        )
        # AgentEngineSessionOperation wraps the response
        if hasattr(operation, "response") and operation.response:
            resp = operation.response
            if hasattr(resp, "name") and resp.name:
                return resp.name.split("/")[-1]
            if isinstance(resp, dict) and resp.get("name"):
                return resp["name"].split("/")[-1]
        # Some SDK versions return the session directly
        if hasattr(operation, "name") and operation.name:
            return operation.name.split("/")[-1]
        if isinstance(operation, dict) and operation.get("id"):
            return operation["id"]
        # Generate a fallback session ID
        import uuid
        logger.warning(
            "Could not extract session ID from operation, using generated ID",
            extra={"component": "reasoning_engine_direct"},
        )
        return f"eval-session-{uuid.uuid4().hex[:8]}"
    except Exception as exc:
        logger.warning(
            "Session creation failed: %s — using generated session ID",
            exc,
            extra={"component": "reasoning_engine_direct"},
        )
        import uuid
        return f"eval-session-{uuid.uuid4().hex[:8]}"


def events_preview(events: list[dict[str, Any]], max_len: int = 500) -> str:
    try:
        return json.dumps(events[:5], default=str)[:max_len]
    except TypeError:
        return str(events)[:max_len]
