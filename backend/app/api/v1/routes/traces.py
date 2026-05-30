"""Trace routes — proxy Cloud Trace API data to the frontend."""

from fastapi import APIRouter, HTTPException, Query

from app.core.logging import get_logger
from app.schemas.traces import TraceDetailResponse, TraceListResponse
from app.services.gcp.traces import CloudTraceService

logger = get_logger(__name__)

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", response_model=TraceListResponse)
async def list_traces(
    hours: int = Query(default=24, ge=1, le=168, description="Look-back window in hours"),
    limit: int = Query(default=50, ge=1, le=100, description="Max traces to return"),
    agent: str | None = Query(default=None, description="Filter by agent name"),
) -> TraceListResponse:
    """List recent traces from Google Cloud Trace."""
    try:
        service = CloudTraceService()
        traces, total = await service.list_traces(
            hours=hours,
            page_size=limit,
            agent_filter=agent,
        )
        return TraceListResponse(
            items=traces,
            total=total,
            has_more=total >= limit,
        )
    except Exception as exc:
        logger.exception("Failed to list traces", extra={"component": "traces_api"})
        raise HTTPException(status_code=502, detail=f"Cloud Trace API error: {exc}")


@router.get("/{trace_id}", response_model=TraceDetailResponse)
async def get_trace(trace_id: str) -> TraceDetailResponse:
    """Get full trace details with all spans."""
    try:
        service = CloudTraceService()
        trace = await service.get_trace(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

        span_tree = CloudTraceService.build_span_tree(trace.spans)
        return TraceDetailResponse(trace=trace, span_tree=span_tree)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to get trace %s",
            trace_id,
            extra={"component": "traces_api"},
        )
        raise HTTPException(status_code=502, detail=f"Cloud Trace API error: {exc}")
