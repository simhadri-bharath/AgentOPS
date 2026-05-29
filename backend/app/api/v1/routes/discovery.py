"""Discovery sync routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_session
from app.schemas.agent import DiscoverySyncSummary, VertexAITestResponse
from app.services.discovery.vertex_ai import VertexAIDiscoveryService
from app.services.gcp.auth import validate_adc_credentials

router = APIRouter(prefix="/discovery", tags=["discovery"])


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
