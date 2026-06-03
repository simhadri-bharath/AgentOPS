"""Vertex AI Gemini backend for DeepEval metrics (GCP ADC, no OpenAI key)."""

from __future__ import annotations

import asyncio
import json

from deepeval.models.base_model import DeepEvalBaseLLM

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.gcp.auth import require_adc

logger = get_logger(__name__)

RETIRED_MODEL_FALLBACKS: dict[str, str] = {
    "gemini-1.5-pro": "gemini-2.5-pro",
    "gemini-1.5-pro-001": "gemini-2.5-pro",
    "gemini-1.5-pro-002": "gemini-2.5-pro",
    "gemini-2.0-flash": "gemini-2.5-pro",
    "gemini-2.0-flash-001": "gemini-2.5-pro",
    "gemini-1.5-flash": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-001": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-002": "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite": "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite-001": "gemini-2.5-flash-lite",
}


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
        model_id = self._normalize_model_id(self._model_name)
        self._client_model = GenerativeModel(model_id)
        logger.debug(
            "VertexGeminiJudge loaded",
            extra={"component": "vertex_gemini_judge", "model": model_id},
        )
        return self._client_model

    def generate(self, prompt: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self._client_model is None:
            self.load_model()
        assert self._client_model is not None
        schema = kwargs.get("schema")
        try:
            response = self._client_model.generate_content(
                prompt,
                generation_config={"temperature": self._temperature},
            )
        except Exception as exc:
            fallback_model = self._fallback_for_error(exc)
            if not fallback_model:
                raise
            logger.warning(
                "VertexGeminiJudge model fallback triggered",
                extra={
                    "component": "vertex_gemini_judge",
                    "requested_model": self._model_name,
                    "fallback_model": fallback_model,
                    "error": str(exc),
                },
            )
            self._model_name = fallback_model
            self._client_model = None
            self.load_model()
            assert self._client_model is not None
            response = self._client_model.generate_content(
                prompt,
                generation_config={"temperature": self._temperature},
            )
        text = (response.text or "").strip()
        if schema is None:
            return text
        return self._coerce_schema_response(text, schema)

    async def a_generate(self, prompt: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await asyncio.to_thread(self.generate, prompt, *args, **kwargs)

    def get_model_name(self, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        return self._model_name

    @staticmethod
    def _normalize_model_id(model_name: str) -> str:
        model_id = model_name
        if not model_id.startswith("gemini-"):
            model_id = f"gemini-{model_id}"
        return RETIRED_MODEL_FALLBACKS.get(model_id, model_id)

    def _fallback_for_error(self, exc: Exception) -> str | None:
        message = str(exc)
        if "Publisher Model" not in message and "404" not in message:
            return None
        normalized = self._normalize_model_id(self._model_name)
        fallback = RETIRED_MODEL_FALLBACKS.get(normalized)
        if fallback and fallback != normalized:
            return fallback
        return None

    @staticmethod
    def _coerce_schema_response(text: str, schema):  # type: ignore[no-untyped-def]
        try:
            payload = json.loads(text)
        except Exception:
            from deepeval.metrics.utils import trimAndLoadJson

            payload = trimAndLoadJson(text)

        if hasattr(schema, "model_validate"):
            return schema.model_validate(payload)
        return schema.parse_obj(payload)
