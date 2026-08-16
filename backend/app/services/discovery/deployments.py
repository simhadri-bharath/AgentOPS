"""Live inventory of deployed Agent Engines.

Read-only: nothing is written to the `agents` table until the user explicitly
onboards a deployment. That is what keeps the agent list a curated set rather
than whatever happened to be deployed in the project.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.evaluation.tool_kinds import infer_agent_type, infer_capabilities
from app.services.gcp.agent_engine_client import AgentEngineClient, AgentEngineError

logger = get_logger(__name__)

# Regions Agent Engine is available in. Matches the fan-out already used by
# VertexAIDiscoveryService.
DEFAULT_REGIONS = [
    "us-central1",
    "us-west1",
    "us-east1",
    "us-east4",
    "europe-west1",
    "europe-west3",
    "europe-west9",
    "asia-east1",
    "asia-northeast1",
    "asia-southeast1",
]

# ADK lifecycle plumbing, not agent capabilities.
ADK_FRAMEWORK_METHODS = {
    "get_session", "list_sessions", "create_session", "delete_session",
    "async_get_session", "async_list_sessions", "async_create_session",
    "async_delete_session", "async_add_session_to_memory", "async_search_memory",
    "stream_query", "async_stream_query", "streaming_agent_run_with_events",
    "run", "predict", "query", "stream",
}

_CACHE_TTL_S = 60.0
_cache: dict[str, tuple[float, list["Deployment"]]] = {}


@dataclass
class Deployment:
    engine_id: str
    resource_name: str
    display_name: str
    region: str
    framework: str | None = None
    description: str | None = None
    class_methods: list[str] = field(default_factory=list)
    custom_methods: list[str] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    session_count: int = 0
    # The count comes from one capped page, so "50" means "at least 50".
    session_count_capped: bool = False
    sessions_inspected: int = 0
    last_activity_at: str | None = None
    observed_tools: list[str] = field(default_factory=list)
    observed_authors: list[str] = field(default_factory=list)
    agent_type_guess: str = "unknown"
    capabilities_guess: list[str] = field(default_factory=list)
    purpose_guess: str | None = None
    onboarded_agent_id: str | None = None
    probe_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_regions(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    raw = (settings.gcp_region or "").strip()
    if "," in raw:
        return [r.strip() for r in raw.split(",") if r.strip()]
    if raw and raw != "us-central1":
        return sorted({raw, "us-central1", "us-west1"})
    return list(DEFAULT_REGIONS)


async def list_deployments(
    *,
    project: str | None = None,
    regions: list[str] | None = None,
    inspect_sessions: bool = True,
    use_cache: bool = True,
) -> list[Deployment]:
    """Enumerate Agent Engines and annotate each with observed behaviour."""
    settings = get_settings()
    project = project or settings.gcp_project_id
    regions = regions or resolve_regions(settings)

    cache_key = f"{project}|{','.join(sorted(regions))}|{inspect_sessions}"
    if use_cache:
        cached = _cache.get(cache_key)
        if cached and (time.monotonic() - cached[0]) < _CACHE_TTL_S:
            return cached[1]

    async with AgentEngineClient(project) as client:
        results = await asyncio.gather(
            *(client.list_engines(region) for region in regions),
            return_exceptions=True,
        )

        deployments: list[Deployment] = []
        for region, result in zip(regions, results):
            if isinstance(result, BaseException):
                # A region that is not enabled for the project is normal, not an error.
                logger.debug(
                    "Region %s unavailable during inventory: %s",
                    region,
                    result,
                    extra={"component": "deployments"},
                )
                continue
            for engine in result:
                deployments.append(_parse_engine(engine, region))

        if inspect_sessions and deployments:
            await asyncio.gather(
                *(_annotate_from_sessions(client, d) for d in deployments),
                return_exceptions=True,
            )

    for deployment in deployments:
        if not inspect_sessions:
            # No sessions were read, so there is no evidence to infer from.
            # Guessing "conversational" from class methods alone would show a
            # confident wrong answer that the enrichment pass then silently
            # corrects.
            deployment.agent_type_guess = "unknown"
            deployment.capabilities_guess = []
            deployment.purpose_guess = _purpose_guess(deployment)
            continue
        deployment.agent_type_guess = infer_agent_type(
            deployment.observed_tools,
            deployment.observed_authors,
            class_methods=deployment.class_methods,
        )
        deployment.capabilities_guess = infer_capabilities(deployment.observed_tools)
        if len({a for a in deployment.observed_authors if a and a != "user"}) > 1:
            if "multi_agent" not in deployment.capabilities_guess:
                deployment.capabilities_guess.append("multi_agent")
        deployment.purpose_guess = _purpose_guess(deployment)

    deployments.sort(key=lambda d: (d.last_activity_at or "", d.display_name), reverse=True)
    _cache[cache_key] = (time.monotonic(), deployments)
    return deployments


def _parse_engine(engine: dict[str, Any], region: str) -> Deployment:
    resource_name = engine.get("name", "")
    spec = engine.get("spec") or {}
    methods = [m.get("name", "") for m in spec.get("classMethods") or []]
    return Deployment(
        engine_id=resource_name.split("/")[-1],
        resource_name=resource_name,
        display_name=engine.get("displayName") or resource_name.split("/")[-1],
        region=region,
        framework=spec.get("agentFramework"),
        description=engine.get("description"),
        class_methods=methods,
        custom_methods=[m for m in methods if m and m not in ADK_FRAMEWORK_METHODS],
        created_at=engine.get("createTime"),
        updated_at=engine.get("updateTime"),
    )


_SESSION_PAGE_SIZE = 50
# A single session is not representative: a turn where the agent answered from
# context shows no tool calls at all. Walk back a few until tools appear, but
# cap it so page cost does not scale with production traffic.
_MAX_SESSIONS_INSPECTED = 3


async def _annotate_from_sessions(client: AgentEngineClient, deployment: Deployment) -> None:
    """Fill in activity, observed tools, and sub-agent authors from recent sessions."""
    try:
        sessions = await client.list_sessions(
            deployment.resource_name,
            page_size=_SESSION_PAGE_SIZE,
            order_by="updateTime desc",
        )
    except AgentEngineError as exc:
        deployment.probe_error = str(exc)[:300]
        return

    deployment.session_count = len(sessions)
    deployment.session_count_capped = len(sessions) >= _SESSION_PAGE_SIZE
    if not sessions:
        return
    deployment.last_activity_at = sessions[0].get("updateTime") or sessions[0].get("createTime")

    tools: list[str] = []
    authors: list[str] = []
    for session in sessions[:_MAX_SESSIONS_INSPECTED]:
        try:
            events = await client.list_events(
                deployment.resource_name, session["name"].split("/")[-1]
            )
        except AgentEngineError as exc:
            deployment.probe_error = str(exc)[:300]
            break
        deployment.sessions_inspected += 1
        for event in events:
            author = event.get("author")
            if author and author not in authors:
                authors.append(author)
            for part in (event.get("content") or {}).get("parts") or []:
                call = part.get("functionCall")
                if call and call.get("name") and call["name"] not in tools:
                    tools.append(call["name"])
        if tools:
            break

    deployment.observed_tools = tools
    deployment.observed_authors = authors


def _purpose_guess(deployment: Deployment) -> str | None:
    """Draft a purpose line from what is actually known about the deployment."""
    if deployment.description:
        return deployment.description
    readable = deployment.display_name.strip()
    if not readable:
        return None
    parts = [f"{readable}."]
    if deployment.observed_tools:
        parts.append(f"Uses tools: {', '.join(deployment.observed_tools)}.")
    sub_agents = [a for a in deployment.observed_authors if a and a != "user"]
    if len(sub_agents) > 1:
        parts.append(f"Multi-agent pipeline: {' -> '.join(sub_agents)}.")
    return " ".join(parts)


def clear_cache() -> None:
    _cache.clear()
