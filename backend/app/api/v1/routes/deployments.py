"""Deployment inventory and onboarding routes."""

from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.config import get_settings
from app.dependencies import get_agent_repository
from app.repositories.agent_repository import AgentRepository
from app.schemas.agent import (
    AgentCreate,
    AgentInvokeTestRequest,
    AgentInvokeTestResponse,
    AgentRead,
)
from app.schemas.deployment import (
    DeploymentDetail,
    DeploymentListResponse,
    DeploymentOnboardRequest,
    DeploymentRead,
)
from app.services.discovery.deployments import (
    Deployment,
    clear_cache,
    list_deployments,
    resolve_regions,
)
from app.services.discovery.vertex_ai import agent_uuid_for_resource, slugify
from app.services.evaluation.trace_health import compute_trace_health
from app.services.gcp.agent_engine_client import (
    INVOCATION_CLASS_METHOD,
    INVOCATION_ENDPOINT,
    AgentEngineClient,
    AgentEngineError,
)
from app.services.invokers.agent_engine import AgentEngineInvoker

router = APIRouter(prefix="/deployments", tags=["deployments"])


async def _with_onboarding_state(
    deployments: list[Deployment], repo: AgentRepository
) -> list[Deployment]:
    for deployment in deployments:
        existing = await repo.get_agent_by_endpoint(deployment.resource_name)
        deployment.onboarded_agent_id = str(existing.id) if existing else None
    return deployments


@router.get("", response_model=DeploymentListResponse)
async def get_deployments(
    refresh: bool = Query(default=False, description="Bypass the 60s inventory cache"),
    inspect_sessions: bool = Query(
        default=True, description="Read the newest session to infer tools and type"
    ),
    repo: AgentRepository = Depends(get_agent_repository),
) -> DeploymentListResponse:
    settings = get_settings()
    try:
        deployments = await list_deployments(
            inspect_sessions=inspect_sessions, use_cache=not refresh
        )
    except AgentEngineError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    await _with_onboarding_state(deployments, repo)
    return DeploymentListResponse(
        items=[DeploymentRead(**d.to_dict()) for d in deployments],
        total=len(deployments),
        project=settings.gcp_project_id or None,
        regions=resolve_regions(settings),
    )


@router.get("/{engine_id}", response_model=DeploymentDetail)
async def get_deployment(
    engine_id: str,
    region: str | None = Query(default=None),
    repo: AgentRepository = Depends(get_agent_repository),
) -> DeploymentDetail:
    deployments = await list_deployments()
    match = next(
        (d for d in deployments if d.engine_id == engine_id and (not region or d.region == region)),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail=f"Deployment {engine_id} not found")

    await _with_onboarding_state([match], repo)

    try:
        async with AgentEngineClient() as client:
            engine = await client.get_engine(match.region, engine_id)
            sessions = await client.list_sessions(match.resource_name, page_size=10)
    except AgentEngineError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return DeploymentDetail(
        **match.to_dict(),
        spec=engine.get("spec") or {},
        recent_sessions=[
            {
                "id": s.get("name", "").split("/")[-1],
                "user_id": s.get("userId"),
                "create_time": s.get("createTime"),
                "update_time": s.get("updateTime"),
            }
            for s in sessions
        ],
    )


@router.post("/{engine_id}/test-invoke", response_model=AgentInvokeTestResponse)
async def test_invoke_deployment(
    engine_id: str,
    body: AgentInvokeTestRequest,
    region: str | None = Query(default=None),
) -> AgentInvokeTestResponse:
    """Invoke a deployment before onboarding it.

    Onboarding used to be a prerequisite for testing, which is backwards: the
    point of a test is to decide whether to onboard. Nothing is written here.
    """
    deployments = await list_deployments()
    match = next(
        (
            d
            for d in deployments
            if d.engine_id == engine_id and (not region or d.region == region)
        ),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail=f"Deployment {engine_id} not found")

    invoker = AgentEngineInvoker()
    try:
        outcome = await invoker.invoke(match.resource_name, body.prompt, context=body.context)
    except AgentEngineError as exc:
        return AgentInvokeTestResponse(
            output="",
            latency_ms=0,
            error=str(exc),
            via=f"{INVOCATION_ENDPOINT}/{INVOCATION_CLASS_METHOD}",
            state=exc.kind,
        )

    trace = outcome.trace
    return AgentInvokeTestResponse(
        output=outcome.output,
        latency_ms=outcome.latency_ms,
        error=outcome.error,
        via=f"{INVOCATION_ENDPOINT}/{INVOCATION_CLASS_METHOD}",
        state=outcome.state.value,
        agent_path=list(trace.agent_path) if trace else [],
        trajectory=[t.to_dict() for t in trace.trajectory] if trace else [],
        retrieval_context=[asdict(d) for d in trace.retrieval_context] if trace else [],
        spans=[s.to_dict() for s in trace.spans] if trace else [],
        trace_health=compute_trace_health(trace) if trace else {},
        tokens_in=trace.tokens_in if trace else 0,
        tokens_out=trace.tokens_out if trace else 0,
    )


@router.post("/onboard", response_model=AgentRead, status_code=201)
async def onboard_deployment(
    body: DeploymentOnboardRequest,
    repo: AgentRepository = Depends(get_agent_repository),
) -> AgentRead:
    deployments = await list_deployments()
    match = next(
        (
            d
            for d in deployments
            if d.engine_id == body.engine_id and (not body.region or d.region == body.region)
        ),
        None,
    )
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Deployment {body.engine_id} not found in this project",
        )

    display_name = body.display_name or match.display_name
    settings = get_settings()

    agent_data = AgentCreate(
        id=agent_uuid_for_resource(match.resource_name),
        name=slugify(display_name),
        display_name=display_name,
        deployment_type="vertex_ai",
        endpoint_url=match.resource_name,
        model_name=None,
        region=match.region,
        gcp_project=settings.gcp_project_id or None,
        status="healthy",
        source="deployment_onboard",
        agent_type=body.agent_type or match.agent_type_guess,
        capabilities=body.capabilities
        if body.capabilities is not None
        else match.capabilities_guess,
        purpose=body.purpose or match.purpose_guess,
        environment=body.environment,
        invocation_config={"user_id": "agentops-eval"},
        metadata={
            "gcp_engine_id": match.engine_id,
            "resource_name": match.resource_name,
            "agent_framework": match.framework,
            "class_methods": match.class_methods,
            "observed_tools": match.observed_tools,
            "observed_authors": match.observed_authors,
        },
    )

    agent, _created = await repo.upsert_agent(agent_data)
    # Onboarding is an explicit user decision -- it overrides whatever discovery
    # or a previous onboarding left behind.
    agent = await repo.set_profile(
        agent,
        agent_type=agent_data.agent_type,
        capabilities=agent_data.capabilities,
        purpose=agent_data.purpose,
        environment=agent_data.environment,
        display_name=display_name,
    )

    clear_cache()
    return AgentRead.from_orm_agent(agent)


@router.delete("/onboard/{agent_id}", status_code=204, response_class=Response)
async def offboard_agent(
    agent_id: uuid.UUID,
    repo: AgentRepository = Depends(get_agent_repository),
) -> Response:
    if not await repo.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    clear_cache()
    return Response(status_code=204)
