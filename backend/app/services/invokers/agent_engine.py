"""Agent Engine invoker.

One invocation per sample, each in its own session, with the trajectory
harvested from sessions.events.list afterwards. Sessions are deleted once
harvested so evaluation and red-team traffic never pollutes the production
session list.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.evaluation.trace_model import InvocationState, Trace
from app.services.evaluation.trace_normalizer import (
    build_trace,
    normalize_events,
    unwrap_json_text,
)
from app.services.gcp.agent_engine_client import AgentEngineClient, AgentEngineError

logger = get_logger(__name__)

EVAL_USER_ID = "agentops-eval"
REDTEAM_USER_ID = "agentops-redteam"


@dataclass
class InvokeOutcome:
    """One sample's invocation: what came back and what actually happened."""

    output: str = ""
    latency_ms: int = 0
    state: InvocationState = InvocationState.SUCCESS
    error: str | None = None
    trace: Trace | None = None
    session_id: str | None = None
    raw_events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.state is InvocationState.SUCCESS


class AgentEngineInvoker:
    """Invoke a deployed Agent Engine and return a normalized trace.

    Cancellation and cleanup are part of the interface from the start so
    evaluation and red-team share one abstraction rather than growing two.
    """

    def __init__(
        self,
        *,
        user_id: str = EVAL_USER_ID,
        concurrency: int | None = None,
        keep_sessions: bool = False,
        tool_overrides: dict[str, str] | None = None,
    ) -> None:
        settings = get_settings()
        self._user_id = user_id
        self._keep_sessions = keep_sessions
        self._tool_overrides = tool_overrides or {}
        self._timeout_s = float(settings.evaluation_timeout_seconds)
        self._concurrency = concurrency or settings.invoke_concurrency
        self._cancelled = asyncio.Event()

    def cancel(self) -> None:
        """Stop dispatching new samples. In-flight requests finish or time out."""
        self._cancelled.set()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    async def invoke(
        self, resource_name: str, prompt: str, *, context: str | None = None
    ) -> InvokeOutcome:
        async with AgentEngineClient() as client:
            return await self._invoke_one(client, resource_name, prompt, context)

    async def batch_invoke(
        self,
        resource_name: str,
        rows: list[dict[str, str]],
        *,
        on_progress: Any = None,
    ) -> list[InvokeOutcome]:
        """Invoke every row concurrently, preserving input order.

        A retrieval turn against the live chat agent takes ~38s, so a serial run
        over 50 samples would exceed half an hour.
        """
        if not rows:
            return []

        semaphore = asyncio.Semaphore(self._concurrency)
        results: list[InvokeOutcome | None] = [None] * len(rows)

        async with AgentEngineClient() as client:

            async def run(index: int, row: dict[str, str]) -> None:
                if self.cancelled:
                    results[index] = InvokeOutcome(
                        state=InvocationState.CANCELLED, error="Cancelled before dispatch"
                    )
                    return
                async with semaphore:
                    if self.cancelled:
                        results[index] = InvokeOutcome(
                            state=InvocationState.CANCELLED, error="Cancelled"
                        )
                        return
                    results[index] = await self._invoke_one(
                        client,
                        resource_name,
                        row.get("input", ""),
                        row.get("context"),
                        sample_index=index,
                    )
                if on_progress:
                    await _maybe_await(on_progress, index, results[index])

            await asyncio.gather(*(run(i, row) for i, row in enumerate(rows)))

        return [r or InvokeOutcome(state=InvocationState.AGENT_ERROR, error="No result") for r in results]

    async def harvest_trace(
        self, resource_name: str, session_id: str, *, invocation_id: str = ""
    ) -> Trace:
        async with AgentEngineClient() as client:
            raw = await client.list_events(resource_name, session_id)
        events = normalize_events(raw, session_id=session_id)
        return build_trace(
            events,
            invocation_id=invocation_id,
            session_id=session_id,
            tool_overrides=self._tool_overrides,
        )

    async def cleanup(self, resource_name: str, session_id: str) -> None:
        async with AgentEngineClient() as client:
            await client.delete_session(resource_name, session_id)

    # -- internals ------------------------------------------------------

    async def _invoke_one(
        self,
        client: AgentEngineClient,
        resource_name: str,
        prompt: str,
        context: str | None = None,
        *,
        sample_index: int = 0,
    ) -> InvokeOutcome:
        message = prompt
        if context:
            message = f"Context:\n{context}\n\nUser:\n{prompt}"

        session_id: str | None = None
        start = time.perf_counter()
        try:
            session_id = await client.create_session(resource_name, self._user_id)
        except AgentEngineError as exc:
            return InvokeOutcome(
                latency_ms=_elapsed_ms(start),
                state=InvocationState(exc.kind),
                error=f"create_session: {exc}",
            )

        try:
            chunks = await asyncio.wait_for(
                client.stream_query(
                    resource_name,
                    user_id=self._user_id,
                    session_id=session_id,
                    message=message,
                ),
                timeout=self._timeout_s,
            )
        except asyncio.TimeoutError:
            latency = _elapsed_ms(start)
            await self._maybe_cleanup(client, resource_name, session_id)
            return InvokeOutcome(
                latency_ms=latency,
                state=InvocationState.TIMEOUT,
                error=f"Invocation exceeded {self._timeout_s:.0f}s",
                session_id=session_id,
            )
        except AgentEngineError as exc:
            latency = _elapsed_ms(start)
            await self._maybe_cleanup(client, resource_name, session_id)
            return InvokeOutcome(
                latency_ms=latency,
                state=InvocationState(exc.kind),
                error=str(exc),
                session_id=session_id,
            )

        # Per-request timing. The previous implementation divided one batch
        # duration by the row count, so every sample reported the same number.
        latency_ms = _elapsed_ms(start)

        try:
            raw_events = await client.list_events(resource_name, session_id)
        except AgentEngineError as exc:
            await self._maybe_cleanup(client, resource_name, session_id)
            return InvokeOutcome(
                output=_text_from_chunks(chunks),
                latency_ms=latency_ms,
                state=InvocationState.HARVEST_ERROR,
                error=f"events.list: {exc}",
                session_id=session_id,
            )

        invocation_id = _invocation_id(chunks, raw_events)
        events = normalize_events(raw_events, session_id=session_id)
        trace = build_trace(
            events,
            invocation_id=invocation_id,
            session_id=session_id,
            tool_overrides=self._tool_overrides,
        )
        trace.latency_ms = latency_ms
        if not trace.input:
            trace.input = prompt
        if not trace.output:
            # The streamed chunks are the fallback: the events API is the
            # authority, but a harvest race should not lose the answer.
            # Unwrapped here too: build_trace only sees the events, and this
            # fallback text bypasses it.
            trace.output = unwrap_json_text(_text_from_chunks(chunks))

        # sessions.events.list does not return usageMetadata -- only the stream
        # carries it, so token counts come from the chunks.
        if not trace.tokens_in and not trace.tokens_out:
            trace.tokens_in, trace.tokens_out = _usage_from_chunks(chunks)

        await self._maybe_cleanup(client, resource_name, session_id)

        state = InvocationState.SUCCESS
        error = None
        if not trace.output.strip():
            state = InvocationState.AGENT_ERROR
            error = trace.error or "Empty agent response"

        return InvokeOutcome(
            output=trace.output,
            latency_ms=latency_ms,
            state=state,
            error=error,
            trace=trace,
            session_id=session_id,
            raw_events=raw_events,
        )

    async def _maybe_cleanup(
        self, client: AgentEngineClient, resource_name: str, session_id: str
    ) -> None:
        if self._keep_sessions:
            return
        await client.delete_session(resource_name, session_id)


def _elapsed_ms(start: float) -> int:
    return max(int((time.perf_counter() - start) * 1000), 1)


def _text_from_chunks(chunks: list[dict[str, Any]]) -> str:
    """Answer text is in the LAST chunk carrying text, not the first."""
    for chunk in reversed(chunks):
        for part in (chunk.get("content") or {}).get("parts") or []:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text
    return ""


def _usage_from_chunks(chunks: list[dict[str, Any]]) -> tuple[int, int]:
    tokens_in = 0
    tokens_out = 0
    for chunk in chunks:
        usage = chunk.get("usage_metadata") or chunk.get("usageMetadata") or {}
        if not isinstance(usage, dict):
            continue
        tokens_in += int(
            usage.get("prompt_token_count") or usage.get("promptTokenCount") or 0
        )
        tokens_out += int(
            usage.get("candidates_token_count") or usage.get("candidatesTokenCount") or 0
        )
    return tokens_in, tokens_out


def _invocation_id(chunks: list[dict[str, Any]], raw_events: list[dict[str, Any]]) -> str:
    for chunk in chunks:
        value = chunk.get("invocation_id") or chunk.get("invocationId")
        if value:
            return str(value)
    for event in reversed(raw_events):
        value = event.get("invocationId") or event.get("invocation_id")
        if value:
            return str(value)
    return f"local-{uuid.uuid4().hex[:12]}"


async def _maybe_await(callback: Any, *args: Any) -> None:
    result = callback(*args)
    if asyncio.iscoroutine(result):
        await result
