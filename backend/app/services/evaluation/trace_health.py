"""Deterministic trace-quality checks.

No LLM, no reference trajectory, no dataset work -- these run on every sample
and already have something to find: the live chat agent calls search_documents
twice inside a single invocation.

All scores are 0..1 where higher is better, so they aggregate the same way as
judged metrics.
"""

from __future__ import annotations

from app.services.evaluation.trace_model import SpanKind, Trace

# Beyond this, a repeated identical call is a loop rather than a refinement.
_LOOP_THRESHOLD = 3


def tool_error_rate(trace: Trace) -> float:
    """Share of tool calls that returned cleanly."""
    if not trace.trajectory:
        return 1.0
    failed = sum(1 for call in trace.trajectory if call.error)
    return 1.0 - (failed / len(trace.trajectory))


def duplicate_tool_calls(trace: Trace) -> int:
    """Identical (name, args) pairs beyond the first within one turn."""
    seen: dict[tuple[str, str], int] = {}
    for call in trace.trajectory:
        signature = call.signature()
        seen[signature] = seen.get(signature, 0) + 1
    return sum(count - 1 for count in seen.values() if count > 1)


def redundancy_score(trace: Trace) -> float:
    """1.0 when every tool call was distinct."""
    if not trace.trajectory:
        return 1.0
    return 1.0 - (duplicate_tool_calls(trace) / len(trace.trajectory))


def has_loop(trace: Trace) -> bool:
    counts: dict[tuple[str, str], int] = {}
    for call in trace.trajectory:
        signature = call.signature()
        counts[signature] = counts.get(signature, 0) + 1
        if counts[signature] >= _LOOP_THRESHOLD:
            return True
    return False


def step_count(trace: Trace) -> int:
    return len(trace.trajectory) + sum(
        1 for span in trace.spans if span.kind is SpanKind.AGENT
    )


def step_efficiency(trace: Trace, minimum_steps: int = 2) -> float:
    """How close the turn came to the minimum plausible number of steps.

    Default minimum is one agent turn plus one answer. Reference-free, so it is
    a smell detector rather than a verdict.
    """
    steps = step_count(trace)
    if steps <= minimum_steps:
        return 1.0
    return max(0.0, minimum_steps / steps)


def answered(trace: Trace) -> float:
    return 1.0 if trace.output.strip() else 0.0


def compute_trace_health(trace: Trace) -> dict[str, float]:
    """All checks, keyed by metric name as used in the registry."""
    return {
        "trace_tool_success_rate": round(tool_error_rate(trace), 4),
        "trace_no_redundant_calls": round(redundancy_score(trace), 4),
        "trace_no_loop": 0.0 if has_loop(trace) else 1.0,
        "trace_step_efficiency": round(step_efficiency(trace), 4),
        "trace_answered": answered(trace),
    }


def trace_health_details(trace: Trace) -> dict[str, object]:
    """Human-readable backing for the scores above."""
    duplicates = duplicate_tool_calls(trace)
    return {
        "tool_calls": len(trace.trajectory),
        "failed_tool_calls": sum(1 for call in trace.trajectory if call.error),
        "duplicate_tool_calls": duplicates,
        "duplicate_detail": [
            f"{name} x{count}"
            for (name, _args), count in _signature_counts(trace).items()
            if count > 1
        ],
        "steps": step_count(trace),
        "agent_path": list(trace.agent_path),
        "looped": has_loop(trace),
    }


def _signature_counts(trace: Trace) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for call in trace.trajectory:
        signature = call.signature()
        counts[signature] = counts.get(signature, 0) + 1
    return counts
