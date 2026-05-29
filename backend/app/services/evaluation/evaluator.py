"""Per-sample metric evaluation."""

from app.services.evaluation.metrics import MetricInput, compute_metrics


class SampleEvaluator:
    def evaluate_sample(
        self,
        *,
        actual_output: str,
        expected_output: str | None,
        latency_ms: int | None,
        metric_names: list[str],
    ) -> dict:
        scores = compute_metrics(
            MetricInput(
                actual_output=actual_output,
                expected_output=expected_output,
                latency_ms=latency_ms,
            ),
            metric_names,
        )
        scores["actual_output_nonempty"] = bool((actual_output or "").strip())
        return scores
