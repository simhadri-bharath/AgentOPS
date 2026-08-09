"""Deterministic metrics: no LLM, no cost, exactly reproducible."""

from __future__ import annotations

from app.services.evaluation.metric_registry import MetricSpec
from app.services.evaluation.trace_health import compute_trace_health
from app.services.evaluation.trace_model import EvaluationCase, ToolCall


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def exact_match(case: EvaluationCase) -> float:
    return 1.0 if _norm(case.actual_output) == _norm(case.expected_output) else 0.0


def contains_expected(case: EvaluationCase) -> float:
    expected = _norm(case.expected_output)
    return 1.0 if expected and expected in _norm(case.actual_output) else 0.0


def response_nonempty(case: EvaluationCase) -> float:
    return 1.0 if case.actual_output.strip() else 0.0


def _names(calls: list[ToolCall]) -> list[str]:
    return [c.name for c in calls]


def trajectory_in_order_match(case: EvaluationCase) -> float:
    """Reference calls appear in order, extra calls allowed between them."""
    reference = _names(case.reference_trajectory)
    if not reference:
        return 0.0
    predicted = _names(case.predicted_trajectory)
    index = 0
    for name in predicted:
        if index < len(reference) and name == reference[index]:
            index += 1
    return 1.0 if index == len(reference) else 0.0


def trajectory_any_order_match(case: EvaluationCase) -> float:
    reference = set(_names(case.reference_trajectory))
    if not reference:
        return 0.0
    return 1.0 if reference == set(_names(case.predicted_trajectory)) else 0.0


def trajectory_precision(case: EvaluationCase) -> float:
    predicted = _names(case.predicted_trajectory)
    if not predicted:
        return 0.0
    reference = set(_names(case.reference_trajectory))
    return sum(1 for n in predicted if n in reference) / len(predicted)


def trajectory_recall(case: EvaluationCase) -> float:
    reference = _names(case.reference_trajectory)
    if not reference:
        return 0.0
    predicted = set(_names(case.predicted_trajectory))
    return sum(1 for n in reference if n in predicted) / len(reference)


def argument_match(case: EvaluationCase) -> float:
    """Fraction of expected (tool, key, value) triples the agent got right.

    Tool-name-only trajectory metrics cannot tell a good search from a bad one:
    for a retrieval agent the query it chose carries most of the quality signal.
    """
    expected_triples: list[tuple[str, str, str]] = []
    for call in case.reference_trajectory:
        for key, value in (call.args or {}).items():
            expected_triples.append((call.name, key, _stringify(value)))
    if not expected_triples:
        return 0.0

    actual: set[tuple[str, str, str]] = set()
    for call in case.predicted_trajectory:
        for key, value in (call.args or {}).items():
            actual.add((call.name, key, _stringify(value)))

    matched = sum(1 for triple in expected_triples if triple in actual)
    return matched / len(expected_triples)


def _stringify(value: object) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, (list, tuple)):
        return ",".join(sorted(_stringify(v) for v in value))
    return str(value).strip().lower()


_FUNCTIONS = {
    "exact_match": exact_match,
    "contains_expected": contains_expected,
    "response_nonempty": response_nonempty,
    "argument_match": argument_match,
    "trajectory_in_order_match": trajectory_in_order_match,
    "trajectory_any_order_match": trajectory_any_order_match,
    "trajectory_precision": trajectory_precision,
    "trajectory_recall": trajectory_recall,
}


def run_deterministic(specs: list[MetricSpec], case: EvaluationCase) -> dict[str, float]:
    scores: dict[str, float] = {}
    present = case.available_fields()
    for spec in specs:
        if spec.unavailable_reason(present):
            continue
        function = _FUNCTIONS.get(spec.name)
        if function is not None:
            scores[spec.name] = round(float(function(case)), 4)
    return scores


def run_trace_health(specs: list[MetricSpec], case: EvaluationCase) -> dict[str, float]:
    if case.trace is None:
        return {}
    all_scores = compute_trace_health(case.trace)
    return {spec.name: all_scores[spec.name] for spec in specs if spec.name in all_scores}
