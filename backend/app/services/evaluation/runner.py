"""Evaluation orchestration.

load -> invoke -> normalize -> build cases -> group metrics by executor ->
gather -> aggregate -> persist.

Replaces a 451-line method that inlined imports, two metric dictionaries, a
nested field-extraction closure, DataFrame assembly, two SDK code paths and the
database writes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories.agent_repository import AgentRepository
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.services.datasets.parser import parse_dataset_file
from app.services.evaluation.executors.deepeval_exec import (
    MetricOutcome,
    run_deepeval_batch,
)
from app.services.evaluation.executors.deterministic import (
    run_deterministic,
    run_trace_health,
)
from app.services.evaluation.judge import (
    estimate_cost_usd,
    framework_versions,
    judge_info,
)
from app.services.evaluation.metric_registry import (
    DEEPEVAL,
    DETERMINISTIC,
    METRIC_CONFIG_VERSION,
    TRACE_HEALTH,
    group_by_executor,
    validate_metrics,
)
from app.services.evaluation.trace_model import (
    EvaluationCase,
    InvocationState,
    ToolCall,
)
from app.services.gcp.agent_engine_client import (
    INVOCATION_CLASS_METHOD,
    INVOCATION_ENDPOINT,
)
from app.services.evaluation import registry
from app.services.invokers.agent_engine import AgentEngineInvoker, InvokeOutcome

logger = get_logger(__name__)


def _tool_calls(raw: Any) -> list[ToolCall]:
    """Parse a dataset's reference_trajectory column into tool calls."""
    if not raw:
        return []
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []

    calls: list[ToolCall] = []
    for entry in raw:
        if isinstance(entry, str):
            calls.append(ToolCall(name=entry))
        elif isinstance(entry, dict):
            name = entry.get("name") or entry.get("tool") or entry.get("tool_name")
            if name:
                calls.append(
                    ToolCall(
                        name=str(name),
                        args=dict(entry.get("args") or entry.get("input_parameters") or {}),
                    )
                )
    return calls


def _retrieval_from_row(row: dict[str, Any]) -> list[str]:
    value = row.get("retrieval_context")
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    context = row.get("context")
    return [context.strip()] if isinstance(context, str) and context.strip() else []


def build_case(
    index: int, row: dict[str, Any], outcome: InvokeOutcome
) -> EvaluationCase:
    """Fuse a dataset row with what the agent actually did."""
    trace = outcome.trace
    # Retrieval context from the live trace wins: it is what the agent really
    # had in front of it, not what a dataset author guessed it would fetch.
    retrieval = (
        [doc.text for doc in trace.retrieval_context]
        if trace and trace.retrieval_context
        else _retrieval_from_row(row)
    )
    return EvaluationCase(
        input=row.get("input", ""),
        actual_output=outcome.output,
        expected_output=(row.get("expected_output") or row.get("reference") or "") or None,
        retrieval_context=retrieval,
        predicted_trajectory=list(trace.trajectory) if trace else [],
        reference_trajectory=_tool_calls(row.get("reference_trajectory")),
        conversation=list(row.get("conversation") or []),
        spans=list(trace.spans) if trace else [],
        trace=trace,
        sample_index=index,
        state=outcome.state,
        error=outcome.error,
        latency_ms=outcome.latency_ms,
        metadata={"category": row.get("category") or "uncategorized"},
    )


def aggregate(
    cases: list[EvaluationCase], per_sample_scores: list[dict[str, float]]
) -> dict[str, Any]:
    """Averages per metric, plus the counts that make a run readable."""
    totals: dict[str, list[float]] = {}
    for scores in per_sample_scores:
        for name, value in scores.items():
            totals.setdefault(name, []).append(value)

    aggregates: dict[str, Any] = {
        f"avg_{name}": round(sum(values) / len(values), 4)
        for name, values in totals.items()
        if values
    }
    aggregates["metric_coverage"] = {
        name: len(values) for name, values in totals.items()
    }

    latencies = [c.latency_ms for c in cases if c.latency_ms]
    if latencies:
        ordered = sorted(latencies)
        aggregates["avg_latency_ms"] = int(sum(ordered) / len(ordered))
        aggregates["p50_latency_ms"] = ordered[len(ordered) // 2]
        aggregates["p95_latency_ms"] = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]

    succeeded = [c for c in cases if c.state is InvocationState.SUCCESS]
    aggregates["total_samples"] = len(cases)
    aggregates["total_invoked"] = len(succeeded)
    aggregates["total_failed"] = len(cases) - len(succeeded)
    aggregates["empty_responses"] = sum(1 for c in cases if not c.actual_output.strip())

    # "Passed" needs a threshold, so it only means something when a judged
    # metric ran. Anything else would be the old rule where any non-empty
    # response counted as a pass.
    judged = [name for name in totals if name.startswith("avg_") is False]
    scored_samples = [
        scores for scores in per_sample_scores if scores
    ]
    if scored_samples:
        settings = get_settings()
        threshold = settings.metric_pass_threshold
        passed = sum(
            1
            for scores in scored_samples
            if scores and (sum(scores.values()) / len(scores)) >= threshold
        )
        aggregates["total_passed"] = passed
        aggregates["total_scored"] = len(scored_samples)
        aggregates["pass_threshold"] = threshold
    aggregates["states"] = _state_counts(cases)
    return aggregates


def _state_counts(cases: list[EvaluationCase]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        key = case.state.value
        counts[key] = counts.get(key, 0) + 1
    return counts


class EvaluationRunner:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._eval_repo = EvaluationRepository(session)
        self._agent_repo = AgentRepository(session)
        self._dataset_repo = DatasetRepository(session)

    async def run(self, evaluation_id: uuid.UUID) -> None:
        run = await self._eval_repo.get_run(evaluation_id)
        if not run:
            logger.error("Evaluation run not found: %s", evaluation_id)
            return

        log_extra = {"component": "evaluation_runner", "evaluation_id": str(evaluation_id)}
        await self._eval_repo.update_run_status(run, "running", mark_started=True)
        await self._session.commit()

        try:
            agent, dataset, rows, metrics = await self._load(run)
            snapshot = self._snapshot(agent, dataset, metrics)
            await self._eval_repo.update_run_status(run, "running", run_config=snapshot)
            await self._session.commit()

            logger.info(
                "Invoking agent for %s samples with metrics %s",
                len(rows),
                metrics,
                extra=log_extra,
            )
            invoker = AgentEngineInvoker(
                tool_overrides=(agent.invocation_config or {}).get("tool_overrides")
            )
            # Registered so POST /{id}/cancel can reach this instance; the
            # invoker could always be cancelled, but nothing held the handle.
            registry.register(evaluation_id, invoker)
            try:
                outcomes = await invoker.batch_invoke(agent.endpoint_url, rows)
            finally:
                registry.unregister(evaluation_id)
            cases = [build_case(i, row, out) for i, (row, out) in enumerate(zip(rows, outcomes))]

            if invoker.cancelled:
                await self._persist(run, cases, [MetricOutcome() for _ in cases])
                await self._eval_repo.update_run_status(
                    run,
                    "cancelled",
                    error_message="Cancelled before completion.",
                    aggregate_scores=aggregate(cases, []),
                    run_config=snapshot,
                    mark_completed=True,
                )
                await self._session.commit()
                logger.info("Evaluation cancelled", extra=log_extra)
                return

            per_sample = await self._score(metrics, cases)

            usage = self._usage(cases, per_sample)
            aggregates = aggregate(cases, [s.scores for s in per_sample])
            await self._persist(run, cases, per_sample)

            # A run where nothing was successfully invoked is not a completed
            # evaluation -- it is an outage. Reporting it as completed would let
            # the dashboard count an unreachable agent as a healthy run.
            status, failure = self._terminal_status(cases)
            await self._eval_repo.update_run_status(
                run,
                status,
                error_message=failure,
                aggregate_scores=aggregates,
                usage=usage,
                mark_completed=True,
            )
            await self._session.commit()
            logger.info(
                "Evaluation %s", status, extra={**log_extra, "states": aggregates.get("states")}
            )

        except Exception as exc:
            logger.exception("Evaluation failed", extra=log_extra)
            await self._session.rollback()
            fresh = await self._eval_repo.get_run(evaluation_id)
            if fresh:
                await self._eval_repo.update_run_status(
                    fresh, "failed", error_message=str(exc)[:2000], mark_completed=True
                )
                await self._session.commit()

    # -- steps ----------------------------------------------------------

    @staticmethod
    def _terminal_status(cases: list[EvaluationCase]) -> tuple[str, str | None]:
        """completed, or failed when no sample was actually invoked.

        Partial failure still completes -- the scored samples are real results.
        Total failure does not, and the message names the dominant cause, so an
        unreachable agent is not counted as a healthy run with empty scores.
        """
        if not cases:
            return "failed", "Dataset produced no samples."
        if any(c.state is InvocationState.SUCCESS for c in cases):
            return "completed", None

        counts: dict[str, int] = {}
        for case in cases:
            counts[case.state.value] = counts.get(case.state.value, 0) + 1
        dominant = max(counts, key=lambda k: counts[k])
        detail = next(
            (c.error for c in cases if c.state.value == dominant and c.error), ""
        )
        summary = f"No sample was invoked successfully ({dominant} x{counts[dominant]})."
        return "failed", f"{summary} {detail}".strip()[:2000]

    async def _load(self, run: Any) -> tuple[Any, Any, list[dict[str, Any]], list[str]]:
        agent = await self._agent_repo.get_agent(run.agent_id)
        if not agent:
            raise ValueError(f"Agent {run.agent_id} not found")
        if not agent.endpoint_url:
            raise ValueError("Agent has no endpoint_url (reasoning engine resource)")

        dataset = await self._dataset_repo.get(run.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {run.dataset_id} not found")

        validated = parse_dataset_file(dataset.file_path)
        metrics = validate_metrics(run.metrics or [])
        if not metrics:
            raise ValueError("No metrics selected for this evaluation")
        return agent, dataset, validated.rows, metrics

    def _snapshot(self, agent: Any, dataset: Any, metrics: list[str]) -> dict[str, Any]:
        """Everything needed to interpret this run's numbers later."""
        settings = get_settings()
        return {
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
            "agent_engine_id": (agent.extra_metadata or {}).get("gcp_engine_id"),
            "agent_resource_name": agent.endpoint_url,
            "agent_type": agent.agent_type,
            "agent_capabilities": list(agent.capabilities or []),
            "environment": agent.environment,
            "dataset_id": str(dataset.id),
            "dataset_version": dataset.version,
            "dataset_source": dataset.source,
            "dataset_review_status": dataset.review_status,
            "metrics": metrics,
            "metric_config_version": METRIC_CONFIG_VERSION,
            "invocation_interface": f"{INVOCATION_ENDPOINT}/{INVOCATION_CLASS_METHOD}",
            "invoke_concurrency": settings.invoke_concurrency,
            "framework_versions": framework_versions(),
            **judge_info(),
        }

    async def _score(
        self, metrics: list[str], cases: list[EvaluationCase]
    ) -> list[MetricOutcome]:
        grouped = group_by_executor(metrics)
        outcomes = [MetricOutcome() for _ in cases]

        for index, case in enumerate(cases):
            if case.state is not InvocationState.SUCCESS:
                # Scoring a failed invocation would report an agent outage as
                # poor answer quality.
                outcomes[index].unavailable = {
                    name: f"Invocation did not succeed ({case.state.value})."
                    for name in metrics
                }
                continue
            outcomes[index].scores.update(
                run_deterministic(grouped.get(DETERMINISTIC, []), case)
            )
            outcomes[index].scores.update(
                run_trace_health(grouped.get(TRACE_HEALTH, []), case)
            )
            for spec in grouped.get(DETERMINISTIC, []):
                reason = spec.unavailable_reason(case.available_fields())
                if reason:
                    outcomes[index].unavailable[spec.name] = reason

        deepeval_specs = grouped.get(DEEPEVAL, [])
        if deepeval_specs:
            scoreable = [
                (i, c) for i, c in enumerate(cases) if c.state is InvocationState.SUCCESS
            ]
            if scoreable:
                judged = await run_deepeval_batch(
                    deepeval_specs, [c for _, c in scoreable]
                )
                for (index, _), result in zip(scoreable, judged):
                    outcomes[index].scores.update(result.scores)
                    outcomes[index].explanations.update(result.explanations)
                    outcomes[index].unavailable.update(result.unavailable)
                    outcomes[index].errors.update(result.errors)
                    outcomes[index].span_scores.extend(result.span_scores)
                    outcomes[index].judge_failed |= result.judge_failed
        return outcomes

    def _usage(
        self, cases: list[EvaluationCase], outcomes: list[MetricOutcome]
    ) -> dict[str, Any]:
        tokens_in = sum(c.trace.tokens_in for c in cases if c.trace)
        tokens_out = sum(c.trace.tokens_out for c in cases if c.trace)
        tool_calls = sum(c.trace.tool_calls for c in cases if c.trace)
        llm_calls = sum(c.trace.llm_calls for c in cases if c.trace)
        judged_metrics = sum(len(o.scores) for o in outcomes)
        span_judgements = sum(len(o.span_scores) for o in outcomes)
        return {
            "agent_tokens_in": tokens_in,
            "agent_tokens_out": tokens_out,
            "agent_tool_calls": tool_calls,
            "agent_llm_calls": llm_calls,
            "judge_metric_evaluations": judged_metrics,
            "judge_span_evaluations": span_judgements,
            # Estimated, not billing-accurate. Per-span scoring multiplies judge
            # calls, so the number needs to be visible rather than discovered.
            "agent_cost_usd_estimate": estimate_cost_usd(tokens_in, tokens_out),
            "judge_failures": sum(1 for o in outcomes if o.judge_failed),
        }

    async def _persist(
        self,
        run: Any,
        cases: list[EvaluationCase],
        outcomes: list[MetricOutcome],
    ) -> None:
        for case, outcome in zip(cases, outcomes):
            state = case.state
            if state is InvocationState.SUCCESS and outcome.judge_failed and not outcome.scores:
                # The agent answered; the judge is what broke.
                state = InvocationState.JUDGE_ERROR
            await self._eval_repo.add_result(
                evaluation_run_id=run.id,
                sample_index=case.sample_index,
                input_text=case.input,
                expected_output=case.expected_output,
                actual_output=case.actual_output,
                scores=outcome.scores,
                latency_ms=case.latency_ms,
                metric_explanations=outcome.explanations,
                metric_unavailable=outcome.unavailable,
                metric_errors=outcome.errors,
                span_scores=outcome.span_scores,
                trace=case.trace.to_dict() if case.trace else {},
                state=state.value,
                error_message=case.error,
                tokens_in=case.trace.tokens_in if case.trace else 0,
                tokens_out=case.trace.tokens_out if case.trace else 0,
            )
