"""The metric catalogue: one source of truth that can explain itself.

Replaces FRAMEWORK_METRIC_EXECUTION_MAP, which rewrote every named metric into
a string comparison before the run was queued -- faithfulness became
`contains_expected`, toxicity became `response_nonempty`. Users saw real metric
names over `str.__contains__` results.

A metric now either runs, or reports why it cannot. It never silently degrades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.services.evaluation.trace_model import EvaluationCase


@dataclass(frozen=True)
class MetricSpec:
    name: str
    label: str
    executor: str  # deterministic | trace_health | deepeval
    description: str
    requires: tuple[str, ...] = ()
    level: str = "trace"  # trace | span
    supports_span: bool = False
    requires_reference: bool = False
    cost: str = "free"  # free | low | medium | high
    category: str = "quality"
    higher_is_better: bool = True

    def unavailable_reason(self, available: set[str]) -> str | None:
        """Why this metric cannot run against a case, in words a user can act on."""
        missing = [f for f in self.requires if f not in available]
        if not missing:
            return None
        hints = {
            "expected_output": (
                "expected_output is missing. Add it to the dataset, or review a "
                "bootstrapped dataset and fill it in."
            ),
            "retrieval_context": (
                "retrieval_context is missing. The agent made no retrieval tool "
                "call on this sample, so there is nothing to check groundedness "
                "against."
            ),
            "reference_trajectory": (
                "reference_trajectory is missing. Build one from production "
                "sessions and review it."
            ),
            "predicted_trajectory": (
                "predicted_trajectory is missing. The agent called no tools on "
                "this sample."
            ),
            "conversation": "conversation is missing. This metric needs a multi-turn sample.",
        }
        return " ".join(hints.get(f, f"{f} is missing.") for f in missing)


DETERMINISTIC = "deterministic"
TRACE_HEALTH = "trace_health"
DEEPEVAL = "deepeval"


_SPECS: tuple[MetricSpec, ...] = (
    # -- deterministic, no LLM, no cost ---------------------------------
    MetricSpec(
        name="exact_match",
        label="Exact match",
        executor=DETERMINISTIC,
        description="Output matches expected_output exactly, ignoring case and surrounding space.",
        requires=("actual_output", "expected_output"),
        requires_reference=True,
        category="deterministic",
    ),
    MetricSpec(
        name="contains_expected",
        label="Contains expected",
        executor=DETERMINISTIC,
        description="Expected output appears somewhere in the response.",
        requires=("actual_output", "expected_output"),
        requires_reference=True,
        category="deterministic",
    ),
    MetricSpec(
        name="response_nonempty",
        label="Non-empty response",
        executor=DETERMINISTIC,
        description="The agent answered at all.",
        requires=("actual_output",),
        category="deterministic",
    ),
    MetricSpec(
        name="argument_match",
        label="Tool argument match",
        executor=DETERMINISTIC,
        description=(
            "Fraction of expected (tool, key, value) triples the agent got right. "
            "For a search agent the query it chose is most of the quality signal."
        ),
        requires=("predicted_trajectory", "reference_trajectory"),
        requires_reference=True,
        category="trajectory",
    ),
    MetricSpec(
        name="trajectory_in_order_match",
        label="Trajectory in-order match",
        executor=DETERMINISTIC,
        description="Tools were called in the reference order.",
        requires=("predicted_trajectory", "reference_trajectory"),
        requires_reference=True,
        category="trajectory",
    ),
    MetricSpec(
        name="trajectory_any_order_match",
        label="Trajectory any-order match",
        executor=DETERMINISTIC,
        description="The same set of tools was called, order ignored.",
        requires=("predicted_trajectory", "reference_trajectory"),
        requires_reference=True,
        category="trajectory",
    ),
    MetricSpec(
        name="trajectory_precision",
        label="Trajectory precision",
        executor=DETERMINISTIC,
        description="Share of the agent's tool calls that appear in the reference.",
        requires=("predicted_trajectory", "reference_trajectory"),
        requires_reference=True,
        category="trajectory",
    ),
    MetricSpec(
        name="trajectory_recall",
        label="Trajectory recall",
        executor=DETERMINISTIC,
        description="Share of reference tool calls the agent actually made.",
        requires=("predicted_trajectory", "reference_trajectory"),
        requires_reference=True,
        category="trajectory",
    ),
    # -- trace health: deterministic, needs no reference at all ----------
    MetricSpec(
        name="trace_tool_success_rate",
        label="Tool success rate",
        executor=TRACE_HEALTH,
        description="Share of tool calls that returned without error.",
        requires=("spans",),
        category="trace_health",
    ),
    MetricSpec(
        name="trace_no_redundant_calls",
        label="No redundant tool calls",
        executor=TRACE_HEALTH,
        description="Penalises the same tool being called twice with identical arguments.",
        requires=("spans",),
        category="trace_health",
    ),
    MetricSpec(
        name="trace_no_loop",
        label="No tool loop",
        executor=TRACE_HEALTH,
        description="Zero when a tool was called three or more times identically.",
        requires=("spans",),
        category="trace_health",
    ),
    MetricSpec(
        name="trace_step_efficiency",
        label="Step efficiency",
        executor=TRACE_HEALTH,
        description="How close the turn came to the minimum plausible number of steps.",
        requires=("spans",),
        category="trace_health",
    ),
    MetricSpec(
        name="trace_answered",
        label="Answered",
        executor=TRACE_HEALTH,
        description="The turn produced a final answer.",
        requires=("actual_output",),
        category="trace_health",
    ),
    # -- DeepEval, LLM-judged -------------------------------------------
    MetricSpec(
        name="answer_relevancy",
        label="Answer relevancy",
        executor=DEEPEVAL,
        description="Does the response actually address the question asked?",
        requires=("input", "actual_output"),
        supports_span=True,
        cost="medium",
        category="quality",
    ),
    MetricSpec(
        name="faithfulness",
        label="Faithfulness",
        executor=DEEPEVAL,
        description="Are the claims supported by the retrieved documents?",
        requires=("input", "actual_output", "retrieval_context"),
        supports_span=True,
        cost="medium",
        category="rag",
    ),
    MetricSpec(
        name="contextual_precision",
        label="Contextual precision",
        executor=DEEPEVAL,
        description="Are the relevant documents ranked above the irrelevant ones?",
        requires=("input", "actual_output", "expected_output", "retrieval_context"),
        requires_reference=True,
        supports_span=True,
        cost="medium",
        category="rag",
    ),
    MetricSpec(
        name="contextual_recall",
        label="Contextual recall",
        executor=DEEPEVAL,
        description="Did retrieval find everything the expected answer needs?",
        requires=("input", "actual_output", "expected_output", "retrieval_context"),
        requires_reference=True,
        supports_span=True,
        cost="medium",
        category="rag",
    ),
    MetricSpec(
        name="hallucination",
        label="Hallucination (inverted)",
        executor=DEEPEVAL,
        description="1.0 means nothing was contradicted by the retrieved context.",
        requires=("input", "actual_output", "retrieval_context"),
        supports_span=True,
        cost="medium",
        category="rag",
    ),
    MetricSpec(
        name="toxicity",
        label="Non-toxic (inverted)",
        executor=DEEPEVAL,
        description="1.0 means no toxic content was found.",
        requires=("input", "actual_output"),
        cost="medium",
        category="safety",
    ),
    MetricSpec(
        name="bias",
        label="Unbiased (inverted)",
        executor=DEEPEVAL,
        description="1.0 means no biased content was found.",
        requires=("input", "actual_output"),
        cost="medium",
        category="safety",
    ),
    MetricSpec(
        name="tool_correctness",
        label="Tool correctness",
        executor=DEEPEVAL,
        description="Were the right tools called, in the right order?",
        requires=("predicted_trajectory", "reference_trajectory"),
        requires_reference=True,
        cost="low",
        category="trajectory",
    ),
    MetricSpec(
        name="task_completion",
        label="Task completion",
        executor=DEEPEVAL,
        description=(
            "Judged from the trace: did the agent achieve what the user asked? "
            "Needs no reference trajectory."
        ),
        requires=("input", "actual_output"),
        cost="high",
        category="quality",
    ),
    MetricSpec(
        name="correctness",
        label="Correctness",
        executor=DEEPEVAL,
        description="Judged agreement between the response and the expected answer.",
        requires=("input", "actual_output", "expected_output"),
        requires_reference=True,
        supports_span=True,
        cost="medium",
        category="quality",
    ),
)

METRIC_REGISTRY: dict[str, MetricSpec] = {spec.name: spec for spec in _SPECS}

# Metric-config version, bumped when the catalogue changes. Snapshotted on every
# run so a score comparison months apart is meaningful.
METRIC_CONFIG_VERSION = "1"


class UnknownMetricError(ValueError):
    def __init__(self, unknown: Iterable[str]) -> None:
        names = sorted(set(unknown))
        super().__init__(
            f"Unknown metric(s): {names}. Valid metrics: {sorted(METRIC_REGISTRY)}"
        )
        self.unknown = names


def validate_metrics(metrics: Iterable[str]) -> list[str]:
    """Reject unknown metrics loudly instead of degrading them silently."""
    requested = [m for m in metrics if m]
    unknown = [m for m in requested if m not in METRIC_REGISTRY]
    if unknown:
        raise UnknownMetricError(unknown)
    seen: set[str] = set()
    ordered: list[str] = []
    for metric in requested:
        if metric not in seen:
            seen.add(metric)
            ordered.append(metric)
    return ordered


def specs_for(metrics: Iterable[str]) -> list[MetricSpec]:
    return [METRIC_REGISTRY[m] for m in metrics if m in METRIC_REGISTRY]


def group_by_executor(metrics: Iterable[str]) -> dict[str, list[MetricSpec]]:
    grouped: dict[str, list[MetricSpec]] = {}
    for spec in specs_for(metrics):
        grouped.setdefault(spec.executor, []).append(spec)
    return grouped


@dataclass
class MetricAvailability:
    name: str
    available: bool
    reason: str | None = None


def availability(metrics: Iterable[str], case: EvaluationCase) -> list[MetricAvailability]:
    present = case.available_fields()
    return [
        MetricAvailability(
            name=spec.name,
            available=spec.unavailable_reason(present) is None,
            reason=spec.unavailable_reason(present),
        )
        for spec in specs_for(metrics)
    ]


def catalogue() -> list[dict[str, object]]:
    """Serve the catalogue to the UI so the metric list has one definition."""
    return [
        {
            "name": spec.name,
            "label": spec.label,
            "executor": spec.executor,
            "description": spec.description,
            "requires": list(spec.requires),
            "level": spec.level,
            "supports_span": spec.supports_span,
            "requires_reference": spec.requires_reference,
            "cost": spec.cost,
            "category": spec.category,
            "higher_is_better": spec.higher_is_better,
        }
        for spec in _SPECS
    ]
