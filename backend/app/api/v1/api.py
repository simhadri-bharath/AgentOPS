"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.routes import agents, datasets, discovery, evaluations

api_router = APIRouter()
api_router.include_router(agents.router)
api_router.include_router(discovery.router)
api_router.include_router(datasets.router)
api_router.include_router(evaluations.router)
