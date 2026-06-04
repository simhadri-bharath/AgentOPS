"""Vertex AI Gemini backend for DeepEval metrics (GCP ADC, no OpenAI key)."""

from __future__ import annotations

import asyncio

from deepeval.models.base_model import DeepEvalBaseLLM

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.gcp.auth import require_adc

logger = get_logger(__name__)


class VertexGeminiJudge(DeepEvalBaseLLM):
    """DeepEval-compatible Gemini judge using Application Default Credentials."""

    def __init__(self, model: str, *, temperature: float = 0.0) -> None:
        self._model_name = model
        self._temperature = temperature
        self._client_model = None
        super().__init__(model)

    def load_model(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        settings = get_settings()
        auth = require_adc()
        project = settings.gcp_project_id or auth.project_id
        if not project:
            raise RuntimeError(
                "GCP_PROJECT_ID or ADC project required for DeepEval Gemini judge"
            )

        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=project, location=settings.gcp_region)
        model_id = self._model_name
        if not model_id.startswith("gemini-"):
            model_id = f"gemini-{model_id}"
        self._client_model = GenerativeModel(model_id)
        logger.debug(
            "VertexGeminiJudge loaded",
            extra={"component": "vertex_gemini_judge", "model": model_id},
        )
        return self._client_model

    def generate(self, prompt: str, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        if "schema" in kwargs:
            raise TypeError("Schema-based generation is not supported directly by this custom judge.")
        if self._client_model is None:
            self.load_model()
        assert self._client_model is not None
        response = self._client_model.generate_content(
            prompt,
            generation_config={"temperature": self._temperature},
        )
        return (response.text or "").strip()

    async def a_generate(self, prompt: str, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        if "schema" in kwargs:
            raise TypeError("Schema-based generation is not supported directly by this custom judge.")
        return await asyncio.to_thread(self.generate, prompt, *args, **kwargs)

    def get_model_name(self, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        return self._model_name

