"""Metric packs chosen by what an agent is for.

Selection uses agent_type AND capabilities. Type alone is not enough: the live
chat agent is multi_agent and retrieval-backed, and a multi_agent pack without
the RAG metrics would miss the thing most likely to be wrong with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.evaluation.metric_registry import METRIC_REGISTRY

# Cheap, reference-free, and applicable to anything that answers at all.
BASELINE_METRICS = [
    "response_nonempty",
    "trace_answered",
    "trace_tool_success_rate",
    "trace_no_redundant_calls",
    "trace_no_loop",
]


@dataclass
class Profile:
    agent_type: str
    metrics: list[str] = field(default_factory=list)
    span_metrics: list[str] = field(default_factory=list)
    rationale: str = ""


AGENT_PROFILES: dict[str, Profile] = {
    "rag": Profile(
        agent_type="rag",
        metrics=[
            "faithfulness",
            "answer_relevancy",
            "contextual_precision",
            "contextual_recall",
            "hallucination",
        ],
        span_metrics=["faithfulness"],
        rationale="Retrieval quality and groundedness dominate failures for a RAG agent.",
    ),
    "conversational": Profile(
        agent_type="conversational",
        metrics=["answer_relevancy", "task_completion", "toxicity", "bias"],
        rationale="Relevance and safety across turns matter more than exact wording.",
    ),
    "tool_calling": Profile(
        agent_type="tool_calling",
        metrics=["tool_correctness", "argument_match", "task_completion"],
        rationale="Which tool was called, and with what arguments, is the whole job.",
    ),
    "task": Profile(
        agent_type="task",
        metrics=["task_completion", "correctness", "answer_relevancy"],
        rationale="A task agent is judged on whether the task got done.",
    ),
    "multi_agent": Profile(
        agent_type="multi_agent",
        metrics=["task_completion", "answer_relevancy"],
        span_metrics=["faithfulness", "answer_relevancy", "correctness"],
        rationale=(
            "An end-to-end score says something broke, not which sub-agent broke it, "
            "so the pack is scored per span as well as per trace."
        ),
    ),
    "unknown": Profile(
        agent_type="unknown",
        metrics=["answer_relevancy"],
        rationale="Classify the agent to get a metric pack suited to it.",
    ),
}

# Capabilities pull in extra metrics regardless of type.
CAPABILITY_METRICS: dict[str, list[str]] = {
    "retrieval": ["faithfulness", "answer_relevancy"],
    "tool_use": ["tool_correctness", "argument_match", "trace_step_efficiency"],
    "code_execution": ["task_completion"],
    "external_api": ["trace_tool_success_rate"],
}


def recommend(agent_type: str | None, capabilities: list[str] | None = None) -> dict[str, object]:
    """Resolve a metric pack for an agent, with the reasons it was chosen."""
    resolved_type = (agent_type or "unknown").strip() or "unknown"
    profile = AGENT_PROFILES.get(resolved_type, AGENT_PROFILES["unknown"])
    caps = [c for c in (capabilities or []) if c]

    metrics: list[str] = []
    reasons: dict[str, str] = {}

    def add(name: str, why: str) -> None:
        if name in METRIC_REGISTRY and name not in metrics:
            metrics.append(name)
            reasons[name] = why

    for name in BASELINE_METRICS:
        add(name, "Baseline: free, needs no reference.")
    for name in profile.metrics:
        add(name, f"Recommended for {resolved_type} agents.")
    for capability in caps:
        for name in CAPABILITY_METRICS.get(capability, []):
            add(name, f"Agent has the '{capability}' capability.")

    span_metrics = [m for m in profile.span_metrics if m in METRIC_REGISTRY]
    if "retrieval" in caps and "faithfulness" not in span_metrics:
        span_metrics.append("faithfulness")

    reference_based = [m for m in metrics if METRIC_REGISTRY[m].requires_reference]

    return {
        "agent_type": resolved_type,
        "capabilities": caps,
        "metrics": metrics,
        "span_metrics": span_metrics,
        "rationale": profile.rationale,
        "reasons": reasons,
        "reference_based": reference_based,
        "note": (
            "Metrics marked reference-based need expected_output or a reviewed "
            "reference_trajectory. Build one from production sessions if the "
            "dataset has none."
        )
        if reference_based
        else "",
    }
