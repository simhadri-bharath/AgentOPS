"""Google session events -> AgentEvent[] -> Trace + Span[].

This is the only module that understands the Agent Engine event schema. Its
output is what every metric executor consumes, so the shape of a functionCall
part is a detail that stops here.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.core.logging import get_logger
from app.services.evaluation.tool_kinds import (
    RetrievalDoc,
    ToolKind,
    classify_tool,
    extract_retrieval_docs,
)
from app.services.evaluation.trace_model import (
    AgentEvent,
    EventType,
    Span,
    SpanKind,
    ToolCall,
    Trace,
)

logger = get_logger(__name__)


def normalize_events(
    raw_events: Iterable[dict[str, Any]], *, session_id: str = ""
) -> list[AgentEvent]:
    """Flatten Google session events into normalized events.

    One raw event can carry several parts (a text part and a functionCall in the
    same message), so this is one-to-many, not one-to-one.
    """
    events: list[AgentEvent] = []
    seq = 0
    for raw in raw_events:
        author = raw.get("author") or ""
        invocation_id = raw.get("invocationId") or raw.get("invocation_id") or ""
        event_name = raw.get("name") or ""
        event_id = raw.get("id") or (event_name.split("/")[-1] if event_name else f"e{seq}")
        timestamp = raw.get("timestamp")
        tokens_in, tokens_out = _usage(raw)
        state_delta = ((raw.get("actions") or {}).get("stateDelta")) or {}
        error_code = raw.get("errorCode")
        error_message = raw.get("errorMessage")

        parts = (raw.get("content") or {}).get("parts") or []
        made_event = False
        # Usage is reported per raw event. Attach it to the first normalized
        # event derived from it: assigning per part would multiply the token
        # count, assigning only to text parts would drop the tokens the model
        # spent deciding to call a tool.
        usage_pending = True

        for part in parts:
            base = dict(
                invocation_id=invocation_id,
                session_id=session_id or _session_of(event_name),
                timestamp=timestamp,
                author=author,
                raw_event=raw,
            )
            if "functionCall" in part:
                call = part["functionCall"] or {}
                events.append(
                    AgentEvent(
                        event_id=f"{event_id}#{seq}",
                        seq=seq,
                        event_type=EventType.TOOL_CALL,
                        role="assistant",
                        tool_name=call.get("name"),
                        tool_args=dict(call.get("args") or {}),
                        **base,
                    )
                )
            elif "functionResponse" in part:
                response = part["functionResponse"] or {}
                payload = response.get("response", response)
                events.append(
                    AgentEvent(
                        event_id=f"{event_id}#{seq}",
                        seq=seq,
                        event_type=EventType.TOOL_RESULT,
                        role="tool",
                        tool_name=response.get("name"),
                        tool_result=payload,
                        error_message=_tool_error(payload),
                        **base,
                    )
                )
            elif isinstance(part.get("text"), str):
                is_user = author == "user"
                events.append(
                    AgentEvent(
                        event_id=f"{event_id}#{seq}",
                        seq=seq,
                        event_type=EventType.USER_MESSAGE
                        if is_user
                        else EventType.AGENT_MESSAGE,
                        role="user" if is_user else "assistant",
                        text=part["text"],
                        **base,
                    )
                )
            else:
                continue
            if usage_pending:
                events[-1].tokens_in = tokens_in
                events[-1].tokens_out = tokens_out
                usage_pending = False
            seq += 1
            made_event = True

        # An event can carry only a state change or only an error -- no parts at
        # all. Those still matter for trace health, so they are not dropped.
        if not made_event and (state_delta or error_code or error_message):
            events.append(
                AgentEvent(
                    event_id=f"{event_id}#{seq}",
                    invocation_id=invocation_id,
                    session_id=session_id or _session_of(event_name),
                    seq=seq,
                    timestamp=timestamp,
                    author=author,
                    event_type=EventType.ERROR if error_message else EventType.STATE_UPDATE,
                    state_delta=dict(state_delta),
                    error_code=error_code,
                    error_message=error_message,
                    raw_event=raw,
                )
            )
            seq += 1

        if state_delta and made_event:
            events[-1].state_delta = dict(state_delta)

    return events


def _session_of(event_name: str) -> str:
    if "/sessions/" in event_name:
        return event_name.split("/sessions/")[1].split("/")[0]
    return ""


def _usage(raw: dict[str, Any]) -> tuple[int, int]:
    """Token counts, which Agent Engine attaches per event."""
    usage = raw.get("usageMetadata") or raw.get("usage_metadata") or {}
    meta = raw.get("eventMetadata") or {}
    if not usage and isinstance(meta.get("usageMetadata"), dict):
        usage = meta["usageMetadata"]
    return (
        int(usage.get("promptTokenCount") or usage.get("prompt_token_count") or 0),
        int(usage.get("candidatesTokenCount") or usage.get("candidates_token_count") or 0),
    )


def _tool_error(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("error", "error_message", "errorMessage"):
            value = payload.get(key)
            if value:
                return str(value)[:500]
    return None


def group_by_invocation(events: list[AgentEvent]) -> dict[str, list[AgentEvent]]:
    """Group events into turns.

    invocationId is what ties a user message to the tool calls and sub-agent
    handoffs it triggered. Events without one are bucketed together rather than
    dropped.
    """
    grouped: dict[str, list[AgentEvent]] = {}
    for event in events:
        grouped.setdefault(event.invocation_id or "_ungrouped", []).append(event)
    for bucket in grouped.values():
        bucket.sort(key=lambda e: (e.timestamp or "", e.seq))
    return grouped


def build_trace(
    events: list[AgentEvent],
    *,
    invocation_id: str = "",
    session_id: str = "",
    tool_overrides: dict[str, str] | None = None,
) -> Trace:
    """Assemble one turn's events into a scoreable trace with spans."""
    trace = Trace(
        invocation_id=invocation_id or (events[0].invocation_id if events else ""),
        session_id=session_id or (events[0].session_id if events else ""),
        events=list(events),
    )

    pending_calls: dict[str, AgentEvent] = {}
    span_seq = 0
    current_agent_span: Span | None = None

    for event in events:
        if event.author and event.author != "user" and event.author not in trace.agent_path:
            trace.agent_path.append(event.author)
        trace.tokens_in += event.tokens_in
        trace.tokens_out += event.tokens_out

        if event.event_type is EventType.USER_MESSAGE:
            # Last user message wins: a turn has exactly one prompt, and a
            # re-ask inside the same invocation is the real input.
            trace.input = event.text
            continue

        if event.event_type is EventType.TOOL_CALL:
            pending_calls[event.tool_name or ""] = event
            trace.tool_calls += 1
            continue

        if event.event_type is EventType.TOOL_RESULT:
            call = pending_calls.pop(event.tool_name or "", None)
            args = call.tool_args if call else {}
            kind = classify_tool(
                event.tool_name or "", event.tool_result, overrides=tool_overrides
            )
            docs = (
                extract_retrieval_docs(event.tool_result)
                if kind is ToolKind.RETRIEVAL
                else []
            )
            trace.trajectory.append(
                ToolCall(
                    name=event.tool_name or "",
                    args=dict(args),
                    output=event.tool_result,
                    error=event.error_message,
                )
            )
            trace.retrieval_context.extend(docs)
            span_seq += 1
            trace.spans.append(
                Span(
                    span_id=f"{trace.invocation_id}:tool:{span_seq}",
                    parent_span_id=current_agent_span.span_id if current_agent_span else None,
                    kind=SpanKind.TOOL,
                    author=event.author,
                    invocation_id=trace.invocation_id,
                    seq=span_seq,
                    input=_render(args),
                    output=_render(event.tool_result),
                    tool_name=event.tool_name,
                    tool_args=dict(args),
                    tool_result=event.tool_result,
                    tool_kind=kind,
                    error=event.error_message,
                    tool_calls=1,
                    # Tokens the model spent deciding to make this call.
                    tokens_in=(call.tokens_in if call else 0) + event.tokens_in,
                    tokens_out=(call.tokens_out if call else 0) + event.tokens_out,
                    retrieval_context=docs,
                )
            )
            continue

        if event.event_type is EventType.AGENT_MESSAGE:
            trace.llm_calls += 1
            span_seq += 1
            span = Span(
                span_id=f"{trace.invocation_id}:agent:{span_seq}",
                kind=SpanKind.AGENT,
                author=event.author,
                invocation_id=trace.invocation_id,
                seq=span_seq,
                input=trace.input,
                output=event.text,
                llm_calls=1,
                tokens_in=event.tokens_in,
                tokens_out=event.tokens_out,
                # An agent span is judged against whatever was retrieved before
                # it spoke -- that is what it had available to ground on.
                retrieval_context=list(trace.retrieval_context),
            )
            trace.spans.append(span)
            current_agent_span = span
            if event.text.strip():
                trace.output = event.text
            continue

        if event.event_type is EventType.ERROR:
            trace.error = event.error_message or event.error_code

    # A tool call with no response came back empty or the turn was cut short.
    for name, call in pending_calls.items():
        trace.trajectory.append(
            ToolCall(name=name, args=dict(call.tool_args), error="No tool response")
        )

    trace.output = unwrap_json_text(trace.output)
    trace.retrieval_context = _dedupe_docs(trace.retrieval_context)
    for span in trace.spans:
        if span.kind is SpanKind.AGENT:
            span.retrieval_context = _dedupe_docs(span.retrieval_context)
    return trace


def unwrap_json_text(output: str) -> str:
    """Unwrap answers the agent returned as a JSON envelope.

    The live formatter agent emits {"text": "..."} rather than bare text;
    scoring the envelope would penalise the agent for its own serialization.
    Applied here rather than in the invoker so trace harvesting gets it too.
    """
    stripped = (output or "").strip()
    if not stripped.startswith("{"):
        return output
    import json

    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return output
    if not isinstance(parsed, dict):
        return output
    for key in ("text", "answer", "response", "output", "content", "message"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return output


def _render(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    import json

    try:
        return json.dumps(value, default=str)[:4000]
    except (TypeError, ValueError):
        return str(value)[:4000]


def _dedupe_docs(docs: list[RetrievalDoc]) -> list[RetrievalDoc]:
    """Drop repeats while keeping order.

    Agents commonly call the same retrieval tool twice; the same passage counted
    twice would inflate contextual-recall.
    """
    seen: set[str] = set()
    unique: list[RetrievalDoc] = []
    for doc in docs:
        key = doc.document_id or doc.text[:200]
        if key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    return unique


def traces_from_session(
    raw_events: Iterable[dict[str, Any]],
    *,
    session_id: str = "",
    tool_overrides: dict[str, str] | None = None,
) -> list[Trace]:
    """All turns in a session, oldest first."""
    events = normalize_events(raw_events, session_id=session_id)
    grouped = group_by_invocation(events)
    traces = [
        build_trace(
            bucket,
            invocation_id=invocation_id,
            session_id=session_id,
            tool_overrides=tool_overrides,
        )
        for invocation_id, bucket in grouped.items()
    ]
    traces.sort(key=lambda t: (t.events[0].timestamp or "") if t.events else "")
    return traces
