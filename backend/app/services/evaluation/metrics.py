"""Simple MVP evaluation metrics."""

from dataclasses import dataclass
from typing import Any


@dataclass
class MetricInput:
    actual_output: str
    expected_output: str | None
    latency_ms: int | None = None


SUPPORTED_METRICS = frozenset(
    {
        "exact_match",
        "contains_expected",
        "response_length",
        "response_nonempty",
        "latency_ms",
    }
)

# Notebook-style: prompts only; agent output is generated, not provided in the dataset
PROMPT_ONLY_METRICS = ["response_nonempty", "response_length", "latency_ms"]


def compute_metrics(
    sample: MetricInput,
    metric_names: list[str],
) -> dict[str, Any]:
    scores: dict[str, Any] = {}
    actual = (sample.actual_output or "").strip()
    expected = (sample.expected_output or "").strip()

    for name in metric_names:
        if name not in SUPPORTED_METRICS:
            continue
        if name == "exact_match":
            scores[name] = (
                1.0
                if expected and actual.lower() == expected.lower()
                else 0.0
            )
        elif name == "contains_expected":
            if not expected:
                scores[name] = None  # no golden answer — notebook uses LLM judges instead
            else:
                scores[name] = 1.0 if expected.lower() in actual.lower() else 0.0
        elif name == "response_length":
            scores[name] = len(actual)
        elif name == "response_nonempty":
            scores[name] = 1.0 if actual else 0.0
        elif name == "latency_ms":
            scores[name] = sample.latency_ms

    scores["actual_output_nonempty"] = bool(actual)
    return scores


def compute_aggregates(
    all_scores: list[dict[str, Any]],
    metric_names: list[str],
) -> dict[str, Any]:
    aggregates: dict[str, Any] = {}
    passed = 0
    failed = 0

    empty_responses = 0
    for scores in all_scores:
        em = scores.get("exact_match")
        ce = scores.get("contains_expected")
        nonempty = scores.get("actual_output_nonempty", False)
        if not nonempty:
            empty_responses += 1
        sample_pass = False
        rn = scores.get("response_nonempty")
        if em == 1.0 or ce == 1.0:
            sample_pass = True
        elif rn == 1.0:
            sample_pass = True
        elif em is None and ce is None and nonempty:
            sample_pass = True
        if sample_pass:
            passed += 1
        else:
            failed += 1

    aggregates["empty_responses"] = empty_responses

    aggregates["total_passed"] = passed
    aggregates["total_failed"] = failed
    aggregates["total_samples"] = len(all_scores)

    for name in metric_names:
        if name == "response_length":
            values = [s[name] for s in all_scores if name in s and isinstance(s[name], (int, float))]
            aggregates[f"avg_{name}"] = sum(values) / len(values) if values else 0
        elif name == "latency_ms":
            values = [s[name] for s in all_scores if name in s and s[name] is not None]
            aggregates[f"avg_{name}"] = sum(values) / len(values) if values else 0
        elif name in ("exact_match", "contains_expected", "response_nonempty"):
            values = [s[name] for s in all_scores if name in s and s[name] is not None]
            aggregates[f"avg_{name}"] = sum(values) / len(values) if values else 0

    return aggregates
