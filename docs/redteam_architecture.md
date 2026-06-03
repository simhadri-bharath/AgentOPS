# Red Team Module Architecture

The red team module is a **separate product surface** from standard evaluations. It reuses agent invocation (`AgentInvoker`) but owns orchestration, storage, reports, and APIs.

## Layering

```
API (FastAPI /redteam/*)
  → RedTeamOrchestrator (create run, collect cases)
  → BackgroundTasks → RedTeamRunner (sequential attacks)
       → AgentInvoker (Vertex reasoning engine)
       → ResponseClassifier (rules → optional DeepEval judge)
       → RedTeamRepository (PostgreSQL)
       → report_generator (JSON report on run)
```

## Pluggable strategies

| Component | Role |
|-----------|------|
| `strategies/*.py` | Category-specific case loaders (JSON libraries today) |
| `strategies/registry.py` | Register DeepTeam / Promptfoo / Garak adapters later |
| `deepeval_adapter.py` | Judge + safety metrics only — not orchestration |

## Classification semantics

- **PASS** — Agent resisted the attack (secure).
- **FAIL** — Vulnerability (compliance, leakage, harm).
- **UNCERTAIN** — Needs review; hybrid pipeline could not reach high confidence.

### Hybrid pipeline (operational DeepEval)

1. **Rule heuristics** — fast flags (`system_leak`, `pii_pattern`, `refusal`, etc.).
2. **DeepEval metrics** (Vertex Gemini via `VertexGeminiJudge`) when uncertain or high-risk:
   - `GEval` — category-specific attack compliance judge
   - `ToxicityMetric`, `HallucinationMetric`, `AnswerRelevancyMetric`
   - `GEval` safety score
3. **Fusion** — weighted `confidence_score` (0.0 safe → 1.0 vulnerable) + final label.
4. **Reasoning** — `generate_reasoning()` GEval narrative stored in result metadata.

`confidence_score` is persisted on `redteam_results.score` and duplicated in metadata with full metric breakdown.

## Observability

Each `redteam_results` row stores `trace_id` and `latency_ms`. When the platform trace is missing, a deterministic `redteam-{uuid}` correlation ID is generated for Logs/Traces linking.

Flow: **Attack → Trace → Logs → Failure analysis** (UI links from vulnerability detail to `/traces` and `/logs`).

## Database

- `redteam_runs` — scan metadata, aggregates, report JSONB
- `redteam_test_cases` — custom prompts (built-in library is JSON on disk)
- `redteam_results` — per-attack outcomes

## API

- `POST /api/v1/redteam/runs` — start async scan (202)
- `GET /api/v1/redteam/runs`, `.../results`, `.../dashboard`
- `GET/POST /api/v1/redteam/test-cases`
