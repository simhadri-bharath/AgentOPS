"""Shared LLM judge for every DeepEval metric.

Replaces the hand-rolled VertexGeminiJudge, which raised
TypeError("Schema-based generation is not supported...") whenever a metric
asked for structured output -- silently breaking every DeepEval metric that
prefers schema-constrained generation.

DeepEval 3.9 ships a native Vertex-backed Gemini model, so the custom subclass
is unnecessary. One judge now serves evaluation and (later) red-team, instead
of three modules each hardcoding a different default model.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.gcp.auth import require_adc

logger = get_logger(__name__)

# Rough Gemini Flash pricing, USD per 1M tokens. Used to show what a run cost;
# not billing-accurate, and deliberately reported as an estimate.
_COST_PER_1M_INPUT = 0.075
_COST_PER_1M_OUTPUT = 0.30


class JudgeUnavailableError(RuntimeError):
    """The judge could not be constructed. Distinct from a judge that ran and failed."""


@lru_cache(maxsize=4)
def get_judge(model: str | None = None, temperature: float | None = None) -> Any:
    """Build the shared Gemini judge, backed by the ADC the app already needs."""
    settings = get_settings()
    model_name = model or settings.judge_model
    temp = settings.judge_temperature if temperature is None else temperature

    auth = require_adc()
    project = settings.gcp_project_id or auth.project_id
    if not project:
        raise JudgeUnavailableError(
            "GCP_PROJECT_ID or an ADC project is required for the evaluation judge."
        )
    region = (settings.gcp_region or "us-central1").split(",")[0].strip()

    try:
        from deepeval.models import GeminiModel
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise JudgeUnavailableError(f"deepeval is not installed: {exc}") from exc

    try:
        judge = GeminiModel(
            model=model_name,
            project=project,
            location=region,
            use_vertexai=True,
            temperature=temp,
        )
    except Exception as exc:
        raise JudgeUnavailableError(
            f"Could not initialise Gemini judge '{model_name}' in {project}/{region}: {exc}"
        ) from exc

    logger.info(
        "Evaluation judge ready",
        extra={"component": "judge", "model": model_name, "location": region},
    )
    return judge


def judge_info(model: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    return {
        "evaluator_framework": "deepeval",
        "evaluator_model": model or settings.judge_model,
        "evaluator_temperature": settings.judge_temperature,
    }


def estimate_cost_usd(tokens_in: int, tokens_out: int) -> float:
    return round(
        (tokens_in / 1_000_000) * _COST_PER_1M_INPUT
        + (tokens_out / 1_000_000) * _COST_PER_1M_OUTPUT,
        6,
    )


def framework_versions() -> dict[str, str]:
    """Snapshot library versions so an old score stays interpretable."""
    versions: dict[str, str] = {}
    for package in ("deepeval", "google-genai", "google-cloud-aiplatform", "httpx"):
        try:
            from importlib.metadata import version

            versions[package] = version(package)
        except Exception:
            versions[package] = "unknown"
    return versions
