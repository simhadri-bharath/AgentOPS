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

           # ── Vertex AI metric groups ───────────────────────────────────────
            TRAJECTORY_METRICS = {
                "trajectory_exact_match",
                "trajectory_in_order_match",
                "trajectory_any_order_match",
                "trajectory_precision",
                "trajectory_recall",
                "agent_trajectory_exact_match",
                "agent_trajectory_in_order_match",
                "agent_trajectory_any_order_match",
                "agent_trajectory_precision",
                "agent_trajectory_recall",
            }

            # Map your UI metric names → EvalTask string literals
            TRAJECTORY_METRIC_MAP: dict[str, str] = {
                "trajectory_exact_match":          "trajectory_exact_match",
                "trajectory_in_order_match":       "trajectory_in_order_match",
                "trajectory_any_order_match":      "trajectory_any_order_match",
                "trajectory_precision":            "trajectory_precision",
                "trajectory_recall":               "trajectory_recall",
                "agent_trajectory_exact_match":    "trajectory_exact_match",
                "agent_trajectory_in_order_match": "trajectory_in_order_match",
                "agent_trajectory_any_order_match":"trajectory_any_order_match",
                "agent_trajectory_precision":      "trajectory_precision",
                "agent_trajectory_recall":         "trajectory_recall",
            }

            # Managed metrics — handled via vertexai.Client + EvalCase (pre-computed responses)
            MANAGED_METRICS = {
                "final_response_quality",
                "hallucination",
                "tool_use_quality",
                "safety",
                "final_response_match",
                "final_response_ref_free",
                "agent_multi_turn_task_success",
                "agent_multi_turn_tool_use_quality",
                "agent_multi_turn_trajectory_quality",
            }

           # Maps UI metric name → publishers/google resource name for GCP
            MANAGED_METRIC_MAP: dict[str, str] = {
                "final_response_quality":              "publishers/google/evaluationMetrics/final_response_quality",
                "hallucination":                       "publishers/google/evaluationMetrics/hallucination",
                "tool_use_quality":                    "publishers/google/evaluationMetrics/tool_use_quality",
                "safety":                              "publishers/google/evaluationMetrics/safety",
                "final_response_match":                "publishers/google/evaluationMetrics/final_response_match",
                "final_response_ref_free":             "publishers/google/evaluationMetrics/final_response_reference_free",
                "agent_multi_turn_task_success":       "publishers/google/evaluationMetrics/multi_turn_task_success",
                "agent_multi_turn_tool_use_quality":   "publishers/google/evaluationMetrics/multi_turn_tool_use_quality",
                "agent_multi_turn_trajectory_quality": "publishers/google/evaluationMetrics/multi_turn_trajectory_quality",
            }

            selected_trajectory_metrics = [m for m in metric_names if m in TRAJECTORY_METRICS]
            selected_managed_metrics    = [m for m in metric_names if m in MANAGED_METRICS]
            managed_scores_by_index: dict[int, dict[str, Any]] = {}

            needs_vertex_eval = bool(selected_trajectory_metrics or selected_managed_metrics)

            if needs_vertex_eval:
                import asyncio
                import re
                import pandas as pd
                import vertexai
                from vertexai import Client as VertexClient
                from vertexai import types as vertex_types
                from vertexai.preview.evaluation import EvalTask
                from google.genai import types as genai_types
                from app.core.config import get_settings

                settings = get_settings()
                project_id = agent.gcp_project or settings.gcp_project_id
                region     = agent.region or settings.gcp_region
                if not project_id:
                    raise ValueError("GCP Project ID is required for Vertex AI evaluation")

                vertexai.init(project=project_id, location=region)

                # ── Extract data from invoke results ─────────────────────────
                prompts:                  list[str] = []
                responses:                list[str] = []
                references:               list[Any] = []
                predicted_trajectories:   list[Any] = []
                reference_trajectories:   list[Any] = []
                intermediate_events_list: list[Any] = []

                def _extract_field(raw: Any, fields: list[str]) -> Any:
                    if raw is None:
                        return None
                    for f in fields:
                        if isinstance(raw, pd.Series):
                            val = raw.get(f)
                            if val is not None and not (
                                isinstance(val, float) and pd.isna(val)
                            ):
                                return val
                        elif isinstance(raw, dict):
                            if f in raw:
                                return raw[f]
                        elif hasattr(raw, f):
                            try:
                                return getattr(raw, f)
                            except Exception:
                                pass
                    return None

                for idx, row in enumerate(validated.rows):
                    invoke = invoke_results[idx] if idx < len(invoke_results) else None

                    context = (row.get("context") or "").strip()
                    prompt  = row.get("input", "")
                    prompts.append(
                        f"Context:\n{context}\n\nUser:\n{prompt}" if context else prompt
                    )

                    actual = invoke.output if invoke and not invoke.error else ""
                    responses.append(actual)

                    raw_row = invoke.raw if invoke else None
                    pred_traj = _extract_field(
                        raw_row,
                        ["predicted_trajectory", "agent_trajectory", "trajectory"]
                    )

                    # Fallback: extract agent calls from agent_data turns
                    if pred_traj is None and raw_row is not None:
                        import json
                        agent_data_raw = None
                        if isinstance(raw_row, pd.Series):
                            agent_data_raw = raw_row.get("agent_data")
                        elif isinstance(raw_row, dict):
                            agent_data_raw = raw_row.get("agent_data")

                        if agent_data_raw:
                            try:
                                agent_data = (
                                    json.loads(agent_data_raw)
                                    if isinstance(agent_data_raw, str)
                                    else agent_data_raw
                                )
                                tool_calls = []
                                seen_authors: set[str] = set()
                                turns = agent_data.get("turns") or []
                                for turn in turns:
                                    events = turn.get("events") or []
                                    for event in events:
                                        if not isinstance(event, dict):
                                            continue
                                        author = event.get("author", "").strip()
                                        if not author or author in seen_authors:
                                            continue
                                        # Extract text input from content parts
                                        parts = event.get("content", {}).get("parts", []) or []
                                        input_text = ""
                                        for part in parts:
                                            if isinstance(part, dict) and part.get("text"):
                                                input_text = part["text"][:200]
                                                break
                                        tool_calls.append({
                                            "tool_name": author,
                                            "tool_input": {"request": input_text} if input_text else {},
                                        })
                                        seen_authors.add(author)
                                if tool_calls:
                                    pred_traj = tool_calls
                                    logger.info(
                                        "Extracted %d agent calls from agent_data for row %d: %s",
                                        len(tool_calls), idx,
                                        [t["tool_name"] for t in tool_calls],
                                        extra={"component": "evaluation_runner", "evaluation_id": str(evaluation_id)},
                                    )
                            except Exception as e:
                                logger.warning(
                                    "Failed to extract trajectory from agent_data for row %d: %s",
                                    idx, e,
                                    extra={"component": "evaluation_runner", "evaluation_id": str(evaluation_id)},
                                )

                    predicted_trajectories.append(pred_traj)

                    

                    # reference_trajectory comes from the dataset row
                    ref_traj = row.get("reference_trajectory")
                    reference_trajectories.append(ref_traj)

                    ref = row.get("reference") or row.get("expected_output")
                    references.append(ref or "")
                    raw_row = invoke.raw if invoke else None
                    ie = _extract_field(raw_row, ["intermediate_events"])
                    intermediate_events_list.append(ie if ie is not None else "")

                # ── Build DataFrame ───────────────────────────────────────────
                eval_df_data: dict[str, Any] = {
                    "prompt":   prompts,
                    "response": responses,
                }
                if any(r for r in references):
                    eval_df_data["reference"] = references
                if any(t is not None for t in predicted_trajectories):
                    eval_df_data["predicted_trajectory"] = predicted_trajectories
                if any(t is not None for t in reference_trajectories):
                    eval_df_data["reference_trajectory"] = reference_trajectories

                eval_df = pd.DataFrame(eval_df_data)

                

                # ── PART A: Trajectory metrics via EvalTask ───────────────────
                if selected_trajectory_metrics:
                    traj_eval_metrics: list[Any] = []
                    seen_traj: set[str] = set()
                    for m in selected_trajectory_metrics:
                        mapped = TRAJECTORY_METRIC_MAP.get(m)
                        if mapped and mapped not in seen_traj:
                            traj_eval_metrics.append(mapped)
                            seen_traj.add(mapped)

                   

                    traj_eval_task = EvalTask(
                        dataset=eval_df,
                        metrics=traj_eval_metrics,
                        experiment=f"agentops-traj-{str(run.id)[:8]}",
                    )
                    traj_result = await asyncio.to_thread(traj_eval_task.evaluate)
                    traj_table  = traj_result.metrics_table


                    for idx in range(len(traj_table)):
                        result_row = traj_table.iloc[idx]
                        row_scores = managed_scores_by_index.setdefault(idx, {})
                        for m in selected_trajectory_metrics:
                            mapped = TRAJECTORY_METRIC_MAP.get(m)
                            if not mapped:
                                continue
                            score_col = (
                                f"{mapped}/score"
                                if f"{mapped}/score" in traj_table.columns
                                else mapped
                            )
                            if score_col in traj_table.columns:
                                val = result_row[score_col]
                                if val is not None and not (
                                    isinstance(val, float) and pd.isna(val)
                                ):
                                    row_scores[m] = float(val)

                    

                # ── PART B: Managed metrics via client.evals.evaluate ─────────
                if selected_managed_metrics:

                    # Map UI metric names → types.RubricMetric constants
                    RUBRIC_METRIC_MAP = {
                        "final_response_quality":              vertex_types.RubricMetric.FINAL_RESPONSE_QUALITY,
                        "hallucination":                       vertex_types.RubricMetric.HALLUCINATION,
                        "tool_use_quality":                    vertex_types.RubricMetric.TOOL_USE_QUALITY,
                        "safety":                              vertex_types.RubricMetric.SAFETY,
                        "final_response_match":                vertex_types.RubricMetric.FINAL_RESPONSE_MATCH,
                        "final_response_ref_free":             vertex_types.RubricMetric.FINAL_RESPONSE_REFERENCE_FREE,
                        "agent_multi_turn_task_success":       vertex_types.RubricMetric.MULTI_TURN_TASK_SUCCESS,
                        "agent_multi_turn_tool_use_quality":   vertex_types.RubricMetric.MULTI_TURN_TOOL_USE_QUALITY,
                        "agent_multi_turn_trajectory_quality": vertex_types.RubricMetric.MULTI_TURN_TRAJECTORY_QUALITY,
                    }

                    # Build rubric metrics list — deduplicated
                    rubric_metrics = []
                    seen_rubric: set[str] = set()
                    for m in selected_managed_metrics:
                        rubric = RUBRIC_METRIC_MAP.get(m)
                        if rubric and m not in seen_rubric:
                            rubric_metrics.append(rubric)
                            seen_rubric.add(m)

                    # Build DataFrame with prompt + response + optional reference
                    managed_df_data: dict[str, Any] = {
                        "prompt":   prompts,
                        "response": responses,
                    }
                    if any(r for r in references):
                        managed_df_data["reference"] = references

                    if any(ie for ie in intermediate_events_list):
                        managed_df_data["intermediate_events"] = intermediate_events_list

                    managed_df = pd.DataFrame(managed_df_data)

                    

                    vertex_client = VertexClient(project=project_id, location=region)

                    eval_result = await asyncio.to_thread(
                        vertex_client.evals.evaluate,
                        dataset=vertex_types.EvaluationDataset(eval_dataset_df=managed_df),
                        metrics=rubric_metrics,
                    )

                    # Parse per-row scores into managed_scores_by_index
                    for case_result in (eval_result.eval_case_results or []):
                        case_idx = case_result.eval_case_index or 0
                        candidates = case_result.response_candidate_results or []
                        if not candidates:
                            continue
                        row_scores = managed_scores_by_index.setdefault(case_idx, {})
                        for metric_key, metric_result in (
                            candidates[0].metric_results or {}
                        ).items():
                            norm = re.sub(r"_v\d+$", "", metric_key.lower())

                            # Store error if metric failed
                            error_msg = getattr(metric_result, "error_message", None)
                            if error_msg:
                                row_scores[f"{norm}_error"] = error_msg
                                logger.warning(
                                    "Metric %s failed for case %s: %s",
                                    norm, case_idx, error_msg,
                                    extra={"component": "evaluation_runner", "evaluation_id": str(evaluation_id)},
                                )
                                continue

                            # Store scalar score
                            if metric_result.score is not None:
                                row_scores[norm] = metric_result.score

                            # Store explanation
                            if getattr(metric_result, "explanation", None):
                                row_scores[f"{norm}_explanation"] = metric_result.explanation

                            # Store rubric verdicts
                            rubric_verdicts = getattr(metric_result, "rubric_verdicts", None) or []
                            if rubric_verdicts:
                                verdicts_list = []
                                for rv in rubric_verdicts:
                                    verdict_dict: dict[str, Any] = {}
                                    verdict_val = getattr(rv, "verdict", None)
                                    if verdict_val is not None:
                                        verdict_dict["verdict"] = "Pass" if verdict_val else "Fail"
                                    reasoning = getattr(rv, "reasoning", None)
                                    if reasoning:
                                        verdict_dict["reasoning"] = reasoning
                                    evaluated_rubric = getattr(rv, "evaluated_rubric", None)
                                    if evaluated_rubric:
                                        criteria = getattr(evaluated_rubric, "criteria", None)
                                        if criteria:
                                            verdict_dict["criteria"] = criteria
                                    verdicts_list.append(verdict_dict)
                                row_scores[f"{norm}_rubric_verdicts"] = verdicts_list

                    

            # ── Per-sample scoring and DB save ────────────────────────────────
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

                # Merge Vertex managed/trajectory scores if present
                if idx in managed_scores_by_index:
                    scores.update(managed_scores_by_index[idx])

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
