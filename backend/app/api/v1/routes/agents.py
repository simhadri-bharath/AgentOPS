"""Agent CRUD routes."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_agent_repository, get_session
from app.repositories.agent_repository import AgentRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.schemas.agent import (
    AgentInvokeTestRequest,
    AgentInvokeTestResponse,
    AgentListResponse,
    AgentRead,
)
from app.schemas.evaluation import EvaluationRunListResponse, evaluation_run_from_orm
from app.services.evaluation.agent_invoker import AgentInvoker
from app.services.evaluation.reasoning_engine_direct import events_preview, stream_query_prompt

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=AgentListResponse)
async def list_agents(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    deployment_type: str | None = Query(default=None),
    repo: AgentRepository = Depends(get_agent_repository),
) -> AgentListResponse:
    agents, total = await repo.list_agents(
        limit=limit,
        offset=offset,
        deployment_type=deployment_type,
    )
    return AgentListResponse(
        items=[AgentRead.from_orm_agent(a) for a in agents],
        total=total,
    )


@router.get("/{agent_id}/evaluations", response_model=EvaluationRunListResponse)
async def list_agent_evaluations(
    agent_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> EvaluationRunListResponse:
    agent = await AgentRepository(session).get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    items, total = await EvaluationRepository(session).list_runs(
        agent_id=agent_id, limit=limit, offset=offset
    )
    return EvaluationRunListResponse(
        items=[evaluation_run_from_orm(r) for r in items],
        total=total,
    )


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: uuid.UUID,
    repo: AgentRepository = Depends(get_agent_repository),
) -> AgentRead:
    agent = await repo.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return AgentRead.from_orm_agent(agent)


@router.post("/{agent_id}/test-invoke", response_model=AgentInvokeTestResponse)
async def test_invoke_agent(
    agent_id: uuid.UUID,
    body: AgentInvokeTestRequest,
    repo: AgentRepository = Depends(get_agent_repository),
) -> AgentInvokeTestResponse:
    """
    Debug a single prompt against the agent's Reasoning Engine.
    Tries run_inference (1 row) then stream_query fallback.
    """
    agent = await repo.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    if not agent.endpoint_url:
        raise HTTPException(status_code=400, detail="Agent has no endpoint_url")

    row: dict[str, str] = {"input": body.prompt}
    if body.context:
        row["context"] = body.context

    invoker = AgentInvoker()

    def _run() -> AgentInvokeTestResponse:
        from app.core.config import get_settings
        from app.services.gcp.auth import require_adc

        invoker.initialize()
        settings = get_settings()
        auth = require_adc()
        project_id = settings.gcp_project_id or auth.project_id or ""
        region = settings.gcp_region

        results = invoker.batch_invoke(agent.endpoint_url, [row])
        r = results[0] if results else None
        if r and r.output.strip():
            return AgentInvokeTestResponse(
                output=r.output,
                latency_ms=r.latency_ms,
                via="run_inference",
            )

        prompt = row["input"]
        if row.get("context"):
            prompt = f"Context:\n{row['context']}\n\nUser:\n{prompt}"
        text, events, err = stream_query_prompt(
            project_id=project_id,
            region=region,
            resource_name=agent.endpoint_url,
            prompt=prompt,
        )
        return AgentInvokeTestResponse(
            output=text,
            latency_ms=r.latency_ms if r else 0,
            error=err or (r.error if r else None),
            via="stream_query",
            events_preview=events_preview(events),
        )

    return await asyncio.to_thread(_run)
