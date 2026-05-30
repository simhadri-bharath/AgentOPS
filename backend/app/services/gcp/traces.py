"""Cloud Trace service — reads traces and spans from GCP Cloud Trace API."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.traces import SpanNode, SpanRead, TraceRead

logger = get_logger(__name__)

# Span kind mapping from Cloud Trace API protobuf enum
_SPAN_KINDS = {
    0: "INTERNAL",
    1: "SERVER",
    2: "CLIENT",
    3: "PRODUCER",
    4: "CONSUMER",
}


class CloudTraceService:
    """Reads traces from Google Cloud Trace API (v1)."""

    def __init__(self, project_id: str | None = None) -> None:
        settings = get_settings()
        self._project_id = project_id or settings.gcp_project_id
        if not self._project_id:
            raise RuntimeError(
                "GCP project ID is required. Set GCP_PROJECT_ID in .env."
            )

    def _get_client(self) -> Any:
        """Lazy import to avoid blocking startup."""
        from google.cloud import trace_v1

        return trace_v1.TraceServiceClient()

    async def list_traces(
        self,
        *,
        hours: int = 24,
        page_size: int = 50,
        status_filter: str | None = None,
        agent_filter: str | None = None,
    ) -> tuple[list[TraceRead], int]:
        """List recent traces from Cloud Trace API."""
        return await asyncio.to_thread(
            self._list_traces_sync,
            hours=hours,
            page_size=page_size,
            status_filter=status_filter,
            agent_filter=agent_filter,
        )

    def _list_traces_sync(
        self,
        *,
        hours: int = 24,
        page_size: int = 50,
        status_filter: str | None = None,
        agent_filter: str | None = None,
    ) -> tuple[list[TraceRead], int]:
        from google.cloud import trace_v1
        from google.protobuf import timestamp_pb2

        client = self._get_client()

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)

        start_time = timestamp_pb2.Timestamp()
        start_time.FromDatetime(start)
        end_time = timestamp_pb2.Timestamp()
        end_time.FromDatetime(now)

        # Build filter string for Cloud Trace
        filter_str = ""
        if agent_filter:
            filter_str = f'gen_ai.agent.name:"{agent_filter}"'

        request = trace_v1.ListTracesRequest(
            project_id=self._project_id,
            start_time=start_time,
            end_time=end_time,
            view=trace_v1.ListTracesRequest.ViewType.COMPLETE,
            page_size=min(page_size, 100),
            filter=filter_str or "",
        )

        traces_list: list[TraceRead] = []

        try:
            pager = client.list_traces(request=request)
            # Use .pages to iterate page-by-page, avoiding the auto-pager's
            # tendency to fetch the next page even after we have enough results
            # (which causes "Invalid page token" 400 errors).
            done = False
            for page in pager.pages:
                for trace in page.traces:
                    parsed = self._parse_trace(trace, include_spans=False)
                    if parsed:
                        traces_list.append(parsed)
                    if len(traces_list) >= page_size:
                        done = True
                        break
                if done:
                    break
        except Exception as exc:
            # If we already have some results, log the error but return them
            if traces_list:
                logger.warning(
                    "Partial trace listing (%d collected) — pagination error: %s",
                    len(traces_list),
                    exc,
                    extra={"component": "cloud_trace"},
                )
            else:
                logger.error(
                    "Failed to list traces: %s",
                    exc,
                    extra={"component": "cloud_trace"},
                )
                raise

        # Sort by start time descending (most recent first)
        traces_list.sort(
            key=lambda t: t.start_time or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        logger.info(
            "Listed %d traces from Cloud Trace",
            len(traces_list),
            extra={"component": "cloud_trace"},
        )
        return traces_list, len(traces_list)

    async def get_trace(self, trace_id: str) -> TraceRead | None:
        """Get a single trace with all spans."""
        return await asyncio.to_thread(self._get_trace_sync, trace_id)

    def _get_trace_sync(self, trace_id: str) -> TraceRead | None:
        client = self._get_client()
        try:
            trace = client.get_trace(
                project_id=self._project_id,
                trace_id=trace_id,
            )
            return self._parse_trace(trace, include_spans=True)
        except Exception as exc:
            logger.error(
                "Failed to get trace %s: %s",
                trace_id,
                exc,
                extra={"component": "cloud_trace"},
            )
            return None

    def _parse_trace(self, trace: Any, *, include_spans: bool = True) -> TraceRead | None:
        """Parse a Cloud Trace API Trace object into our schema."""
        if not trace.spans:
            return None

        spans: list[SpanRead] = []
        earliest_start: datetime | None = None
        latest_end: datetime | None = None
        root_span_name: str | None = None
        agent_name: str | None = None
        session_id: str | None = None
        has_error = False

        for span in trace.spans:
            parsed_span = self._parse_span(span)
            if parsed_span:
                spans.append(parsed_span)

                # Track time bounds
                if earliest_start is None or parsed_span.start_time < earliest_start:
                    earliest_start = parsed_span.start_time
                if latest_end is None or parsed_span.end_time > latest_end:
                    latest_end = parsed_span.end_time

                # Find root span (no parent) for metadata
                if not span.parent_span_id:
                    root_span_name = parsed_span.name
                    agent_name = parsed_span.agent_name
                    session_id = parsed_span.session_id

                if parsed_span.status == "ERROR":
                    has_error = True

        # If no root span found, use first span's agent_name
        if not agent_name and spans:
            for s in spans:
                if s.agent_name:
                    agent_name = s.agent_name
                    break

        if not session_id and spans:
            for s in spans:
                if s.session_id:
                    session_id = s.session_id
                    break

        duration_ms = 0.0
        if earliest_start and latest_end:
            duration_ms = (latest_end - earliest_start).total_seconds() * 1000

        return TraceRead(
            trace_id=trace.trace_id,
            project_id=trace.project_id,
            start_time=earliest_start,
            end_time=latest_end,
            duration_ms=round(duration_ms, 1),
            span_count=len(spans),
            status="ERROR" if has_error else "OK",
            root_span_name=root_span_name,
            agent_name=agent_name,
            session_id=session_id,
            spans=spans if include_spans else [],
        )

    def _parse_span(self, span: Any) -> SpanRead | None:
        """Parse a Cloud Trace API TraceSpan into our schema."""
        try:
            labels = dict(span.labels) if span.labels else {}

            start_time = span.start_time
            end_time = span.end_time

            # Ensure timezone-aware
            if start_time and start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time and end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            duration_ms = 0.0
            if start_time and end_time:
                duration_ms = (end_time - start_time).total_seconds() * 1000

            # Extract convenience fields from labels
            agent_name = labels.get("gen_ai.agent.name")
            operation = labels.get("gen_ai.operation.name", span.name)
            model_name = labels.get("gen_ai.request.model")
            session_id = labels.get("gen_ai.conversation.id") or labels.get(
                "gcp.vertex.agent.session_id"
            )

            input_tokens = None
            output_tokens = None
            try:
                if "gen_ai.usage.input_tokens" in labels:
                    input_tokens = int(labels["gen_ai.usage.input_tokens"])
                if "gen_ai.usage.output_tokens" in labels:
                    output_tokens = int(labels["gen_ai.usage.output_tokens"])
            except (ValueError, TypeError):
                pass

            # Determine status from labels
            status = "OK"
            finish_reasons = labels.get("gen_ai.response.finish_reasons", "")
            if "error" in finish_reasons.lower():
                status = "ERROR"

            return SpanRead(
                span_id=str(span.span_id),
                parent_span_id=str(span.parent_span_id) if span.parent_span_id else None,
                name=span.name or "unknown",
                kind=_SPAN_KINDS.get(span.kind, "INTERNAL"),
                start_time=start_time,
                end_time=end_time,
                duration_ms=round(duration_ms, 1),
                status=status,
                labels=labels,
                agent_name=agent_name,
                operation=operation,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                session_id=session_id,
                conversation_id=labels.get("gen_ai.conversation.id"),
            )
        except Exception as exc:
            logger.warning(
                "Failed to parse span: %s",
                exc,
                extra={"component": "cloud_trace"},
            )
            return None

    @staticmethod
    def build_span_tree(spans: list[SpanRead]) -> list[SpanNode]:
        """Build a tree structure from flat span list using parent_span_id."""
        nodes: dict[str, SpanNode] = {}
        roots: list[SpanNode] = []

        # Create nodes
        for span in spans:
            nodes[span.span_id] = SpanNode(span=span, children=[], depth=0)

        # Link children
        for span in spans:
            node = nodes[span.span_id]
            if span.parent_span_id and span.parent_span_id in nodes:
                parent = nodes[span.parent_span_id]
                parent.children.append(node)
            else:
                roots.append(node)

        # Set depths
        def _set_depth(node: SpanNode, depth: int) -> None:
            node.depth = depth
            for child in node.children:
                _set_depth(child, depth + 1)

        for root in roots:
            _set_depth(root, 0)

        # Sort children by start_time
        def _sort_children(node: SpanNode) -> None:
            node.children.sort(key=lambda n: n.span.start_time)
            for child in node.children:
                _sort_children(child)

        for root in roots:
            _sort_children(root)

        roots.sort(key=lambda n: n.span.start_time)
        return roots
