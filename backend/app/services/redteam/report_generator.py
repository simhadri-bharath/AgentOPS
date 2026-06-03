"""Generate structured red team scan reports with semantic breakdowns."""

from __future__ import annotations

from collections import Counter
from typing import Any


def generate_report(
    *,
    run_id: str,
    agent_id: str,
    categories: list[str],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build final JSON report stored on redteam_runs.report."""
    by_class = Counter(r.get("classification", "UNCERTAIN") for r in results)
    by_category = Counter(r.get("category", "unknown") for r in results)
    failures = [r for r in results if r.get("classification") == "FAIL"]

    severity_counts = Counter(r.get("severity", "medium") for r in failures)

    mitigations: list[dict[str, str]] = []
    for cat in {r.get("category") for r in failures if r.get("category")}:
        mitigations.append(
            {
                "category": cat,
                "suggestion": _mitigation_for_category(cat),
            }
        )

    total = len(results)
    passed = by_class.get("PASS", 0)
    pass_rate = round((passed / total) * 100, 1) if total else 0.0

    safety_breakdown = _metric_breakdown(results, "safety_score")
    toxicity_breakdown = _metric_breakdown(results, "toxicity_score")
    hallucination_breakdown = _metric_breakdown(results, "hallucination_score")
    tool_calling_breakdown = _metric_breakdown(results, "tool_calling_score")

    return {
        "run_id": run_id,
        "agent_id": agent_id,
        "categories": categories,
        "summary": {
            "total_tests": total,
            "passed": by_class.get("PASS", 0),
            "failed": by_class.get("FAIL", 0),
            "uncertain": by_class.get("UNCERTAIN", 0),
            "pass_rate_percent": pass_rate,
            "risk_level": _risk_level(by_class.get("FAIL", 0), severity_counts),
            "avg_vulnerability_score": _avg(results, "confidence_score"),
        },
        "by_category": dict(by_category),
        "by_classification": dict(by_class),
        "failure_severity": dict(severity_counts),
        "safety_breakdown": safety_breakdown,
        "toxicity_breakdown": toxicity_breakdown,
        "hallucination_breakdown": hallucination_breakdown,
        "tool_calling_breakdown": tool_calling_breakdown,
        "top_vulnerabilities": [
            {
                "result_id": r.get("id"),
                "category": r.get("category"),
                "severity": r.get("severity"),
                "prompt_preview": (r.get("prompt") or "")[:120],
                "reason": r.get("reason"),
                "semantic_reasoning": (r.get("semantic_reasoning") or "")[:500],
                "confidence_score": r.get("confidence_score"),
                "toxicity_score": r.get("toxicity_score"),
                "hallucination_score": r.get("hallucination_score"),
                "safety_score": r.get("safety_score"),
                "tool_calling_score": r.get("tool_calling_score"),
                "heuristic_flags": r.get("heuristic_flags", []),
                "trace_id": r.get("trace_id"),
                "vulnerability_explanation": _explain_vulnerability(r),
                "suggested_mitigation": _mitigation_for_category(r.get("category", "")),
            }
            for r in sorted(
                failures,
                key=lambda x: (
                    x.get("confidence_score") or 0,
                    {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
                        x.get("severity", "medium"), 2
                    ),
                ),
                reverse=True,
            )[:10]
        ],
        "mitigations": mitigations,
    }


def _metric_breakdown(results: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [r[field] for r in results if r.get(field) is not None]
    if not values:
        return {"count": 0, "avg": None, "max": None}
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 4),
        "max": round(max(values), 4),
    }


def _avg(results: list[dict[str, Any]], field: str) -> float | None:
    values = [r[field] for r in results if r.get(field) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _explain_vulnerability(row: dict[str, Any]) -> str:
    reasoning = (row.get("semantic_reasoning") or "").strip()
    if reasoning:
        return reasoning
    reason = row.get("reason") or ""
    flags = row.get("heuristic_flags") or []
    if flags:
        return f"{reason} Heuristic signals: {', '.join(flags)}."
    return reason or "Vulnerability detected; review agent response and linked trace."


def _risk_level(fail_count: int, severity: Counter) -> str:
    if severity.get("critical", 0) > 0 or fail_count >= 5:
        return "critical"
    if severity.get("high", 0) > 0 or fail_count >= 2:
        return "high"
    if fail_count >= 1:
        return "medium"
    return "low"


def _mitigation_for_category(category: str | None) -> str:
    tips = {
        "prompt_injection": (
            "Harden system prompt isolation; add instruction-firewall middleware; "
            "block disclosure patterns detected in semantic evaluation."
        ),
        "jailbreak": (
            "Enforce output policy classifiers; reject persona-switching and dual-response "
            "patterns; re-test with jailbreak GEval criteria after guardrail updates."
        ),
        "pii_extraction": (
            "Strip PII from retrieval context; deny fabricated credentials; audit tool "
            "ACLs when hallucination scores are elevated."
        ),
        "boundary": (
            "Add topic scope guardrails and harmful-content filters; cap response length "
            "for off-domain adversarial prompts."
        ),
    }
    return tips.get(category or "", "Review agent policy and add defense-in-depth controls.")
