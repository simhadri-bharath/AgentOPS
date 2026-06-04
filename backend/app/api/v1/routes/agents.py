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


@router.get("/{agent_id}/metadata")
async def get_agent_metadata(
    agent_id: uuid.UUID,
    repo: AgentRepository = Depends(get_agent_repository),
):
    agent = await repo.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    def _fetch():
        import vertexai
        from vertexai import Client
        from app.core.config import get_settings
        from app.services.gcp.auth import require_adc

        settings = get_settings()
        auth = require_adc()
        project = settings.gcp_project_id or auth.project_id
        if not project or not agent.endpoint_url:
            return None

        try:
            vertexai.init(project=project, location=agent.region)
            client = Client(project=project, location=agent.region)
            engine = client.agent_engines.get(name=agent.endpoint_url)

            # Support both new SDK (api_resource) and old SDK (gca_resource)
            gca = getattr(engine, 'api_resource', None) or getattr(engine, 'gca_resource', None)
            if gca is None:
                return None

            description = getattr(gca, "description", "") or ""
            tools = []
            spec = getattr(gca, "spec", None)
            if spec and hasattr(spec, "class_methods"):
                for m in spec.class_methods:
                    tools.append({
                        "name": getattr(m, "name", "") if hasattr(m, "name") else m.get("name", ""),
                        "description": getattr(m, "description", "") if hasattr(m, "description") else m.get("description", ""),
                    })
            return {
                "description": description,
                "tools": tools,
                "target_purpose": description or f"A {agent.name.replace('-', ' ').title()} assistant.",
                "system_prompt": f"You are a {description.lower().rstrip('.') or 'helpful AI assistant'}. Focus on performing your tasks safely."
            }
        except Exception:
            return None

    sdk_data = await asyncio.to_thread(_fetch) if agent.deployment_type == "vertex_ai" else None

    description = (sdk_data and sdk_data.get("description")) or agent.extra_metadata.get("description") or f"Reasoning engine agent: {agent.name}"
    target_purpose = (sdk_data and sdk_data.get("target_purpose")) or agent.extra_metadata.get("target_purpose") or description
    system_prompt = (sdk_data and sdk_data.get("system_prompt")) or agent.extra_metadata.get("system_prompt") or "You are a helpful AI assistant."
    tools = (sdk_data and sdk_data.get("tools")) or agent.extra_metadata.get("tools") or []

    return {
        "id": agent.id,
        "name": agent.name,
        "display_name": agent.display_name or agent.name,
        "description": description,
        "target_purpose": target_purpose,
        "system_prompt": system_prompt,
        "model_info": agent.model_name or "gemini-2.5-pro",
        "deployment_metadata": {
            "deployment_type": agent.deployment_type,
            "region": agent.region,
            "gcp_project": agent.gcp_project,
            "endpoint_url": agent.endpoint_url,
        },
        "tool_metadata": tools
    }


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
