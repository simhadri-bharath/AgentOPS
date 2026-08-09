"""Async REST client for Vertex AI Agent Engine (reasoningEngines).

Uses the public v1 REST surface rather than the Vertex SDK, because the SDK path
previously in use went through `client.agent_engines._stream_query` -- a private
method that breaks silently on an SDK bump.

Interface choice is settled by the Phase 1 compatibility probe (see
docs/invocation_compatibility.md): `:query` cannot dispatch an ADK agent's
streaming class methods and returns 404, so `:streamQuery` is the only working
invocation endpoint. INVOCATION_ENDPOINT / INVOCATION_CLASS_METHOD below are the
single place that decision lives.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import google.auth
import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Settled by Phase 1. `:query` 404s against ADK agents -- it dispatches only
# non-streaming class methods, and AdkApp registers none.
INVOCATION_ENDPOINT = "streamQuery"
INVOCATION_CLASS_METHOD = "stream_query"

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_TOKEN_REFRESH_MARGIN_S = 300


class AgentEngineError(RuntimeError):
    """Agent Engine returned an error. `kind` maps to the invocation state machine."""

    def __init__(self, message: str, *, status: int | None = None, kind: str = "AGENT_ERROR"):
        super().__init__(message)
        self.status = status
        self.kind = kind


def classify_http_error(status: int, body: str) -> str:
    """Map an HTTP failure onto an invocation state.

    Agent Engine returns 404 for both "engine does not exist" and "class method
    not found", so the body has to be read -- status alone cannot tell an agent
    bug from a config bug.
    """
    if status in (401, 403):
        return "AUTH_ERROR"
    if status == 429:
        return "RATE_LIMITED"
    if status == 404 and "not found" in body.lower() and "method" in body.lower():
        return "AGENT_ERROR"
    if status == 404:
        return "AGENT_ERROR"
    if status in (408, 504):
        return "TIMEOUT"
    return "AGENT_ERROR"


class _TokenSource:
    """ADC access token with in-process caching.

    google.auth refresh is blocking, so it runs in a thread. One lock stops a
    burst of concurrent invocations from all refreshing at once.
    """

    def __init__(self) -> None:
        self._credentials = None
        self._default_project: str | None = None
        self._lock = asyncio.Lock()

    async def token(self) -> str:
        async with self._lock:
            if self._credentials is None:
                self._credentials, self._default_project = await asyncio.to_thread(
                    google.auth.default, scopes=_SCOPES
                )
            if not self._is_fresh(self._credentials):
                await asyncio.to_thread(self._credentials.refresh, GoogleAuthRequest())
            return self._credentials.token

    async def default_project(self) -> str | None:
        await self.token()
        return self._default_project

    @staticmethod
    def _is_fresh(credentials: Any) -> bool:
        if not getattr(credentials, "token", None):
            return False
        expiry = getattr(credentials, "expiry", None)
        if expiry is None:
            return bool(credentials.valid)
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return (expiry - now).total_seconds() > _TOKEN_REFRESH_MARGIN_S


_token_source = _TokenSource()


class AgentEngineClient:
    """Thin async wrapper over the reasoningEngines REST surface."""

    def __init__(self, project: str | None = None, *, timeout_s: float = 600.0) -> None:
        settings = get_settings()
        self._project = project or settings.gcp_project_id
        self._timeout = timeout_s
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AgentEngineClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- plumbing -------------------------------------------------------

    async def _project_id(self) -> str:
        if self._project:
            return self._project
        project = await _token_source.default_project()
        if not project:
            raise AgentEngineError(
                "No GCP project. Set GCP_PROJECT_ID or configure ADC.",
                kind="AUTH_ERROR",
            )
        self._project = project
        return project

    async def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {await _token_source.token()}",
            "x-goog-user-project": await self._project_id(),
            "Content-Type": "application/json",
        }

    @staticmethod
    def base_url(region: str) -> str:
        return f"https://{region}-aiplatform.googleapis.com/v1"

    async def resource_name(self, region: str, engine_id: str) -> str:
        project = await self._project_id()
        return (
            f"projects/{project}/locations/{region}/reasoningEngines/{engine_id}"
        )

    @staticmethod
    def region_of(resource_name: str) -> str:
        if "locations/" in resource_name:
            return resource_name.split("locations/")[1].split("/")[0]
        return get_settings().gcp_region.split(",")[0].strip() or "us-central1"

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("AgentEngineClient must be used as an async context manager")
        return self._client

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        client = self._require_client()
        try:
            response = await client.request(method, url, headers=await self._headers(), **kwargs)
        except httpx.TimeoutException as exc:
            raise AgentEngineError(f"Timeout calling {url}: {exc}", kind="TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise AgentEngineError(f"Transport error calling {url}: {exc}") from exc
        if response.status_code >= 400:
            body = response.text[:800]
            raise AgentEngineError(
                f"{response.status_code} from {url}: {body}",
                status=response.status_code,
                kind=classify_http_error(response.status_code, body),
            )
        return response

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._request("GET", url, params=params)
        return response.json() if response.content else {}

    # -- engines --------------------------------------------------------

    async def list_engines(self, region: str) -> list[dict[str, Any]]:
        project = await self._project_id()
        url = f"{self.base_url(region)}/projects/{project}/locations/{region}/reasoningEngines"
        engines: list[dict[str, Any]] = []
        params: dict[str, Any] = {"pageSize": 100}
        while True:
            data = await self._get_json(url, params)
            engines.extend(data.get("reasoningEngines", []))
            token = data.get("nextPageToken")
            if not token:
                return engines
            params = {"pageSize": 100, "pageToken": token}

    async def get_engine(self, region: str, engine_id: str) -> dict[str, Any]:
        name = await self.resource_name(region, engine_id)
        return await self._get_json(f"{self.base_url(region)}/{name}")

    # -- sessions -------------------------------------------------------

    async def list_sessions(
        self,
        resource_name: str,
        *,
        page_size: int = 50,
        order_by: str = "updateTime desc",
    ) -> list[dict[str, Any]]:
        """List sessions, newest first.

        order_by is passed explicitly -- the API's default ordering is not
        documented, and "last activity" must not depend on it.
        """
        region = self.region_of(resource_name)
        url = f"{self.base_url(region)}/{resource_name}/sessions"
        data = await self._get_json(url, {"pageSize": page_size, "orderBy": order_by})
        return data.get("sessions", [])

    async def create_session(self, resource_name: str, user_id: str) -> str:
        """Create a session and return its ID.

        sessions.create is a long-running operation, so the operation is polled
        rather than assumed complete.
        """
        region = self.region_of(resource_name)
        response = await self._request(
            "POST",
            f"{self.base_url(region)}/{resource_name}/sessions",
            json={"userId": user_id},
        )
        operation = response.json()
        name = (operation.get("response") or {}).get("name")
        if not name:
            name = await self._await_operation(region, operation)
        return name.split("/")[-1]

    async def _await_operation(
        self, region: str, operation: dict[str, Any], timeout_s: float = 120.0
    ) -> str:
        op_name = operation.get("name")
        if not op_name:
            raise AgentEngineError(f"Operation has no name: {operation}")
        deadline = time.monotonic() + timeout_s
        delay = 0.5
        while time.monotonic() < deadline:
            current = await self._get_json(f"{self.base_url(region)}/{op_name}")
            if current.get("done"):
                if "error" in current:
                    raise AgentEngineError(f"Operation failed: {current['error']}")
                return current["response"]["name"]
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 5.0)
        raise AgentEngineError(f"Operation {op_name} did not complete", kind="TIMEOUT")

    async def delete_session(self, resource_name: str, session_id: str) -> None:
        region = self.region_of(resource_name)
        try:
            await self._request(
                "DELETE", f"{self.base_url(region)}/{resource_name}/sessions/{session_id}"
            )
        except AgentEngineError as exc:
            # Cleanup failure must never mask the result it was cleaning up after.
            logger.warning(
                "Session cleanup failed for %s: %s",
                session_id,
                exc,
                extra={"component": "agent_engine_client"},
            )

    async def list_events(self, resource_name: str, session_id: str) -> list[dict[str, Any]]:
        region = self.region_of(resource_name)
        url = f"{self.base_url(region)}/{resource_name}/sessions/{session_id}/events"
        events: list[dict[str, Any]] = []
        params: dict[str, Any] = {"pageSize": 200}
        while True:
            data = await self._get_json(url, params)
            events.extend(data.get("sessionEvents", []))
            token = data.get("nextPageToken")
            if not token:
                return events
            params = {"pageSize": 200, "pageToken": token}

    # -- invocation -----------------------------------------------------

    async def stream_query(
        self,
        resource_name: str,
        *,
        user_id: str,
        session_id: str,
        message: str,
        class_method: str = INVOCATION_CLASS_METHOD,
    ) -> list[dict[str, Any]]:
        """Invoke the agent and return the full list of streamed ADK events.

        The response is a JSON array of event objects; the answer text lives in
        the LAST element with text content, not the first.
        """
        region = self.region_of(resource_name)
        url = f"{self.base_url(region)}/{resource_name}:{INVOCATION_ENDPOINT}"
        body = {
            "classMethod": class_method,
            "input": {"user_id": user_id, "session_id": session_id, "message": message},
        }
        client = self._require_client()
        chunks: list[dict[str, Any]] = []
        try:
            async with client.stream(
                "POST", url, headers=await self._headers(), json=body
            ) as response:
                if response.status_code >= 400:
                    raw = (await response.aread()).decode("utf-8", "replace")[:800]
                    raise AgentEngineError(
                        f"{response.status_code} from streamQuery: {raw}",
                        status=response.status_code,
                        kind=classify_http_error(response.status_code, raw),
                    )
                buffer = ""
                async for line in response.aiter_lines():
                    parsed, buffer = _consume_stream_line(line, buffer)
                    if parsed is not None:
                        chunks.append(parsed)
                if buffer.strip():
                    leftover = _try_parse(buffer)
                    if leftover is not None:
                        chunks.append(leftover)
        except httpx.TimeoutException as exc:
            raise AgentEngineError(f"streamQuery timed out: {exc}", kind="TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise AgentEngineError(f"streamQuery transport error: {exc}") from exc
        return chunks


def _try_parse(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _consume_stream_line(line: str, buffer: str) -> tuple[dict[str, Any] | None, str]:
    """Accumulate a streamed line into a complete JSON object.

    The response is a JSON array delivered in chunks, so lines arrive with array
    punctuation attached and a single object may span several lines.
    """
    if not line:
        return None, buffer
    cleaned = line.strip()
    if cleaned.startswith("data:"):
        cleaned = cleaned[5:].strip()
    cleaned = cleaned.lstrip("[,").rstrip("]")
    if not cleaned.strip():
        return None, buffer
    buffer += cleaned
    parsed = _try_parse(buffer)
    if parsed is not None:
        return parsed, ""
    return None, buffer
