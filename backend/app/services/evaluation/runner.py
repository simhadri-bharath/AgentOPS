"""Evaluation run orchestration."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories.agent_repository import AgentRepository
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.services.datasets.parser import parse_dataset_file
from app.services.evaluation.agent_invoker import AgentInvoker
from app.services.evaluation.evaluator import SampleEvaluator
from app.services.evaluation.metrics import compute_aggregates

logger = get_logger(__name__)


class EvaluationRunner:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._eval_repo = EvaluationRepository(session)
        self._agent_repo = AgentRepository(session)
        self._dataset_repo = DatasetRepository(session)
        self._invoker = AgentInvoker()
        self._evaluator = SampleEvaluator()

    async def run(self, evaluation_id: uuid.UUID) -> None:
        run = await self._eval_repo.get_run(evaluation_id)
        if not run:
            logger.error("Evaluation run not found: %s", evaluation_id)
            return

        logger.info(
            "Evaluation started",
            extra={"component": "evaluation_runner", "evaluation_id": str(evaluation_id)},
        )

        await self._eval_repo.update_run_status(run, "running", mark_started=True)
        await self._session.commit()

        try:
            agent = await self._agent_repo.get_agent(run.agent_id)
            if not agent:
                raise ValueError(f"Agent {run.agent_id} not found")

            dataset = await self._dataset_repo.get(run.dataset_id)
            if not dataset:
                raise ValueError(f"Dataset {run.dataset_id} not found")

            if not agent.endpoint_url:
                raise ValueError("Agent has no endpoint_url (reasoning engine resource)")

            validated = parse_dataset_file(dataset.file_path)
            metric_names: list[str] = list(run.metrics or [])

            # Single bulk run_inference call (notebook pattern)
            invoke_results = await self._run_batch_invoke(
                agent.endpoint_url, validated.rows
            )

            all_score_rows: list[dict[str, Any]] = []

            for idx, row in enumerate(validated.rows):
                invoke = invoke_results[idx] if idx < len(invoke_results) else None
                if invoke is None:
                    invoke_error = "No invocation result"
                    actual = ""
                    latency = None
                else:
                    invoke_error = invoke.error
                    actual = invoke.output if not invoke.error else ""
                    latency = invoke.latency_ms

                expected = row.get("expected_output")

                logger.info(
                    "Sample %s/%s latency_ms=%s has_output=%s error=%s",
                    idx + 1,
                    validated.row_count,
                    latency,
                    bool(actual),
                    invoke_error,
                    extra={
                        "component": "evaluation_runner",
                        "evaluation_id": str(evaluation_id),
                        "sample_index": idx,
                    },
                )

                scores = self._evaluator.evaluate_sample(
                    actual_output=actual,
                    expected_output=expected,
                    latency_ms=latency,
                    metric_names=metric_names,
                )
                if invoke_error:
                    scores["invocation_error"] = invoke_error

                all_score_rows.append(scores)

                await self._eval_repo.add_result(
                    evaluation_run_id=run.id,
                    sample_index=idx,
                    input_text=row["input"],
                    expected_output=expected,
                    actual_output=actual or None,
                    scores=scores,
                    latency_ms=latency,
                )
                await self._session.commit()

            aggregates = compute_aggregates(all_score_rows, metric_names)
            run_error: str | None = None
            total = aggregates.get("total_samples") or len(validated.rows)
            empty = aggregates.get("empty_responses", 0)
            if total and empty >= total:
                run_error = (
                    f"All {total} samples returned empty agent output. "
                    "This matches the reference notebook: run_inference completed but the "
                    "deployed Reasoning Engine generated no text. Check Vertex AI agent "
                    "logs for your Travel Planner (or re-deploy the agent). "
                    "Use POST /api/v1/agents/{{id}}/test-invoke to debug one prompt."
                )
            await self._eval_repo.update_run_status(
                run,
                "completed",
                aggregate_scores=aggregates,
                error_message=run_error,
                mark_completed=True,
            )
            await self._session.commit()

            logger.info(
                "Evaluation completed",
                extra={
                    "component": "evaluation_runner",
                    "evaluation_id": str(evaluation_id),
                    "aggregates": str(aggregates),
                },
            )
        except Exception as exc:
            logger.exception(
                "Evaluation failed",
                extra={"component": "evaluation_runner", "evaluation_id": str(evaluation_id)},
            )
            await self._eval_repo.update_run_status(
                run,
                "failed",
                error_message=str(exc),
                mark_completed=True,
            )
            await self._session.commit()

    async def _run_batch_invoke(
        self, resource_name: str, rows: list[dict[str, str]]
    ):
        import asyncio

        return await asyncio.to_thread(self._invoker.batch_invoke, resource_name, rows)
