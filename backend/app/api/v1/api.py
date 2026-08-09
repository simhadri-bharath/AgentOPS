"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.routes import (
    agents,
    datasets,
    deployments,
    discovery,
    evaluations,
    redteam,
    traces,
)

api_router = APIRouter()
api_router.include_router(agents.router)
api_router.include_router(deployments.router)
api_router.include_router(discovery.router)
api_router.include_router(datasets.router)
api_router.include_router(evaluations.router)
api_router.include_router(redteam.router)
api_router.include_router(traces.router)
