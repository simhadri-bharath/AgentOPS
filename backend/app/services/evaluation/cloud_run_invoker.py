"""Cloud Run agent invocation via authenticated HTTP requests."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import requests
import google.auth
import google.auth.transport.requests

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class InvokeResult:
    output: str
    latency_ms: int
    raw: Any | None = None
    error: str | None = None


class CloudRunInvoker:
    """
    Invokes Cloud Run agents via authenticated HTTP requests.
    Supports multiple interface patterns and auto-detects
    what the agent accepts.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._session: requests.Session | None = None
        self._id_token_cache: dict[str, tuple[str, float]] = {}
        self._endpoint_interface_cache: dict[str, str] = {}

    def initialize(self) -> None:
        """Initialize the HTTP session for reuse."""
        if self._session is None:
            self._session = requests.Session()
        logger.info(
            "CloudRunInvoker initialized",
            extra={"component": "cloud_run_invoker"},
        )

    def _get_id_token(self, audience: str) -> str:
        """Get a GCP ID token for authenticating to a Cloud Run service."""
        # Check cache (tokens are valid for ~1 hour, we cache for 50 min)
        cached = self._id_token_cache.get(audience)
        if cached:
            token, expiry = cached
            if time.time() < expiry:
                return token

        try:
            # Use google-auth to get an ID token for the target audience
            auth_req = google.auth.transport.requests.Request()
            credentials, _ = google.auth.default()

            # For service accounts, use IDTokenCredentials
            # For user credentials (ADC), use the impersonation approach
            from google.oauth2 import id_token as id_token_module
            token = id_token_module.fetch_id_token(auth_req, audience)

            # Cache for 50 minutes
            self._id_token_cache[audience] = (token, time.time() + 3000)
            return token
        except Exception as exc:
            logger.info(
                "Standard ID token fetch failed for %s: %s — trying gcloud auth fallback",
                audience,
                exc,
                extra={"component": "cloud_run_invoker"},
            )
            # Try gcloud CLI fallback (highly reliable for local developer user-based ADC)
            try:
                import subprocess
                command_with_aud = [
                    "gcloud", "auth", "print-identity-token",
                    f"--audiences={audience}"
                ]
                token = ""
                try:
                    token = subprocess.check_output(command_with_aud, text=True, stderr=subprocess.DEVNULL).strip()
                except Exception:
                    try:
                        token = subprocess.check_output(command_with_aud, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
                    except Exception:
                        pass

                # If that fails (e.g. user credentials), try printing standard token without audiences
                if not token:
                    command_no_aud = ["gcloud", "auth", "print-identity-token"]
                    try:
                        token = subprocess.check_output(command_no_aud, text=True, stderr=subprocess.DEVNULL).strip()
                    except Exception:
                        try:
                            token = subprocess.check_output(command_no_aud, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
                        except Exception:
                            pass

                if token:
                    self._id_token_cache[audience] = (token, time.time() + 3000)
                    return token
            except Exception as gcloud_exc:
                logger.warning(
                    "gcloud ID token fallback failed: %s",
                    gcloud_exc,
                    extra={"component": "cloud_run_invoker"},
                )

            # Try with access token instead (works for some configurations)
            try:
                credentials, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                auth_req = google.auth.transport.requests.Request()
                credentials.refresh(auth_req)
                return credentials.token
            except Exception:
                return ""

    def _get_base_url(self, endpoint_url: str) -> str:
        """Extract the base URL from an endpoint URL."""
        url = endpoint_url.rstrip("/")
        return url

    def invoke_agent(
        self,
        endpoint_url: str,
        prompt: str,
        *,
        context: str | None = None,
        user_id: str = "agentops_eval_user",
    ) -> InvokeResult:
        """Invoke a Cloud Run agent with a single prompt."""
        if self._session is None:
            self.initialize()

        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\nUser:\n{prompt}"

        base_url = self._get_base_url(endpoint_url)
        token = self._get_id_token(base_url)

        headers = {
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Check cached interface type
        cached_interface = self._endpoint_interface_cache.get(base_url)
        if cached_interface:
            return self._invoke_with_interface(
                base_url, cached_interface, full_prompt, user_id, headers
            )

        # Auto-detect interface by trying patterns in order
        interfaces = [
            ("adk_root", self._try_adk_root),
            ("adk_query", self._try_adk_query),
            ("adk_plan", self._try_adk_plan),
            ("a2a_send", self._try_a2a_send),
            ("generic_query", self._try_generic_query),
            ("generic_chat", self._try_generic_chat),
            ("generic_invoke", self._try_generic_invoke),
        ]

        last_error = ""
        for interface_name, try_fn in interfaces:
            result = try_fn(base_url, full_prompt, user_id, headers)
            if result.output or (result.error and "404" not in (result.error or "")):
                # Cache the working interface
                self._endpoint_interface_cache[base_url] = interface_name
                return result
            last_error = result.error or last_error

        return InvokeResult(
            output="",
            latency_ms=0,
            error=f"Could not invoke Cloud Run agent at {base_url}. "
                  f"Tried multiple interface patterns. Last error: {last_error}",
        )

    def _invoke_with_interface(
        self,
        base_url: str,
        interface: str,
        prompt: str,
        user_id: str,
        headers: dict,
    ) -> InvokeResult:
        """Invoke using a known interface type."""
        fn_map = {
            "adk_root": self._try_adk_root,
            "adk_query": self._try_adk_query,
            "adk_plan": self._try_adk_plan,
            "a2a_send": self._try_a2a_send,
            "generic_query": self._try_generic_query,
            "generic_chat": self._try_generic_chat,
            "generic_invoke": self._try_generic_invoke,
        }
        fn = fn_map.get(interface, self._try_adk_root)
        return fn(base_url, prompt, user_id, headers)

    def _try_adk_plan(
        self, base_url: str, prompt: str, user_id: str, headers: dict
    ) -> InvokeResult:
        """ADK plan endpoint: POST /plan."""
        return self._http_invoke(
            url=f"{base_url}/plan",
            payload={
                "message": prompt,
                "user_id": user_id,
            },
            headers=headers,
        )

    def _try_a2a_send(
        self, base_url: str, prompt: str, user_id: str, headers: dict
    ) -> InvokeResult:
        """A2A task send: POST /tasks/send."""
        return self._http_invoke(
            url=f"{base_url}/tasks/send",
            payload={
                "message": {
                    "parts": [{"text": prompt}]
                }
            },
            headers=headers,
        )

    def _try_adk_root(
        self, base_url: str, prompt: str, user_id: str, headers: dict
    ) -> InvokeResult:
        """ADK-style: POST / with message and session_id."""
        return self._http_invoke(
            url=base_url,
            payload={
                "message": prompt,
                "user_id": user_id,
            },
            headers=headers,
        )

    def _try_adk_query(
        self, base_url: str, prompt: str, user_id: str, headers: dict
    ) -> InvokeResult:
        """ADK query endpoint: POST /query."""
        return self._http_invoke(
            url=f"{base_url}/query",
            payload={
                "message": prompt,
                "user_id": user_id,
            },
            headers=headers,
        )

    def _try_generic_query(
        self, base_url: str, prompt: str, user_id: str, headers: dict
    ) -> InvokeResult:
        """Generic: POST /query with input field."""
        return self._http_invoke(
            url=f"{base_url}/query",
            payload={"input": prompt, "query": prompt},
            headers=headers,
        )

    def _try_generic_chat(
        self, base_url: str, prompt: str, user_id: str, headers: dict
    ) -> InvokeResult:
        """Generic: POST /chat."""
        return self._http_invoke(
            url=f"{base_url}/chat",
            payload={"message": prompt, "input": prompt},
            headers=headers,
        )

    def _try_generic_invoke(
        self, base_url: str, prompt: str, user_id: str, headers: dict
    ) -> InvokeResult:
        """Generic: POST /invoke."""
        return self._http_invoke(
            url=f"{base_url}/invoke",
            payload={"input": prompt, "message": prompt},
            headers=headers,
        )

    def _http_invoke(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> InvokeResult:
        """Execute an HTTP POST and extract the response text."""
        assert self._session is not None

        start = time.perf_counter()
        try:
            resp = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=120,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)

            if resp.status_code == 404:
                return InvokeResult(
                    output="", latency_ms=latency_ms,
                    error=f"404 Not Found: {url}",
                )

            if resp.status_code >= 400:
                return InvokeResult(
                    output="",
                    latency_ms=latency_ms,
                    error=f"HTTP {resp.status_code}: {resp.text[:500]}",
                )

            # Try to extract text from response
            text = self._extract_response_text(resp)
            if text:
                return InvokeResult(
                    output=text,
                    latency_ms=latency_ms,
                    raw=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
                )

            return InvokeResult(
                output="",
                latency_ms=latency_ms,
                error=f"Empty response from {url}",
                raw=resp.text[:500],
            )
        except requests.exceptions.ConnectionError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return InvokeResult(
                output="", latency_ms=latency_ms,
                error=f"Connection failed: {exc}",
            )
        except requests.exceptions.Timeout:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return InvokeResult(
                output="", latency_ms=latency_ms,
                error=f"Timeout after {latency_ms}ms",
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return InvokeResult(
                output="", latency_ms=latency_ms,
                error=str(exc),
            )

    @staticmethod
    def _extract_response_text(resp: requests.Response) -> str:
        """Best-effort text extraction from various response formats."""
        content_type = resp.headers.get("content-type", "")

        # Plain text response
        if "text/plain" in content_type:
            return resp.text.strip()

        # JSON response — try common field names
        if "application/json" in content_type:
            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError):
                return resp.text.strip()

            if isinstance(data, str):
                return data.strip()

            if isinstance(data, dict):
                # A2A task output extraction: artifacts[0].parts[0].text
                artifacts = data.get("artifacts", [])
                if isinstance(artifacts, list) and artifacts:
                    first_art = artifacts[0]
                    if isinstance(first_art, dict):
                        parts = first_art.get("parts", [])
                        texts = []
                        for part in parts:
                            if isinstance(part, dict) and part.get("text"):
                                texts.append(str(part["text"]))
                        if texts:
                            return "".join(texts).strip()

                # Try common response field patterns
                for key in (
                    "output", "response", "text", "result", "answer",
                    "message", "content", "reply", "completion",
                ):
                    if key in data:
                        val = data[key]
                        if isinstance(val, str) and val.strip():
                            return val.strip()
                        if isinstance(val, dict):
                            # Nested: {"response": {"text": "..."}}
                            for sub_key in ("text", "output", "content", "message"):
                                if sub_key in val and isinstance(val[sub_key], str):
                                    return val[sub_key].strip()

                # ADK-style events: content.parts[].text
                content = data.get("content", {})
                if isinstance(content, dict):
                    parts = content.get("parts", [])
                    texts = []
                    for part in parts:
                        if isinstance(part, dict) and part.get("text"):
                            texts.append(str(part["text"]))
                    if texts:
                        return "".join(texts).strip()

                # If data has events (list of event dicts), extract from last event
                events = data.get("events", [])
                if isinstance(events, list) and events:
                    last_event = events[-1]
                    if isinstance(last_event, dict):
                        event_content = last_event.get("content", {})
                        if isinstance(event_content, dict):
                            parts = event_content.get("parts", [])
                            for part in parts:
                                if isinstance(part, dict) and part.get("text"):
                                    return str(part["text"]).strip()

            if isinstance(data, list):
                # List of events — extract text from last
                if data:
                    last = data[-1]
                    if isinstance(last, dict):
                        content = last.get("content", {})
                        if isinstance(content, dict):
                            parts = content.get("parts", [])
                            for part in parts:
                                if isinstance(part, dict) and part.get("text"):
                                    return str(part["text"]).strip()

        # Fallback: raw text
        text = resp.text.strip()
        if text and len(text) < 50000:
            return text
        return ""

    def batch_invoke(
        self,
        endpoint_url: str,
        rows: list[dict[str, str]],
        *,
        user_id: str = "agentops_eval_user",
    ) -> list[InvokeResult]:
        """Invoke agent for each row sequentially (Cloud Run has no batch API)."""
        if not rows:
            return []

        results: list[InvokeResult] = []
        for row in rows:
            prompt = row.get("input", "").strip()
            context = row.get("context", "").strip() if row.get("context") else None
            result = self.invoke_agent(
                endpoint_url, prompt, context=context, user_id=user_id
            )
            results.append(result)

        return results
