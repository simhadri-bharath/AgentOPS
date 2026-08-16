"""Execute red team attacks sequentially against a target agent."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories.agent_repository import AgentRepository
from app.repositories.redteam_repository import RedTeamRepository
from app.services.evaluation import registry
from app.services.invokers.agent_engine import REDTEAM_USER_ID, AgentEngineInvoker
from app.services.redteam.classifier import ResponseClassifier
from app.services.redteam.report_generator import generate_report
from app.services.redteam.case_plan import build_run_cases
from app.services.redteam.strategies.base import AttackCase
from app.services.redteam.trace_utils import correlation_trace_id, extract_trace_id

logger = get_logger(__name__)


class RedTeamRunner:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = RedTeamRepository(session)
        self._agent_repo = AgentRepository(session)
        self._invoker = AgentEngineInvoker(user_id=REDTEAM_USER_ID)

    async def run(self, run_id: uuid.UUID) -> None:
        registry.register(run_id, self._invoker)
        run = await self._repo.get_run(run_id)
        if not run:
            logger.error("Red team run not found: %s", run_id)
            return

        config = dict(run.config or {})
        use_llm_judge = bool(config.get("use_llm_judge", True))
        categories = list(run.categories or [])

        selected_ids = config.get("selected_case_ids") or None
        if selected_ids == []:
            selected_ids = None

        cases: list[AttackCase] = await build_run_cases(
            self._repo,
            categories=categories,
            include_custom_cases=config.get("include_custom_cases", True),
            selected_case_ids=selected_ids,
        )

        await self._repo.update_run(
            run,
            status="running",
            total_tests=len(cases),
            mark_started=True,
        )
        await self._session.commit()

        from collections import Counter

        case_plan = Counter(c.category for c in cases)
        logger.info(
            "Red team scan started: %s tests across %s (interleaved order)",
            len(cases),
            dict(case_plan),
            extra={
                "component": "redteam_runner",
                "run_id": str(run_id),
                "categories": categories,
                "case_plan": dict(case_plan),
            },
        )

        try:
            agent = await self._agent_repo.get_agent(run.agent_id)
            if not agent:
                raise ValueError(f"Agent {run.agent_id} not found")
            if not agent.endpoint_url:
                raise ValueError("Agent has no endpoint_url (reasoning engine resource)")

            classifier = ResponseClassifier(
                use_llm_judge=use_llm_judge,
                judge_model=run.judge_model,
            )

            passed = failed = uncertain = 0
            result_rows: list[dict[str, Any]] = []

            for idx, case in enumerate(cases):
                if self._invoker.cancelled:
                    logger.info(
                        "Red-team scan cancelled after %s case(s)",
                        idx,
                        extra={"component": "redteam_runner", "run_id": str(run_id)},
                    )
                    break

                invoke = await self._invoke_one(agent.endpoint_url, case.prompt)
                response_text = invoke.output if not invoke.error else ""
                # The invocation id is a real, resolvable identifier. The old
                # path fabricated "redteam-<hex>", which Cloud Trace could
                # never resolve, so the observability column was decorative.
                trace_id = (
                    (invoke.trace.invocation_id if invoke.trace else None)
                    or extract_trace_id(invoke.raw_events)
                    or correlation_trace_id(str(run_id), case.id)
                )

                if invoke.error:
                    # Distinguish real API failures from "agent returned empty"
                    is_empty_response = (
                        "no text" in (invoke.error or "").lower()
                        or "empty" in (invoke.error or "").lower()
                    )
                    if is_empty_response:
                        # Agent was reached but returned nothing — this is
                        # likely the agent defending against the attack.
                        # Send through the classifier with empty response.
                        verdict = await classifier.classify_async(
                            category=case.category,
                            prompt=case.prompt,
                            response="",
                            expected_behavior=case.expected_behavior,
                        )
                        classification = verdict.classification
                        score = verdict.confidence_score
                        reason = verdict.reason
                        method = verdict.method
                    else:
                        # Real invocation failure (network, auth, etc.)
                        classification = "UNCERTAIN"
                        score = None
                        reason = f"Invocation error: {invoke.error}"
                        method = "invocation_error"
                        # Create a minimal verdict for the error path
                        verdict = type("V", (), {
                            "classification": classification,
                            "confidence_score": score,
                            "reason": reason,
                            "method": method,
                            "severity": "unknown",
                            "severity_reason": "Cannot determine — agent invocation failed.",
                            "semantic_reasoning": None,
                            "toxicity_score": None,
                            "hallucination_score": None,
                            "safety_score": None,
                            "tool_calling_score": None,
                            "heuristic_flags": [],
                            "details": None,
                        })()
                else:
                    verdict = await classifier.classify_async(
                        category=case.category,
                        prompt=case.prompt,
                        response=response_text,
                        expected_behavior=case.expected_behavior,
                    )
                    classification = verdict.classification
                    score = verdict.confidence_score
                    reason = verdict.reason
                    method = verdict.method

                # Use LLM-generated severity instead of hardcoded case severity
                llm_severity = getattr(verdict, "severity", case.severity)
                llm_severity_reason = getattr(verdict, "severity_reason", "")

                if classification == "PASS":
                    passed += 1
                elif classification == "FAIL":
                    failed += 1
                else:
                    uncertain += 1

                test_case_uuid = uuid.UUID(case.db_id) if case.db_id else None

                row = await self._repo.add_result(
                    run_id=run.id,
                    test_case_id=test_case_uuid,
                    category=case.category,
                    severity=llm_severity,
                    prompt=case.prompt,
                    response=response_text or None,
                    classification=classification,
                    score=score,
                    reason=reason,
                    trace_id=trace_id,
                    latency_ms=invoke.latency_ms,
                    metadata={
                        "case_id": case.id,
                        "method": method,
                        "tags": case.tags,
                        "invocation_error": invoke.error,
                        "confidence_score": verdict.confidence_score,
                        "severity_reason": llm_severity_reason,
                        "semantic_reasoning": verdict.semantic_reasoning,
                        "toxicity_score": verdict.toxicity_score,
                        "hallucination_score": verdict.hallucination_score,
                        "safety_score": verdict.safety_score,
                        "tool_calling_score": verdict.tool_calling_score,
                        "heuristic_flags": verdict.heuristic_flags or [],
                        "deepeval": (verdict.details or {}).get("deepeval")
                        if verdict.details
                        else None,
                        "observability": {
                            "trace_id": trace_id,
                            "correlation_hint": (
                                f"Search traces/logs for trace_id={trace_id} "
                                "to analyze tool calls and failure context."
                            ),
                        },
                    },
                )
                result_rows.append(
                    {
                        "id": str(row.id),
                        "category": case.category,
                        "severity": llm_severity,
                        "prompt": case.prompt,
                        "classification": classification,
                        "reason": reason,
                        "trace_id": trace_id,
                        "confidence_score": score,
                        "severity_reason": llm_severity_reason,
                        "semantic_reasoning": verdict.semantic_reasoning,
                        "toxicity_score": verdict.toxicity_score,
                        "hallucination_score": verdict.hallucination_score,
                        "safety_score": verdict.safety_score,
                        "tool_calling_score": verdict.tool_calling_score,
                        "heuristic_flags": verdict.heuristic_flags or [],
                    }
                )

                await self._repo.update_run(
                    run,
                    passed=passed,
                    failed=failed,
                    uncertain=uncertain,
                )
                await self._session.commit()

                logger.info(
                    "Red team test %s/%s [%s] %s -> %s",
                    idx + 1,
                    len(cases),
                    case.category,
                    case.id,
                    classification,
                    extra={
                        "component": "redteam_runner",
                        "run_id": str(run_id),
                        "category": case.category,
                        "case_id": case.id,
                        "trace_id": trace_id,
                    },
                )

            report = generate_report(
                run_id=str(run.id),
                agent_id=str(run.agent_id),
                categories=categories,
                results=result_rows,
            )
            # A scan stopped part-way is not a completed scan. Reporting it as
            # completed would present partial coverage as a full clean result.
            cancelled = self._invoker.cancelled
            await self._repo.update_run(
                run,
                status="cancelled" if cancelled else "completed",
                error_message=(
                    f"Cancelled after {len(result_rows)} of {len(cases)} attack(s)."
                    if cancelled
                    else None
                ),
                passed=passed,
                failed=failed,
                uncertain=uncertain,
                report=report,
                mark_completed=True,
            )
            await self._session.commit()

            logger.info(
                "Red team scan completed",
                extra={
                    "component": "redteam_runner",
                    "run_id": str(run_id),
                    "passed": passed,
                    "failed": failed,
                },
            )
        except Exception as exc:
            logger.exception("Red team scan failed", extra={"run_id": str(run_id)})
            await self._repo.update_run(
                run,
                status="failed",
                error_message=str(exc),
                mark_completed=True,
            )
            await self._session.commit()

    async def _invoke_one(self, resource_name: str, prompt: str):
        """Invoke one attack prompt and return the harvested outcome.

        Uses the same invoker as evaluation, so a red-team finding carries the
        real trace, trajectory and sub-agent path instead of a synthetic id.
        """
        return await self._invoker.invoke(resource_name, prompt)
