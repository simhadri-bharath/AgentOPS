"""Discovery sync routes — Vertex AI + Cloud Run."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_session
from app.schemas.agent import DiscoverySyncSummary, VertexAITestResponse
from app.services.discovery.vertex_ai import VertexAIDiscoveryService
from app.services.discovery.cloud_run import CloudRunDiscoveryService
from app.services.gcp.auth import validate_adc_credentials

router = APIRouter(prefix="/discovery", tags=["discovery"])


# ── Vertex AI endpoints (unchanged) ──────────────────────────────────────────

@router.post("/vertex-ai/sync", response_model=DiscoverySyncSummary)
async def sync_vertex_ai_agents(
    session: AsyncSession = Depends(get_session),
) -> DiscoverySyncSummary:
    auth = validate_adc_credentials()
    if not auth.available:
        raise HTTPException(
            status_code=503,
            detail=auth.error or "GCP credentials unavailable",
        )

    service = VertexAIDiscoveryService(session)
    try:
        return await service.sync_to_database()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Vertex AI discovery failed: {exc}",
        ) from exc


@router.get("/vertex-ai/test", response_model=VertexAITestResponse)
async def test_vertex_ai_connection(
    session: AsyncSession = Depends(get_session),
) -> VertexAITestResponse:
    auth = validate_adc_credentials()
    if not auth.available:
        return VertexAITestResponse(
            authenticated=False,
            message=auth.error or "GCP credentials unavailable",
        )

    service = VertexAIDiscoveryService(session)
    try:
        result = await service.test_connection()
        return VertexAITestResponse(**result)
    except Exception as exc:
        return VertexAITestResponse(
            authenticated=False,
            project_id=auth.project_id,
            message=str(exc),
        )


# ── Cloud Run endpoints ──────────────────────────────────────────────────────

@router.post("/cloud-run/sync", response_model=DiscoverySyncSummary)
async def sync_cloud_run_agents(
    session: AsyncSession = Depends(get_session),
) -> DiscoverySyncSummary:
    auth = validate_adc_credentials()
    if not auth.available:
        raise HTTPException(
            status_code=503,
            detail=auth.error or "GCP credentials unavailable",
        )

    service = CloudRunDiscoveryService(session)
    try:
        return await service.sync_to_database()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Cloud Run discovery failed: {exc}",
        ) from exc


@router.get("/cloud-run/test")
async def test_cloud_run_connection(
    session: AsyncSession = Depends(get_session),
) -> dict:
    auth = validate_adc_credentials()
    if not auth.available:
        return {
            "authenticated": False,
            "message": auth.error or "GCP credentials unavailable",
        }

    service = CloudRunDiscoveryService(session)
    try:
        return await service.test_connection()
    except Exception as exc:
        return {
            "authenticated": False,
            "project_id": auth.project_id,
            "message": str(exc),
        }


# ── Combined sync-all endpoint ───────────────────────────────────────────────

@router.post("/sync-all", response_model=DiscoverySyncSummary)
async def sync_all_agents(
    session: AsyncSession = Depends(get_session),
) -> DiscoverySyncSummary:
    """Sync agents from both Vertex AI and Cloud Run in parallel."""
    auth = validate_adc_credentials()
    if not auth.available:
        raise HTTPException(
            status_code=503,
            detail=auth.error or "GCP credentials unavailable",
        )

    vertex_service = VertexAIDiscoveryService(session)
    cloud_run_service = CloudRunDiscoveryService(session)

    # Run both syncs — gather with return_exceptions so one failure
    # doesn't block the other
    results = await asyncio.gather(
        vertex_service.sync_to_database(),
        cloud_run_service.sync_to_database(),
        return_exceptions=True,
    )

    # Merge summaries
    combined = DiscoverySyncSummary(
        discovered=0, created=0, updated=0, unchanged=0
    )

    for result in results:
        if isinstance(result, Exception):
            combined.errors.append(str(result))
        else:
            combined.discovered += result.discovered
            combined.created += result.created
            combined.updated += result.updated
            combined.unchanged += result.unchanged
            combined.errors.extend(result.errors)
            combined.agents.extend(result.agents)

    return combined
