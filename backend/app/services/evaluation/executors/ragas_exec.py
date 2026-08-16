"""RAGAS metric executor.

RAGAS was previously offered in the UI while being uninstalled with zero code
behind it -- every RAGAS metric name resolved to a string comparison. It was
removed rather than left as a lie. This is the real implementation.

Metric names are prefixed `ragas_` so a RAGAS score is never silently confused
with the DeepEval metric of the same concept. They measure similar things by
different methods, and averaging them together would hide that.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.evaluation.metric_registry import MetricSpec
from app.services.evaluation.ragas_llm import (
    RagasUnavailable,
    build_ragas_embeddings,
    build_ragas_llm,
    check_ragas_available,
)
from app.services.evaluation.trace_model import EvaluationCase

logger = get_logger(__name__)

RAGAS = "ragas"


class _MetricRunner:
    """Builds RAGAS metrics lazily and scores one case at a time.

    Lazy because constructing a metric creates a judge client, and a run that
    selected no RAGAS metrics should not pay for one.
    """

    def __init__(self, model: str | None = None) -> None:
        self._model = model
        self._llm: Any = None
        self._embeddings: Any = None
        self._cache: dict[str, Any] = {}

    def _get_llm(self) -> Any:
        if self._llm is None:
            self._llm = build_ragas_llm(self._model)
        return self._llm

    def _get_embeddings(self) -> Any:
        if self._embeddings is None:
            self._embeddings = build_ragas_embeddings()
        return self._embeddings

    def metric(self, name: str) -> Any:
        if name in self._cache:
            return self._cache[name]
        import ragas.metrics.collections as collections

        if name == "ragas_faithfulness":
            built = collections.Faithfulness(llm=self._get_llm())
        elif name == "ragas_context_precision":
            # Without-reference variant: it judges the retrieved context against
            # the answer, so it works on datasets that have no expected output.
            built = collections.ContextPrecisionWithoutReference(llm=self._get_llm())
        elif name == "ragas_context_recall":
            built = collections.ContextRecall(llm=self._get_llm())
        elif name == "ragas_answer_relevancy":
            built = collections.AnswerRelevancy(
                llm=self._get_llm(), embeddings=self._get_embeddings()
            )
        elif name == "ragas_response_groundedness":
            built = collections.ResponseGroundedness(llm=self._get_llm())
        else:
            raise ValueError(f"No RAGAS implementation for metric '{name}'")

        self._cache[name] = built
        return built

    async def score(self, name: str, case: EvaluationCase) -> float:
        metric = self.metric(name)
        contexts = list(case.retrieval_context)

        if name == "ragas_faithfulness":
            result = await metric.ascore(
                user_input=case.input,
                response=case.actual_output,
                retrieved_contexts=contexts,
            )
        elif name == "ragas_context_precision":
            result = await metric.ascore(
                user_input=case.input,
                response=case.actual_output,
                retrieved_contexts=contexts,
            )
        elif name == "ragas_context_recall":
            result = await metric.ascore(
                user_input=case.input,
                retrieved_contexts=contexts,
                reference=case.expected_output or "",
            )
        elif name == "ragas_answer_relevancy":
            result = await metric.ascore(
                user_input=case.input, response=case.actual_output
            )
        elif name == "ragas_response_groundedness":
            result = await metric.ascore(
                response=case.actual_output, retrieved_contexts=contexts
            )
        else:
            raise ValueError(f"No RAGAS implementation for metric '{name}'")

        return float(getattr(result, "value", result))


async def run_ragas(
    specs: list[MetricSpec],
    case: EvaluationCase,
    model: str | None = None,
    runner: _MetricRunner | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    """Score a case with the selected RAGAS metrics.

    Returns (scores, errors). A metric that fails is reported by name rather
    than scored as zero -- a judge failure and a bad answer are different
    findings.
    """
    if not specs:
        return {}, {}

    ok, error = check_ragas_available()
    if not ok:
        return {}, {spec.name: error or "ragas unavailable" for spec in specs}

    runner = runner or _MetricRunner(model)
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.judge_concurrency)

    async def one(spec: MetricSpec) -> tuple[str, float | None, str | None]:
        async with semaphore:
            try:
                return spec.name, await runner.score(spec.name, case), None
            except RagasUnavailable as exc:
                return spec.name, None, str(exc)
            except Exception as exc:
                logger.warning(
                    "RAGAS metric %s failed: %s",
                    spec.name,
                    exc,
                    extra={"component": "ragas_exec"},
                )
                return spec.name, None, f"{type(exc).__name__}: {exc}"

    results = await asyncio.gather(*(one(spec) for spec in specs))

    scores: dict[str, float] = {}
    errors: dict[str, str] = {}
    for name, value, err in results:
        if err is not None:
            errors[name] = err
        elif value is not None:
            scores[name] = round(value, 4)
    return scores, errors
