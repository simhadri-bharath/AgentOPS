"""Vertex AI evaluation framework adapter (MVP stub for future managed metrics)."""

from app.core.logging import get_logger

logger = get_logger(__name__)


class VertexAIEvaluator:
    """
    Placeholder for future Vertex AI managed rubric metrics
    (client.evals.create_evaluation_run from the reference notebook).
    MVP uses simple local metrics only via SampleEvaluator.
    """

    framework_name = "vertex_ai"

    def supports_managed_metrics(self) -> bool:
        return False
