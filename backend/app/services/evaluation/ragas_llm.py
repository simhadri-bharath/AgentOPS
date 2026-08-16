"""Vertex Gemini as a RAGAS judge.

RAGAS ships an `llm_factory`, but every path through it needs a provider client
this deployment does not have: the Instructor adapter requires a synchronous
`google.genai.Client` while the metrics call `agenerate()`, and the LiteLLM
adapter still demands a client instance. Rather than add LiteLLM and a second
credential path, this implements the two-method interface the metrics actually
require, on the ADC credentials the rest of the platform already uses.

No API key, no second judge to keep in sync with `JUDGE_MODEL`.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypeVar

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RagasUnavailable(RuntimeError):
    """ragas is not installed, so its metrics cannot run."""


def check_ragas_available() -> tuple[bool, str | None]:
    try:
        import ragas  # noqa: F401
    except ImportError:
        return False, "ragas is not installed. Run: pip install -r requirements.txt"
    return True, None


def _base_class() -> Any:
    from ragas.llms.base import InstructorBaseRagasLLM

    return InstructorBaseRagasLLM


def build_ragas_llm(model: str | None = None, temperature: float | None = None) -> Any:
    """A RAGAS-compatible judge backed by Vertex Gemini."""
    ok, error = check_ragas_available()
    if not ok:
        raise RagasUnavailable(error or "ragas unavailable")

    settings = get_settings()
    model = model or settings.judge_model
    temperature = settings.judge_temperature if temperature is None else temperature
    project = settings.gcp_project_id
    location = (settings.gcp_region or "us-central1").split(",")[0].strip()

    class VertexRagasLLM(_base_class()):  # type: ignore[misc]
        """Structured generation on Vertex, which is all RAGAS metrics need."""

        def __init__(self) -> None:
            from google import genai

            self._model = model
            self._temperature = temperature
            self._client = genai.Client(
                vertexai=True, project=project, location=location
            )

        def _config(self, response_model: type) -> dict[str, Any]:
            # RAGAS passes a Pydantic model and expects an instance back; Gemini
            # does that natively through response_schema.
            return {
                "response_mime_type": "application/json",
                "response_schema": response_model,
                "temperature": self._temperature,
            }

        def generate(self, prompt: str, response_model: type[T]) -> T:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=self._config(response_model),
            )
            parsed = response.parsed
            if parsed is None:
                raise ValueError(
                    f"Judge returned no parseable {response_model.__name__}"
                )
            return parsed

        async def agenerate(self, prompt: str, response_model: type[T]) -> T:
            # The genai async client leaks its aiohttp connector on teardown, so
            # the synchronous client is used on a worker thread instead. The
            # call is I/O-bound either way.
            return await asyncio.to_thread(self.generate, prompt, response_model)

    return VertexRagasLLM()


def build_ragas_embeddings() -> Any:
    """Vertex embeddings, needed by RAGAS answer relevancy.

    `use_vertex=True` alone is not enough: GoogleEmbeddings still requires a
    configured client, and without one every answer-relevancy score fails with
    "Vertex AI embeddings require a client".
    """
    from google import genai
    from ragas.embeddings import GoogleEmbeddings

    settings = get_settings()
    location = (settings.gcp_region or "us-central1").split(",")[0].strip()
    client = genai.Client(
        vertexai=True, project=settings.gcp_project_id, location=location
    )
    return GoogleEmbeddings(
        client=client,
        use_vertex=True,
        project_id=settings.gcp_project_id,
        location=location,
    )


def ragas_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("ragas")
    except Exception:
        return None
