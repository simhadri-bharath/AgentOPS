"""Build Vertex eval inference DataFrames (notebook EvaluationDataIngestor pattern)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

# Columns that are never agent text output
_NON_RESPONSE_COLUMNS = frozenset(
    {
        "prompt",
        "session_inputs",
        "input",
        "intermediate_events",
        "agent_data",
        "eval_cases",
        "reference",
        "context",
        "history",
        "conversation_history",
        "conversation_plan",
        "starting_prompt",
    }
)


def build_inference_dataframe(rows: list[dict[str, str]]) -> pd.DataFrame:
    """
    Match vertexaireasoningengine.ipynb:
    columns prompt + session_inputs, with input mapped to prompt.
    """
    from vertexai import types

    session_inputs = types.evals.SessionInput(user_id="agentops_eval_user", state={})
    prompts: list[str] = []

    for row in rows:
        text = row.get("input", "").strip()
        context = row.get("context", "").strip() if row.get("context") else ""
        if context:
            text = f"Context:\n{context}\n\nUser:\n{text}"
        prompts.append(text)

    return pd.DataFrame(
        {
            "prompt": prompts,
            "session_inputs": [session_inputs] * len(prompts),
        }
    )


def collect_text_from_events(events: list[Any]) -> str:
    """Last model/agent text from ADK-style event dicts (matches Vertex evals SDK)."""
    if not events:
        return ""
    last_model = ""
    last_any = ""
    for event in events:
        if not isinstance(event, dict):
            continue
        text = _extract_text_from_event_dict(event)
        if not text:
            continue
        last_any = text
        author = (event.get("author") or "").lower()
        if author in ("model", "agent", "assistant") or not author:
            last_model = text
    return last_model or last_any


def extract_response_text(row: Any, df: pd.DataFrame) -> tuple[str, str | None]:
    """
    Parse agent response from run_inference output.
    Prefer `response` then `agent_data` then `intermediate_events` (Vertex SDK layout).
    """
    # 1. Official response column (notebook primary)
    if "response" in df.columns:
        text, err = _extract_from_cell(row["response"])
        if text:
            return text, None
        if err:
            return "", err

    # 2. agent_data — structured ADK / reasoning engine turns
    if "agent_data" in df.columns:
        text = _extract_from_agent_data(row["agent_data"])
        if text:
            return text, None

    # 3. intermediate_events from Vertex evals agent run
    if "intermediate_events" in df.columns:
        text = _extract_from_intermediate_events(row["intermediate_events"])
        if text:
            return text, None

    # 4. output alias
    if "output" in df.columns:
        text, err = _extract_from_cell(row["output"])
        if text:
            return text, None
        if err:
            return "", err

    # 5. Notebook fallback: unnamed integer column index 1 (only if not a metadata name)
    if len(df.columns) > 1:
        col_key = df.columns[1]
        if str(col_key) not in _NON_RESPONSE_COLUMNS and col_key not in (0, "0"):
            text, err = _extract_from_cell(row[col_key])
            if text:
                return text, None

    return "", "Empty agent response — check Reasoning Engine logs (notebook also reports empty generations)"


def _extract_from_cell(val: Any) -> tuple[str, str | None]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "", None

    # Vertex Content / ResponseCandidate objects
    try:
        from vertexai._genai._evals_data_converters import _get_content_text

        if hasattr(val, "parts"):
            text = _get_content_text(val)
            if text:
                return text.strip(), None
        if hasattr(val, "response") and val.response:
            text = _get_content_text(val.response)
            if text:
                return text.strip(), None
    except Exception:
        pass

    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return "", None
        if stripped in _NON_RESPONSE_COLUMNS:
            return "", None
        if stripped.startswith("{") or stripped.startswith("["):
            parsed_text, err = _extract_from_json_string(stripped)
            if parsed_text:
                return parsed_text, None
            if err:
                return "", err
        return stripped, None

    if isinstance(val, dict):
        if "error" in val:
            return "", str(val["error"])
        text = _extract_text_from_event_dict(val)
        if text:
            return text, None
        return "", None

    if isinstance(val, list):
        text = _extract_text_from_event_list(val)
        if text:
            return text, None
        return "", None

    text = str(val).strip()
    if text in _NON_RESPONSE_COLUMNS:
        return "", None
    return text, None


def _extract_from_json_string(stripped: str) -> tuple[str, str | None]:
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped, None

    if isinstance(parsed, dict) and "error" in parsed:
        return "", str(parsed.get("error", stripped))

    if isinstance(parsed, list):
        text = _extract_text_from_event_list(parsed)
        return text, None if text else ("", None)

    if isinstance(parsed, dict):
        text = _extract_text_from_event_dict(parsed)
        return text, None if text else ("", None)

    return "", None


def _extract_from_intermediate_events(events_val: Any) -> str:
    if events_val is None or (isinstance(events_val, float) and pd.isna(events_val)):
        return ""
    if isinstance(events_val, str):
        try:
            events_val = json.loads(events_val)
        except json.JSONDecodeError:
            return ""
    if isinstance(events_val, list):
        return collect_text_from_events(events_val)
    return ""


def _extract_from_agent_data(agent_data: Any) -> str:
    if agent_data is None or (isinstance(agent_data, float) and pd.isna(agent_data)):
        return ""

    if isinstance(agent_data, str):
        try:
            agent_data = json.loads(agent_data)
        except json.JSONDecodeError:
            return ""

    if isinstance(agent_data, dict):
        turns = agent_data.get("turns") or []
        all_events: list[Any] = []
        for turn in turns:
            all_events.extend(turn.get("events") or [])
        text = collect_text_from_events(all_events)
        if text:
            return text

    return ""


def _extract_text_from_event_list(events: list[Any]) -> str:
    if not events:
        return ""
    last = events[-1]
    if isinstance(last, dict):
        return _extract_text_from_event_dict(last)
    return ""


def _extract_text_from_event_dict(event: dict[str, Any]) -> str:
    try:
        parts = event.get("content", {}).get("parts", [])
        texts = []
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                texts.append(str(part["text"]))
        return "".join(texts).strip()
    except (AttributeError, TypeError, KeyError):
        return ""
