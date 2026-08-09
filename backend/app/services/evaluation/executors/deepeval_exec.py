"""DeepEval metric execution.

Consumes EvaluationCase only -- no Google types cross this boundary.

Runs at two levels per sample: the whole trace, and one case per sub-agent span.
Component-level scoring is what turns "the agent scored 0.6" into "research_agent
scored 0.4 and formatter_agent scored 0.9".

DeepEval documents component-level evaluation via @observe / update_current_span,
which requires decorating the application. The agent here is a pickle deployed
inside Agent Engine, so spans are reconstructed externally from session events
and passed as ordinary test cases instead.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.evaluation.judge import JudgeUnavailableError, get_judge
from app.services.evaluation.metric_registry import MetricSpec
from app.services.evaluation.trace_model import EvaluationCase, Span, SpanKind

logger = get_logger(__name__)

# Metrics whose raw score means "how much of the bad thing", so a high raw score
# is a bad result. Inverted on the way out so every stored score reads
# higher-is-better and aggregates without special cases.
_INVERTED = {"hallucination", "toxicity", "bias"}


@dataclass
class MetricOutcome:
    scores: dict[str, float] = field(default_factory=dict)
    explanations: dict[str, str] = field(default_factory=dict)
    unavailable: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    span_scores: list[dict[str, Any]] = field(default_factory=list)
    judge_failed: bool = False


def _build_metric(spec: MetricSpec, judge: Any) -> Any | None:
    """Instantiate the DeepEval metric for a spec, or None if unsupported."""
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        BiasMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
        GEval,
        HallucinationMetric,
        TaskCompletionMetric,
        ToolCorrectnessMetric,
        ToxicityMetric,
    )
    from deepeval.test_case import LLMTestCaseParams

    common = {"model": judge, "async_mode": False, "verbose_mode": False}

    if spec.name == "answer_relevancy":
        return AnswerRelevancyMetric(**common)
    if spec.name == "faithfulness":
        return FaithfulnessMetric(**common)
    if spec.name == "contextual_precision":
        return ContextualPrecisionMetric(**common)
    if spec.name == "contextual_recall":
        return ContextualRecallMetric(**common)
    if spec.name == "hallucination":
        return HallucinationMetric(**common)
    if spec.name == "toxicity":
        return ToxicityMetric(**common)
    if spec.name == "bias":
        return BiasMetric(**common)
    if spec.name == "task_completion":
        return TaskCompletionMetric(**common)
    if spec.name == "tool_correctness":
        # Ordering matters, and so do the arguments: the same tool called with
        # the wrong query is not a correct tool call. The model is passed
        # explicitly because the metric otherwise falls back to OpenAI when it
        # needs to explain itself, which this deployment has no key for.
        try:
            from deepeval.test_case import ToolCallParams

            return ToolCorrectnessMetric(
                model=judge,
                should_consider_ordering=True,
                evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
            )
        except Exception:
            return ToolCorrectnessMetric(model=judge, should_consider_ordering=True)
    if spec.name == "correctness":
        return GEval(
            name="Correctness",
            criteria=(
                "Determine whether the actual output is factually consistent with "
                "the expected output. Penalise contradictions heavily; do not "
                "penalise extra detail that is consistent."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            **common,
        )
    return None


def _llm_test_case(case: EvaluationCase) -> Any:
    from deepeval.test_case import LLMTestCase, ToolCall as DeepEvalToolCall

    tools_called = [
        DeepEvalToolCall(name=call.name, input_parameters=dict(call.args or {}))
        for call in case.predicted_trajectory
    ]
    expected_tools = [
        DeepEvalToolCall(name=call.name, input_parameters=dict(call.args or {}))
        for call in case.reference_trajectory
    ]
    return LLMTestCase(
        input=case.input,
        actual_output=case.actual_output,
        expected_output=case.expected_output or None,
        retrieval_context=list(case.retrieval_context) or None,
        # HallucinationMetric checks against `context`, not `retrieval_context`.
        context=list(case.retrieval_context) or None,
        tools_called=tools_called or None,
        expected_tools=expected_tools or None,
    )


def _span_case(case: EvaluationCase, span: Span) -> EvaluationCase:
    """One sub-agent's slice of the turn, as a scoreable case in its own right."""
    return EvaluationCase(
        input=span.input or case.input,
        actual_output=span.output,
        expected_output=case.expected_output,
        retrieval_context=[doc.text for doc in span.retrieval_context],
        predicted_trajectory=list(case.predicted_trajectory),
        reference_trajectory=list(case.reference_trajectory),
        sample_index=case.sample_index,
        metadata={"span_id": span.span_id, "author": span.author},
    )


def _score_one(metric: Any, spec: MetricSpec, test_case: Any) -> tuple[float, str]:
    metric.measure(test_case)
    raw = float(metric.score if metric.score is not None else 0.0)
    score = 1.0 - raw if spec.name in _INVERTED else raw
    return round(max(0.0, min(1.0, score)), 4), (metric.reason or "")


def _run_sync(specs: list[MetricSpec], case: EvaluationCase, judge: Any) -> MetricOutcome:
    outcome = MetricOutcome()
    present = case.available_fields()

    trace_case = _llm_test_case(case)
    for spec in specs:
        reason = spec.unavailable_reason(present)
        if reason:
            # Reported, not silently omitted -- "unavailable and why" is a
            # different answer from "scored zero".
            outcome.unavailable[spec.name] = reason
            continue
        try:
            metric = _build_metric(spec, judge)
            if metric is None:
                outcome.unavailable[spec.name] = "No DeepEval implementation wired."
                continue
            score, explanation = _score_one(metric, spec, trace_case)
            outcome.scores[spec.name] = score
            if explanation:
                outcome.explanations[spec.name] = explanation
        except Exception as exc:
            # A judge failure is not an agent failure and must not be reported
            # as one.
            outcome.errors[spec.name] = f"{type(exc).__name__}: {exc}"[:400]
            outcome.judge_failed = True
            logger.warning(
                "Judge failed for %s: %s",
                spec.name,
                exc,
                extra={"component": "deepeval_exec"},
            )

    span_specs = [s for s in specs if s.supports_span]
    if span_specs and case.spans:
        for span in case.spans:
            if span.kind is not SpanKind.AGENT or not span.output.strip():
                continue
            sub_case = _span_case(case, span)
            sub_present = sub_case.available_fields()
            sub_test_case = _llm_test_case(sub_case)
            entry: dict[str, Any] = {
                "span_id": span.span_id,
                "author": span.author,
                "kind": span.kind.value,
                "scores": {},
                "explanations": {},
            }
            for spec in span_specs:
                if spec.unavailable_reason(sub_present):
                    continue
                try:
                    metric = _build_metric(spec, judge)
                    if metric is None:
                        continue
                    score, explanation = _score_one(metric, spec, sub_test_case)
                    entry["scores"][spec.name] = score
                    if explanation:
                        entry["explanations"][spec.name] = explanation
                except Exception as exc:
                    entry.setdefault("errors", {})[spec.name] = str(exc)[:200]
                    outcome.judge_failed = True
            if entry["scores"]:
                outcome.span_scores.append(entry)

    return outcome


async def run_deepeval(
    specs: list[MetricSpec],
    case: EvaluationCase,
    *,
    judge: Any | None = None,
) -> MetricOutcome:
    """Score one case. Blocking DeepEval work runs off the event loop."""
    if not specs:
        return MetricOutcome()
    try:
        judge = judge or get_judge()
    except JudgeUnavailableError as exc:
        return MetricOutcome(
            errors={spec.name: str(exc) for spec in specs}, judge_failed=True
        )
    return await asyncio.to_thread(_run_sync, specs, case, judge)


async def run_deepeval_batch(
    specs: list[MetricSpec],
    cases: list[EvaluationCase],
    *,
    concurrency: int | None = None,
) -> list[MetricOutcome]:
    """Score many cases concurrently, bounded so the judge is not overloaded."""
    if not specs or not cases:
        return [MetricOutcome() for _ in cases]

    try:
        judge = get_judge()
    except JudgeUnavailableError as exc:
        return [
            MetricOutcome(errors={s.name: str(exc) for s in specs}, judge_failed=True)
            for _ in cases
        ]

    limit = concurrency or get_settings().judge_concurrency
    semaphore = asyncio.Semaphore(limit)

    async def run(case: EvaluationCase) -> MetricOutcome:
        async with semaphore:
            return await run_deepeval(specs, case, judge=judge)

    return list(await asyncio.gather(*(run(c) for c in cases)))
