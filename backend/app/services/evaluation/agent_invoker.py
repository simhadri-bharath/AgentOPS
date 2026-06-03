"""Vertex AI Reasoning Engine invocation (notebook-aligned)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.evaluation.inference_dataset import (
    build_inference_dataframe,
    extract_response_text,
)
from app.services.evaluation.reasoning_engine_direct import (
    events_preview,
    stream_query_prompt,
)
from app.services.gcp.auth import require_adc
from app.services.gcp.eval_deps import check_evals_dependencies

logger = get_logger(__name__)


@dataclass
class InvokeResult:
    output: str
    latency_ms: int
    raw: Any | None = None
    error: str | None = None


class AgentInvoker:
    """
    Invokes Vertex AI Reasoning Engines using Client.evals.run_inference
    (same pattern as vertexaireasoningengine.ipynb).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Any | None = None
        self._project_id: str | None = None
        self._region: str | None = None

    def initialize(self, *, region_override: str | None = None) -> None:
        ok, err = check_evals_dependencies()
        if not ok:
            raise RuntimeError(err or "Evaluation dependencies not installed")

        auth = require_adc()
        self._project_id = self._settings.gcp_project_id or auth.project_id
        self._region = region_override or self._settings.gcp_region
        if not self._project_id:
            raise RuntimeError("GCP_PROJECT_ID is required for agent invocation")

        import vertexai
        from vertexai import Client

        vertexai.init(project=self._project_id, location=self._region)
        self._client = Client(project=self._project_id, location=self._region)
        # Force-load evals so failures happen at init, not mid-batch
        _ = self._client.evals
        logger.info(
            "AgentInvoker initialized",
            extra={"component": "agent_invoker", "project_id": self._project_id},
        )

    def _ensure_client(self, *, resource_name: str | None = None) -> Any:
        desired_region = self._region_from_resource_name(resource_name) or self._settings.gcp_region
        if self._client is None or self._region != desired_region:
            self.initialize(region_override=desired_region)
        return self._client

    def invoke_agent(
        self,
        resource_name: str,
        prompt: str,
        *,
        context: str | None = None,
        user_id: str = "agentops_eval_user",
    ) -> InvokeResult:
        row: dict[str, str] = {"input": prompt}
        if context:
            row["context"] = context
        results = self.batch_invoke(resource_name, [row], user_id=user_id)
        return results[0] if results else InvokeResult(output="", latency_ms=0, error="No result")

    def batch_invoke(
        self,
        resource_name: str,
        rows: list[dict[str, str]],
        *,
        user_id: str = "agentops_eval_user",
    ) -> list[InvokeResult]:
        """Bulk invoke via client.evals.run_inference (notebook bulk pattern)."""
        if not rows:
            return []

        client = self._ensure_client(resource_name=resource_name)
        df = build_inference_dataframe(rows)
        effective_region = self._region_from_resource_name(resource_name) or self._region

        last_error: str | None = None
        for attempt in range(self._settings.evaluation_max_retries + 1):
            start = time.perf_counter()
            try:
                logger.info(
                    "run_inference starting for %s samples (attempt %s)",
                    len(rows),
                    attempt + 1,
                    extra={"component": "agent_invoker"},
                )
                inference_output = client.evals.run_inference(agent=resource_name, src=df)
                total_ms = int((time.perf_counter() - start) * 1000)
                per_row_ms = max(total_ms // len(rows), 1)

                result_df = self._to_dataframe(inference_output)
                logger.info(
                    "run_inference returned columns: %s (rows=%s)",
                    list(result_df.columns),
                    len(result_df),
                    extra={"component": "agent_invoker"},
                )
                if len(result_df) > 0:
                    sample = result_df.iloc[0]
                    preview = {}
                    for col in result_df.columns:
                        val = sample[col]
                        if isinstance(val, str) and len(val) > 120:
                            preview[str(col)] = val[:120] + "..."
                        else:
                            preview[str(col)] = str(val)[:120]
                    logger.info(
                        "run_inference row-0 preview: %s",
                        preview,
                        extra={"component": "agent_invoker"},
                    )

                results = self._parse_result_dataframe(
                    result_df, len(rows), per_row_ms, inference_output
                )
                return self._fallback_empty_results(resource_name, rows, results, user_id, region=effective_region)
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "run_inference attempt %s failed: %s",
                    attempt + 1,
                    exc,
                    extra={"component": "agent_invoker"},
                )

        elapsed = 0
        return [
            InvokeResult(output="", latency_ms=elapsed, error=last_error or "Invocation failed")
            for _ in rows
        ]

    def batch_invoke_legacy(
        self,
        resource_name: str,
        prompts: list[str],
        *,
        contexts: list[str | None] | None = None,
    ) -> list[InvokeResult]:
        rows = []
        for i, prompt in enumerate(prompts):
            row: dict[str, str] = {"input": prompt}
            if contexts and i < len(contexts) and contexts[i]:
                row["context"] = contexts[i]
            rows.append(row)
        return self.batch_invoke(resource_name, rows)

    @staticmethod
    def _to_dataframe(inference_output: Any) -> pd.DataFrame:
        # Vertex Client.evals.run_inference returns EvaluationDataset
        eval_df = getattr(inference_output, "eval_dataset_df", None)
        if eval_df is not None:
            return eval_df
        legacy_dataset = getattr(inference_output, "dataset", None)
        if legacy_dataset is not None:
            return legacy_dataset
        if isinstance(inference_output, pd.DataFrame):
            return inference_output
        return pd.DataFrame(inference_output)

    def _fallback_empty_results(
        self,
        resource_name: str,
        rows: list[dict[str, str]],
        results: list[InvokeResult],
        user_id: str,
        region: str | None = None,
    ) -> list[InvokeResult]:
        """Retry empty run_inference rows via direct stream_query."""
        effective_region = region or self._region_from_resource_name(resource_name) or self._settings.gcp_region
        if not self._project_id or not self._region or self._region != effective_region:
            self.initialize(region_override=effective_region)
        assert self._project_id and effective_region

        out: list[InvokeResult] = []
        for i, (row, result) in enumerate(zip(rows, results)):
            if result.output.strip():
                out.append(result)
                continue

            prompt = row.get("input", "").strip()
            context = row.get("context", "").strip() if row.get("context") else ""
            if context:
                prompt = f"Context:\n{context}\n\nUser:\n{prompt}"

            logger.info(
                "run_inference empty for row %s — trying stream_query fallback",
                i,
                extra={"component": "agent_invoker"},
            )
            start = time.perf_counter()
            text, events, err = stream_query_prompt(
                project_id=self._project_id,
                region=effective_region,
                resource_name=resource_name,
                prompt=prompt,
                user_id=user_id,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)

            if text:
                out.append(
                    InvokeResult(
                        output=text,
                        latency_ms=latency_ms,
                        raw={"fallback": "stream_query", "events": events[:3]},
                    )
                )
            else:
                logger.warning(
                    "stream_query fallback empty row %s: %s preview=%s",
                    i,
                    err,
                    events_preview(events),
                    extra={"component": "agent_invoker"},
                )
                out.append(
                    InvokeResult(
                        output="",
                        latency_ms=latency_ms,
                        error=err or result.error or "Empty agent response",
                        raw={"fallback": "stream_query", "events": events[:5]},
                    )
                )
        return out

    def _parse_result_dataframe(
        self,
        result_df: pd.DataFrame,
        expected_rows: int,
        per_row_ms: int,
        raw_output: Any,
    ) -> list[InvokeResult]:
        results: list[InvokeResult] = []
        for i in range(expected_rows):
            if i >= len(result_df):
                results.append(
                    InvokeResult(
                        output="",
                        latency_ms=per_row_ms,
                        error="Missing row in inference output",
                    )
                )
                continue
            row = result_df.iloc[i]
            text, parse_error = extract_response_text(row, result_df)
            if parse_error and not text:
                results.append(
                    InvokeResult(
                        output="",
                        latency_ms=per_row_ms,
                        error=parse_error,
                        raw=row,
                    )
                )
            elif not text:
                results.append(
                    InvokeResult(
                        output="",
                        latency_ms=per_row_ms,
                        error="Empty agent response (check Vertex agent logs)",
                        raw=row,
                    )
                )
            else:
                results.append(
                    InvokeResult(output=text, latency_ms=per_row_ms, raw=row)
                )
        return results

    def parse_response(self, inference_output: Any) -> str:
        df = self._to_dataframe(inference_output)
        if df.empty:
            return ""
        text, _ = extract_response_text(df.iloc[0], df)
        return text

    @staticmethod
    def _region_from_resource_name(resource_name: str | None) -> str | None:
        if not resource_name:
            return None
        marker = "/locations/"
        if marker not in resource_name:
            return None
        try:
            return resource_name.split(marker, 1)[1].split("/", 1)[0]
        except Exception:
            return None
