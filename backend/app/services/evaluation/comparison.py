"""Compare two evaluation runs.

A score moving is only evidence about the agent if the harness did not move
with it. Every comparison therefore reports what differs in the run snapshots
alongside the deltas, so a judge-model change is never read as a regression.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Below this, a difference is noise rather than a finding.
SIGNIFICANT_DELTA = 0.02

# Snapshot fields that make two runs incomparable if they differ.
COMPARABILITY_KEYS = {
    "evaluator_model": "judge model",
    "evaluator_temperature": "judge temperature",
    "metric_config_version": "metric definitions",
    "dataset_id": "dataset",
    "dataset_version": "dataset version",
    "invocation_interface": "invocation interface",
}


@dataclass
class MetricDelta:
    metric: str
    current: float | None
    baseline: float | None
    delta: float | None
    direction: str  # improved | regressed | unchanged | new | dropped
    significant: bool = False


@dataclass
class SampleDelta:
    sample_index: int
    input: str
    metric: str
    current: float
    baseline: float
    delta: float


@dataclass
class SpanDelta:
    author: str
    metric: str
    current: float
    baseline: float
    delta: float


@dataclass
class RunComparisonResult:
    evaluation_id: str
    baseline_id: str
    comparable: bool
    warnings: list[str] = field(default_factory=list)
    metric_deltas: list[MetricDelta] = field(default_factory=list)
    regressed_samples: list[SampleDelta] = field(default_factory=list)
    span_deltas: list[SpanDelta] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _metric_values(aggregates: dict[str, Any]) -> dict[str, float]:
    return {
        key[len("avg_") :]: value
        for key, value in (aggregates or {}).items()
        if key.startswith("avg_")
        and key != "avg_latency_ms"
        and isinstance(value, (int, float))
    }


def _comparability(current: Any, baseline: Any) -> list[str]:
    """What changed in the harness between the two runs."""
    a = dict(getattr(current, "run_config", None) or {})
    b = dict(getattr(baseline, "run_config", None) or {})
    warnings: list[str] = []

    if not a or not b:
        warnings.append(
            "One or both runs predate run snapshots, so it cannot be confirmed "
            "that the same judge, dataset version and metric definitions were used."
        )

    for key, label in COMPARABILITY_KEYS.items():
        left, right = a.get(key), b.get(key)
        if left is not None and right is not None and left != right:
            warnings.append(
                f"Different {label}: this run used {left!r}, baseline used {right!r}. "
                "The change in score may be the harness, not the agent."
            )

    left_versions = (a.get("framework_versions") or {}).get("deepeval")
    right_versions = (b.get("framework_versions") or {}).get("deepeval")
    if left_versions and right_versions and left_versions != right_versions:
        warnings.append(
            f"Different deepeval version: {left_versions} vs {right_versions}."
        )

    if a.get("agent_resource_name") and a.get("agent_resource_name") != b.get(
        "agent_resource_name"
    ):
        warnings.append("Runs targeted different agents.")

    return warnings


def _sample_regressions(
    current_results: list[Any], baseline_results: list[Any]
) -> list[SampleDelta]:
    """Per-sample drops, so a regression can be traced to specific cases."""
    baseline_by_index = {r.sample_index: r for r in baseline_results}
    deltas: list[SampleDelta] = []
    for row in current_results:
        base = baseline_by_index.get(row.sample_index)
        if base is None:
            continue
        for metric, value in (row.scores or {}).items():
            other = (base.scores or {}).get(metric)
            if not isinstance(value, (int, float)) or not isinstance(other, (int, float)):
                continue
            delta = round(value - other, 4)
            if delta <= -SIGNIFICANT_DELTA:
                deltas.append(
                    SampleDelta(
                        sample_index=row.sample_index,
                        input=(row.input or "")[:160],
                        metric=metric,
                        current=value,
                        baseline=other,
                        delta=delta,
                    )
                )
    deltas.sort(key=lambda d: d.delta)
    return deltas


def _span_averages(results: list[Any]) -> dict[tuple[str, str], list[float]]:
    totals: dict[tuple[str, str], list[float]] = {}
    for row in results:
        for span in row.span_scores or []:
            author = span.get("author") or "unknown"
            for metric, value in (span.get("scores") or {}).items():
                if isinstance(value, (int, float)):
                    totals.setdefault((author, metric), []).append(value)
    return totals


def _span_deltas(current_results: list[Any], baseline_results: list[Any]) -> list[SpanDelta]:
    """Attribute a change to a sub-agent.

    This is what makes a regression actionable: "faithfulness fell" is a fact,
    "research_agent's faithfulness fell" is a place to look.
    """
    current = _span_averages(current_results)
    baseline = _span_averages(baseline_results)
    deltas: list[SpanDelta] = []
    for key, values in current.items():
        if key not in baseline:
            continue
        now = sum(values) / len(values)
        before = sum(baseline[key]) / len(baseline[key])
        delta = round(now - before, 4)
        if abs(delta) >= SIGNIFICANT_DELTA:
            author, metric = key
            deltas.append(
                SpanDelta(
                    author=author,
                    metric=metric,
                    current=round(now, 4),
                    baseline=round(before, 4),
                    delta=delta,
                )
            )
    deltas.sort(key=lambda d: d.delta)
    return deltas


def build_comparison(
    current: Any,
    baseline: Any,
    current_results: list[Any],
    baseline_results: list[Any],
) -> Any:
    from app.schemas.evaluation import RunComparison

    now = _metric_values(current.aggregate_scores or {})
    before = _metric_values(baseline.aggregate_scores or {})

    metric_deltas: list[MetricDelta] = []
    for metric in sorted(set(now) | set(before)):
        a, b = now.get(metric), before.get(metric)
        if a is None:
            direction, delta = "dropped", None
        elif b is None:
            direction, delta = "new", None
        else:
            delta = round(a - b, 4)
            if abs(delta) < SIGNIFICANT_DELTA:
                direction = "unchanged"
            else:
                direction = "improved" if delta > 0 else "regressed"
        metric_deltas.append(
            MetricDelta(
                metric=metric,
                current=a,
                baseline=b,
                delta=delta,
                direction=direction,
                significant=delta is not None and abs(delta) >= SIGNIFICANT_DELTA,
            )
        )

    warnings = _comparability(current, baseline)
    regressed = [d for d in metric_deltas if d.direction == "regressed"]
    improved = [d for d in metric_deltas if d.direction == "improved"]

    if regressed:
        worst = min(regressed, key=lambda d: d.delta or 0)
        summary = (
            f"{len(regressed)} metric(s) regressed; worst is {worst.metric} "
            f"{worst.baseline} -> {worst.current} ({worst.delta:+.4f})."
        )
    elif improved:
        summary = f"{len(improved)} metric(s) improved, none regressed."
    else:
        summary = "No significant change."

    span_deltas = _span_deltas(current_results, baseline_results)
    regressed_spans = [s for s in span_deltas if s.delta < 0]
    if regressed_spans:
        worst_span = regressed_spans[0]
        summary += (
            f" Largest sub-agent drop: {worst_span.author} {worst_span.metric} "
            f"({worst_span.delta:+.4f})."
        )

    return RunComparison(
        evaluation_id=current.id,
        baseline_id=baseline.id,
        comparable=not warnings,
        warnings=warnings,
        summary=summary,
        metric_deltas=[asdict(d) for d in metric_deltas],
        regressed_samples=[asdict(d) for d in _sample_regressions(current_results, baseline_results)][:50],
        span_deltas=[asdict(d) for d in span_deltas],
    )
