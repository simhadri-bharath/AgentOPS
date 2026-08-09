"""Canonical, framework-agnostic trace types.

This is the boundary. Everything upstream speaks Google's event schema;
everything downstream (metric executors, dataset builders, the API) speaks only
these types. If a metric executor ever imports a Google type, the boundary has
leaked and the next provider will require rewriting the evaluators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from app.services.evaluation.tool_kinds import RetrievalDoc, ToolKind


class EventType(str, Enum):
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATE_UPDATE = "state_update"
    ERROR = "error"


class SpanKind(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"


class InvocationState(str, Enum):
    """Terminal states for one invocation.

    Deliberately not collapsed into a single `failed`: an agent that errored and
    a judge that errored mean completely different things to whoever is reading
    the result.
    """

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    AGENT_ERROR = "AGENT_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    HARVEST_ERROR = "HARVEST_ERROR"
    JUDGE_ERROR = "JUDGE_ERROR"


TERMINAL_FAILURE_STATES = {
    InvocationState.TIMEOUT,
    InvocationState.AGENT_ERROR,
    InvocationState.AUTH_ERROR,
    InvocationState.RATE_LIMITED,
    InvocationState.HARVEST_ERROR,
}


@dataclass
class AgentEvent:
    """One normalized event. Nested agents, parallel tool calls, retries, tool
    errors and text-free state updates all land here without special-casing."""

    event_id: str
    invocation_id: str
    session_id: str
    seq: int
    timestamp: str | None = None
    author: str = ""
    event_type: EventType = EventType.AGENT_MESSAGE
    role: str = "assistant"
    text: str = ""
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    state_delta: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    raw_event: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value
        if not include_raw:
            data.pop("raw_event", None)
        return data


@dataclass
class Span:
    span_id: str
    kind: SpanKind
    author: str
    invocation_id: str
    seq: int
    parent_span_id: str | None = None
    input: str = ""
    output: str = ""
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    tool_kind: ToolKind = ToolKind.UNKNOWN
    latency_ms: int | None = None
    error: str | None = None
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    retrieval_context: list[RetrievalDoc] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["tool_kind"] = self.tool_kind.value
        data["retrieval_context"] = [asdict(d) for d in self.retrieval_context]
        return data


@dataclass
class ToolCall:
    """One entry of a trajectory."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def signature(self) -> tuple[str, str]:
        """Name plus a stable rendering of args, for duplicate detection."""
        import json

        try:
            rendered = json.dumps(self.args, sort_keys=True, default=str)
        except (TypeError, ValueError):
            rendered = str(self.args)
        return self.name, rendered


@dataclass
class Trace:
    """One invocation: the user turn, everything the agent did, and the answer."""

    invocation_id: str
    session_id: str
    input: str = ""
    output: str = ""
    events: list[AgentEvent] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    agent_path: list[str] = field(default_factory=list)
    trajectory: list[ToolCall] = field(default_factory=list)
    retrieval_context: list[RetrievalDoc] = field(default_factory=list)
    latency_ms: int | None = None
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None

    def to_dict(self, *, include_events: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "invocation_id": self.invocation_id,
            "session_id": self.session_id,
            "input": self.input,
            "output": self.output,
            "agent_path": list(self.agent_path),
            "trajectory": [t.to_dict() for t in self.trajectory],
            "retrieval_context": [asdict(d) for d in self.retrieval_context],
            "spans": [s.to_dict() for s in self.spans],
            "latency_ms": self.latency_ms,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "error": self.error,
        }
        if include_events:
            data["events"] = [e.to_dict() for e in self.events]
        return data


@dataclass
class EvaluationCase:
    """The only thing metric executors are allowed to see."""

    input: str = ""
    actual_output: str = ""
    expected_output: str | None = None
    retrieval_context: list[str] = field(default_factory=list)
    predicted_trajectory: list[ToolCall] = field(default_factory=list)
    reference_trajectory: list[ToolCall] = field(default_factory=list)
    conversation: list[dict[str, str]] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    trace: Trace | None = None
    sample_index: int = 0
    state: InvocationState = InvocationState.SUCCESS
    error: str | None = None
    latency_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tools_called(self) -> list[str]:
        return [t.name for t in self.predicted_trajectory]

    def available_fields(self) -> set[str]:
        """Which inputs this case can actually supply.

        Drives metric availability: a metric asking for retrieval_context on a
        case that has none is reported unavailable with a reason, not silently
        scored against nothing.
        """
        present: set[str] = set()
        if self.input.strip():
            present.add("input")
        if self.actual_output.strip():
            present.add("actual_output")
        if (self.expected_output or "").strip():
            present.add("expected_output")
        if self.retrieval_context:
            present.add("retrieval_context")
        if self.predicted_trajectory:
            present.add("predicted_trajectory")
        if self.reference_trajectory:
            present.add("reference_trajectory")
        if self.conversation:
            present.add("conversation")
        if self.spans:
            present.add("spans")
        return present
