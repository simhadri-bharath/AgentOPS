# AgentOps — Implementation Status, Architecture, and Roadmap

Branch: `feature/agent-engine-eval` · Last verified against `steptoe-surplus-lines-499008` on 2026-08-09

This document covers what is built, how it fits together, what is deliberately not
built, and what can be extended next. For how to operate the platform, see
[USER_GUIDE.md](USER_GUIDE.md).

---

## 1. What this platform does

AgentOps evaluates AI agents deployed to **Google Vertex AI Agent Engine**
(Reasoning Engines). It discovers what is deployed, invokes agents with real
prompts, harvests the full execution trace, and scores both the final answer and
each sub-agent inside it.

The three deployed agents it was built and verified against:

| Display name | Engine ID | Framework | Shape |
|---|---|---|---|
| Steptoe Chat Agent V1 | `8804280535544233984` | `google-adk` | multi-agent (`research_agent` → `formatter_agent`), retrieval-backed |
| Survey Analysis Agent V2 | `8531812758088318976` | `google-adk` | Discovery Engine + Flash |
| Survey  Agent v1 dev | `4370486702397980672` | `google-adk` | dev/test engine |

---

## 2. Architecture

Everything upstream of `EvaluationCase` speaks Google's event schema. Everything
downstream speaks only the canonical types. **If a metric executor ever imports a
Google type, the boundary has leaked** and the next platform will require
rewriting every evaluator.

```
                       Vertex AI Agent Engine
                                │
                                ▼
                     AgentEngineClient  (REST v1, public API only)
                                │
                                ▼
                     AgentEngineInvoker
                     invoke · batch_invoke · cancel
                     harvest_trace · cleanup
                                │
                                ▼
                        AgentEvent[]        normalized, framework-agnostic
                                │
                                ▼
                       TraceNormalizer
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
                  Trace                  Span[]     AgentSpan | ToolSpan | LLMSpan
                    └───────────┬───────────┘
                                ▼
                        EvaluationCase      the ONLY thing executors see
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        deterministic      trace_health        deepeval
              └─────────────────┼─────────────────┘
                                ▼
                          MetricResult
                                ▼
                    EvaluationRun + EvaluationResult
```

### Key modules

| Path | Responsibility |
|---|---|
| `backend/app/services/gcp/agent_engine_client.py` | Async REST client. The **only** place the invocation interface is chosen. |
| `backend/app/services/invokers/agent_engine.py` | Session lifecycle, invocation, trace harvest, cleanup, cancellation |
| `backend/app/services/evaluation/trace_model.py` | Canonical types: `AgentEvent`, `Span`, `Trace`, `ToolCall`, `EvaluationCase`, `InvocationState` |
| `backend/app/services/evaluation/trace_normalizer.py` | The **only** module that understands Google's event schema |
| `backend/app/services/evaluation/tool_kinds.py` | Tool classification + retrieval-context extraction |
| `backend/app/services/evaluation/trace_health.py` | Deterministic trace checks — no LLM, no reference |
| `backend/app/services/evaluation/metric_registry.py` | One metric catalogue that can explain its own unavailability |
| `backend/app/services/evaluation/judge.py` | Shared Gemini judge (Vertex-backed) |
| `backend/app/services/evaluation/executors/` | `deterministic.py`, `deepeval_exec.py` |
| `backend/app/services/evaluation/profiles.py` | Metric packs by agent type + capabilities |
| `backend/app/services/evaluation/runner.py` | Orchestration: load → invoke → cases → score → aggregate → persist |
| `backend/app/services/discovery/deployments.py` | Live, read-only inventory of what is deployed |
| `backend/app/services/datasets/from_sessions.py` | Golden-set bootstrap from production traffic |
| `backend/app/services/evaluation/sweeper.py` | Fails runs orphaned by a restart |

---

## 3. The invocation interface (settled by measurement, not assumption)

Recorded in [invocation_compatibility.md](invocation_compatibility.md). Three
candidates were probed against live engines:

| Variant | Result |
|---|---|
| `:query` + `classMethod=query` | **404** — method not found |
| `:query` + `classMethod=stream_query` | **404** — method not found |
| `:streamQuery` + `classMethod=stream_query` | **200**, complete trajectory |

**The rule the 404s revealed:** `:query` dispatches only *non-streaming* class
methods; `:streamQuery` dispatches only *streaming* ones. An ADK `AdkApp`
registers `stream_query` as streaming and exposes no plain `query`, so `:query`
is unusable against these agents entirely. `classMethod` selects *within* an
endpoint's method class, never across it.

A malformed `classMethod` also returns **404, not 400**, so status code alone
cannot distinguish a typo from an unsupported method. Error handling reads the
`Error Details` body.

The choice lives in two constants in `agent_engine_client.py`; switching is a
one-line change.

---

## 4. What was found only by running against production

Four defects that a fixture-based test suite would not have caught.

### 4.1 Retrieval context was silently empty

The live `search_documents` tool returns:

```json
{"result": [{"title": "…", "source_url": "…", "snippets": ["…", "…"]}]}
```

Neither `result` (singular) nor `snippets` matched the extractor. A live RAG agent
produced **zero** retrieval context, which would have made `faithfulness` and
`contextual_precision` score against nothing. After the fix: **39 documents** from
one turn.

Each snippet becomes its own `RetrievalDoc`. A concatenated blob would score as a
single relevant-or-not unit regardless of how much of it was noise.

### 4.2 Token counts were zero

`sessions.events.list` does **not** return `usageMetadata` — only the stream does.
Tokens are read from the stream chunks. After the fix: **28,447 in / 1,905 out**
for a single turn.

Separately, usage attached to a *tool-call* event was being dropped entirely,
undercounting every turn by the tokens the model spent deciding to call the tool.

### 4.3 The answer was a JSON envelope

The `formatter_agent` emits `{"text": "…"}` rather than bare text. Scoring the
envelope penalises the agent for its own serialization. Unwrapping happens in the
normalizer so both invocation and harvest paths get it.

### 4.4 Latency was fabricated

The old invoker computed `per_row_ms = total_ms // len(rows)`, so every sample in
a batch reported an identical number — and the dashboard's "average latency" was
built on it. Now measured per request: **p50 39.0s, p95 47.6s** across a real run.

---

## 5. The metric layer

### 5.1 What was removed

`FRAMEWORK_METRIC_EXECUTION_MAP` rewrote every named metric into a string
comparison **before the run was queued**:

```
faithfulness      → contains_expected
toxicity          → response_nonempty
answer_relevancy  → response_nonempty
context_precision → exact_match
```

Users read real metric names over `str.__contains__` results. It is gone. An
unknown metric now returns **400 naming it** instead of degrading silently.

RAGAS was a selectable framework while being uninstalled with zero code. Removed
from the UI until it has an implementation. The custom LLM/code metric authoring
panels mapped to `contains_expected` and `exact_match` and were removed for the
same reason.

### 5.2 The registry

23 metrics, each declaring `executor`, `requires`, `level`, `supports_span`,
`requires_reference`, and `cost`. Served to the frontend at
`GET /api/v1/evaluations/meta/metrics` so there is one definition, not two.

| Category | Metrics | Executor | Needs reference? |
|---|---|---|---|
| Trace health | `trace_tool_success_rate`, `trace_no_redundant_calls`, `trace_no_loop`, `trace_step_efficiency`, `trace_answered` | deterministic | No |
| Deterministic | `exact_match`, `contains_expected`, `response_nonempty` | deterministic | Mostly yes |
| Trajectory | `trajectory_in_order_match`, `trajectory_any_order_match`, `trajectory_precision`, `trajectory_recall`, `argument_match`, `tool_correctness` | deterministic / deepeval | Yes |
| Quality | `answer_relevancy`, `task_completion`, `correctness` | deepeval | `correctness` only |
| RAG | `faithfulness`, `contextual_precision`, `contextual_recall`, `hallucination` | deepeval | Precision/recall only |
| Safety | `toxicity`, `bias` | deepeval | No |

`hallucination`, `toxicity` and `bias` are **inverted** on the way out, so every
stored score reads higher-is-better and aggregates without special cases.

### 5.3 Unavailable is not zero

A metric whose inputs are missing is reported unavailable **with the missing
column named**, never scored as zero. "No `expected_output`" and "the agent got it
wrong" are different findings, and collapsing them into `0.0` destroys the
difference.

### 5.4 `argument_match`

Tool-name metrics cannot tell a good search from a bad one: two calls to
`search_documents` score identically on `trajectory_in_order_match` whether the
query was right or wrong. `argument_match` scores the fraction of expected
`(tool, key, value)` triples the agent got right. For a retrieval agent, the query
it chose carries most of the quality signal.

Verified: **1.0** against the correct query, **0.0** against the wrong one, **0.5**
when one of two arguments matched.

### 5.5 The judge

The previous custom judge raised
`TypeError("Schema-based generation is not supported…")`, silently breaking every
metric that wants structured output. Replaced with deepeval's native
`GeminiModel(use_vertexai=True)`. One judge now serves everything, instead of
three modules hardcoding `gemini-1.5-pro`, `gemini-2.5-flash` and `gemini-2.5-pro`
independently.

`ToolCorrectnessMetric` is passed the judge explicitly — it otherwise falls back
to OpenAI, which this deployment has no key for.

---

## 6. Span-level scoring

DeepEval documents component-level evaluation via `@observe` and
`update_current_span`, both of which require decorating the application. The agent
here is a **pickle deployed inside Agent Engine** — there is no application to
decorate. Spans are therefore reconstructed externally from session events and
passed as ordinary test cases.

The payoff, from a real run:

| Level | `answer_relevancy` |
|---|---|
| Whole trace | **0.9688** |
| `research_agent` span | **0.4062** |
| `formatter_agent` span | **1.0** |

The end-to-end number says the sample was fine. The span scores say the research
step was weak and the formatter covered for it. Only the second is actionable.

---

## 7. Datasets from production sessions

`POST /api/v1/datasets/from-sessions/preview` extracts one case per
`invocationId`:

```
input                <- first user-authored event text
actual_output        <- last terminal-agent text
retrieval_context    <- RETRIEVAL-classified tool responses only
reference_trajectory <- ordered [(tool, args)], seeded from what happened
conversation         <- prior turns, for multi-turn metrics
expected_output      <- blank, for human review
category             <- happy_path | multi_turn | long_context | edge_case | …
```

This removes two blockers at once: "I have no dataset" and "I have no reference
trajectory".

### Lifecycle

```
PRODUCTION_TRACE → BOOTSTRAPPED → NEEDS_REVIEW → HUMAN_REVIEWED → GOLDEN
```

**Promotion to `golden` is refused while any row lacks `expected_output`.** A
captured trajectory records what the agent *did*, not what it *should have done*;
an unreviewed set would enshrine a bug as the regression baseline.

### Self-traffic exclusion

Harvesting skips sessions owned by AgentOps itself
(`agentops-eval`, `agentops-redteam`, `agentops-probe`, plus the legacy
`agentops_eval_user`). On the live agent this excluded **8 of 25 sessions** —
without it, the platform's own test traffic would be fed back in as production
usage. Filtering is on session owner, not prompt text, because only the owner is
reliable.

---

## 8. Invocation state machine

Collapsing every failure into `failed` makes an agent bug indistinguishable from a
judge bug.

```
QUEUED → RUNNING → SUCCESS
                 | TIMEOUT          exceeded evaluation_timeout_seconds
                 | CANCELLED        stopped before or during dispatch
                 | AGENT_ERROR      the agent itself errored or returned nothing
                 | AUTH_ERROR       ADC / IAM (401, 403)
                 | RATE_LIMITED     429 / quota
                 | HARVEST_ERROR    invocation worked, events unreadable
                 | JUDGE_ERROR      invocation fine, metric evaluation failed
```

A sample that did not invoke successfully is **not scored at all** — scoring it
would report an outage as poor answer quality.

---

## 9. Reproducibility

Every run snapshots, at queue time and never re-read from live config:

```json
{
  "evaluator_model": "gemini-2.5-flash",
  "evaluator_framework": "deepeval",
  "evaluator_temperature": 0.0,
  "metric_config_version": "1",
  "invocation_interface": "streamQuery/stream_query",
  "dataset_version": 1,
  "dataset_source": "bootstrapped",
  "dataset_review_status": "needs_review",
  "agent_type": "multi_agent",
  "agent_capabilities": ["retrieval", "tool_use", "multi_agent"],
  "environment": "production",
  "framework_versions": {
    "deepeval": "3.9.9",
    "google-genai": "1.75.0",
    "google-cloud-aiplatform": "1.152.0",
    "httpx": "0.28.1"
  }
}
```

Without this, comparing 0.82 today to 0.71 in three months says nothing about the
agent.

Runs also record usage — agent tokens, tool calls, LLM calls, judge evaluations,
span evaluations, and an estimated cost — because scoring per span multiplies judge
calls and that needs to be visible rather than discovered on an invoice.

---

## 10. API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | DB, ADC, configured project and region |
| GET | `/api/v1/deployments` | Live inventory + activity + inferred type (read-only) |
| GET | `/api/v1/deployments/{engine_id}` | Full spec, class methods, recent sessions |
| POST | `/api/v1/deployments/{engine_id}/test-invoke` | Invoke before onboarding; writes nothing |
| POST | `/api/v1/deployments/onboard` | Create the agent record |
| DELETE | `/api/v1/deployments/onboard/{agent_id}` | Remove it |
| GET | `/api/v1/agents` · `/{id}` | Agent registry |
| PATCH | `/api/v1/agents/{id}` | Edit type, capabilities, purpose, environment |
| GET | `/api/v1/agents/{id}/recommended-metrics` | Metric pack for this agent |
| POST | `/api/v1/agents/{id}/test-invoke` | One prompt, full trace back |
| GET | `/api/v1/agents/{id}/metadata` | A2A card / SDK metadata |
| POST | `/api/v1/datasets/upload` | CSV/JSON upload |
| POST | `/api/v1/datasets/from-sessions/preview` | Harvest candidate cases |
| POST | `/api/v1/datasets/from-sessions` | Persist reviewed cases |
| PATCH | `/api/v1/datasets/{id}/review` | Advance review status (gated) |
| GET | `/api/v1/datasets/{id}/rows` | Rows with review state, filterable to unreviewed |
| PATCH | `/api/v1/datasets/{id}/rows/{index}` | Fill in a reviewer's judgement; bumps dataset version |
| GET | `/api/v1/evaluations/meta/metrics` | The metric catalogue |
| POST | `/api/v1/evaluations/{id}/cancel` | Stop a running or queued run |
| DELETE | `/api/v1/evaluations/{id}` | Delete a run and its results |
| GET | `/api/v1/evaluations/{id}/compare?baseline=` | Run-over-run deltas + comparability warnings |
| POST | `/api/v1/evaluations/jobs` · `/{id}/run` · `/run` | Create / queue / one-shot |
| POST | `/api/v1/evaluations/{id}/retry` | Re-run a failed job |
| GET | `/api/v1/evaluations/{id}` · `/results` · `/results/{rid}` | Run, samples, one sample |
| GET/POST | `/api/v1/redteam/*` | Red-team scans (see §12) |
| GET | `/api/v1/traces` · `/{trace_id}` | Cloud Trace proxy |

---

## 11. Data model

| Table | Added in this work |
|---|---|
| `agents` | `agent_type`, `capabilities`, `purpose`, `environment`, `invocation_config` (migration 005) |
| `datasets` | `source`, `review_status`, `version`, `created_by`, `agent_id`, `category_distribution` (006) |
| `evaluation_runs` | `run_config`, `usage` (007) |
| `evaluation_results` | `metric_explanations`, `metric_unavailable`, `metric_errors`, `span_scores`, `trace`, `state`, `error_message`, `tokens_in`, `tokens_out` (007) |

`agent_type` and `capabilities` are separate on purpose. The live chat agent is
`multi_agent` **and** retrieval-backed; type alone would recommend the wrong
metric pack for it.

Discovery does **not** overwrite these fields. `upsert_agent` fills blanks only, so
the startup sync cannot wipe what someone set during onboarding; `set_profile` is
the explicit-override path used by onboarding and PATCH.

---

## 11a. Red teaming

The catalogue is introspected from the installed DeepTeam rather than
hand-written. The previous two literals exposed 21 of 37 vulnerabilities and 9
of 28 attacks, and omitted every agentic one -- `GoalTheft`,
`RecursiveHijacking`, `ToolOrchestrationAbuse`, `UnexpectedCodeExecution`,
`AgentIdentityAbuse` -- which are the ones that matter for a tool-using ADK
agent.

| | Before | Now |
|---|---|---|
| Vulnerabilities | 21 hardcoded | 37, from the package |
| Attacks | 9 hardcoded | 28, from the package |
| Framework presets | none | 7 |

Framework presets (OWASP Top 10, OWASP ASI 2026, NIST AI RMF, MITRE ATLAS,
EU AI Act, Aegis, BeaverTails) are passed straight to `red_team(framework=...)`,
which derives the vulnerabilities and attacks itself. That turns a scan from
thirty-seven checkboxes into one choice.

Unknown names are rejected with the valid list. They used to be logged and
skipped, so a typo ran a smaller scan and still reported success.

Scans run with `async_mode=True` and `REDTEAM_CONCURRENCY`. They were forced
serial, and each attack is an agent round-trip plus judge calls.

Both scan modes now use `AgentEngineInvoker`, the same one evaluation uses, so
a finding carries the real invocation id, the sub-agent path and the tools that
were called. Previously custom mode fabricated `redteam-<hex>` -- which Cloud
Trace could never resolve -- and dynamic mode wrote `trace_id=None`, leaving the
observability column decorative.

`POST /redteam/runs/{id}/cancel` stops a scan, and a stopped scan reports
`cancelled` with how far it got rather than `completed` -- partial coverage
must not read as a clean result. There was previously no way to stop one short
of restarting the process.

One judge now serves evaluation and both scan modes. The red-team path used a
hand-rolled judge that raised `TypeError` on schema-based generation, which is
how newer DeepEval metrics request structured output, so those metrics were
silently broken there. `REDTEAM_DEFAULT_JUDGE` and `REDTEAM_USE_LLM_JUDGE` were
removed: nothing read them, and `JUDGE_MODEL` is the single setting.

DeepTeam's `model_callback` must be synchronous while the invoker is async.
`asyncio.run()` is not a safe bridge -- with `async_mode=True` DeepTeam may call
the callback from inside its own running loop, where it raises -- so the
coroutine is submitted to a dedicated loop on its own thread
(`invokers/sync_bridge.py`), which is correct from any caller.

---

## 12. What is NOT built (deliberate)

These are decisions, not omissions.

| Not built | Why |
|---|---|
| **RAGAS adapter** | DeepEval + deterministic + trace-health already cover the ground. RAGAS adds a third abstraction. It was removed from the UI rather than left as a dead option. |
| **Vertex managed metrics** | The `MANAGED_METRIC_MAP` path is half-working and the registry now unblocks the trajectory family, but it is out of the agreed scope. |
| **Cross-project discovery** | Every agent in this deployment lives in one project. The setting would be config with no caller. |
| **Multi-turn metrics** | `knowledge_retention`, `conversation_relevancy`, `role_adherence`. The `conversation` column exists so datasets do not need re-bootstrapping later. |
| **Dataset balance enforcement** | Categories are recorded and displayed; requiring a distribution is a policy decision. |
| **Job queue (Celery/RQ)** | Premature with one worker. A startup sweep handles restart orphans instead. |
| **Authentication / multi-tenancy** | No user model, no RBAC. Single-tenant, ADC-only. |
| **Custom metric authoring** | The UI existed but nothing implemented it. Removed rather than faked. |

---

## 13. Known limitations

1. **Latency is high and irreducible.** A retrieval turn against the live chat
   agent takes 30–48 seconds. A 50-sample run at `INVOKE_CONCURRENCY=8` takes
   roughly 4–5 minutes; serially it would exceed half an hour.

2. **`evaluation_timeout_seconds` defaults to 120s.** That allows roughly three
   retrieval turns. Raise it for slower agents.

3. **Survey agents show no observed tools.** Their retrieval happens inside the
   agent (Discovery Engine grounding) rather than as a `functionCall` event, so
   type inference proposes `conversational`. This is honest — it reports only what
   is observable — but means you must set `rag` manually for those two.

4. **Red team still uses the old invoker.** It has not been migrated to
   `AgentEngineInvoker`, so its trace IDs are still synthetic and its scans are
   still serial.

5. **Cost figures are estimates.** Based on published Gemini Flash rates, not
   billing data.

6. **`runtimeRevisions` is unavailable.** The v1 API has no `list` method and
   returns 404 on these engines, so revision-level comparison is not possible.

7. **Startup discovery scans 10 regions on every boot.** Regions not enabled for
   the project log a warning and are skipped, which is noisy but harmless.

---

## 14. Roadmap — ordered by value per unit of work

### Delivered since the first draft of this roadmap

- **Test before onboarding** — testing used to require onboarding first, which
  inverts the point of a test. `POST /deployments/{id}/test-invoke` writes nothing.
- **Agent profile editor** — type and capabilities had no UI, while the docs
  instructed users to set them by hand for agents whose retrieval is internal.
- **Run profile panel** — `usage` and `run_config` were persisted and never shown.

- **Dataset review** — `GET/PATCH /datasets/{id}/rows` plus a `/datasets` page.
  The golden gate was previously **unsatisfiable**: promotion was refused until
  every row had an `expected_output`, and no endpoint could read or set it.
- **Cancellation** — the invoker always supported it; nothing held the handle.
  An in-process registry now maps a run id to its invoker.
- **Run deletion** — refused while a run is executing.
- **Run comparison** — deltas per metric, per sub-agent and per sample, with the
  run snapshots checked so a judge or dataset change is reported instead of
  being read as a regression.

### Tier 1 — small, high value

| Item | Why | Where |
|---|---|---|

| **Per-agent thresholds** | `{metric: {warning, critical}}` → PASS / WARNING / FAIL, replacing the single global `METRIC_PASS_THRESHOLD` | `agents.invocation_config` or a new column |
| **Vertex managed metrics** | Half-working already; the registry unblocks the trajectory family | `metric_registry.py` + a `vertex_exec.py` |

### Tier 2 — moderate

| Item | Why |
|---|---|
| **Red-team on the new invoker** | Real trace IDs, real trajectories, concurrency, and cancellation come free. Currently red-team findings carry synthetic `redteam-<hex>` IDs that Cloud Trace cannot resolve. |
| **Red-team scope enforcement** | Backend-enforced gate on `agent.environment` before `POST /redteam/runs`. The column exists for exactly this. |
| **Tool safety policy** | `allowed` / `read_only` / `requires_confirmation` / `blocked` per tool, so a red-team run cannot exercise destructive capabilities against real infrastructure. `ToolKind` is the classification layer it builds on. |
| **Multi-turn metrics** | `knowledge_retention`, `conversation_relevancy`, `role_adherence`. The `conversation` column already carries the history. |
| **DeepTeam catalogue derivation** | The hand-maintained list exposes 21 of ~38 vulnerabilities and omits every agentic one (`goal_theft`, `recursive_hijacking`, `tool_orchestration_abuse`, `unexpected_code_execution`, `agent_identity_abuse`) — precisely the ones that matter for an ADK tool agent. |
| **Scheduled / CI evaluation** | Run a golden set nightly or on agent redeploy; alert on regression. |

### Tier 3 — larger

| Item | Why |
|---|---|
| **Additional platforms** | The canonical pipeline was built for this. A Cloud Run or A2A agent needs a new invoker and normalizer; nothing downstream changes. |
| **RAGAS as an optional adapter** | Cross-check for `tool_correctness` and RAG metrics. Pin a tested version and write adapter tests first — the 0.2 API has moved. |
| **Authentication and tenancy** | Required before this is shared beyond one team. |
| **Durable job queue** | Only once there is more than one worker. |
| **Human review / annotation queue** | Pair LLM judgements with periodic human labels to keep the judge calibrated. |

---

## 14a. Endpoint coverage

Every path the frontend calls was probed live against the running backend.
All 40 respond correctly; the API surface has no gaps relative to the UI.

One environment issue was found and fixed: `google-cloud-trace` is declared in
`requirements.txt` but was absent from the environment, so `GET /api/v1/traces`
returned **502 — cannot import name 'trace_v1'**, taking the Traces page, the
Logs page and the AgentDetail latency panel down with it. `pip install -r
requirements.txt` resolves it.

Payload shapes were checked in both directions, not just status codes:
`RedTeamRunCreate` against `startRedTeamRun`, and `RedTeamTestCaseCreate`
against the Attack Library form. Both match.

## 15. Testing

60 tests, `backend/tests/`. There were none before this work (`c547d76 "removed
test files"`).

| File | Covers |
|---|---|
| `test_tool_kinds.py` | Classification, the UNKNOWN-excluded case, the real `search_documents` payload shape |
| `test_trace_normalizer.py` | Event typing, `invocationId` grouping, multi-agent path, trajectory, retrieval harvest, token summing, duplicate detection — against a fixture mirroring a real session |
| `test_agent_engine_client.py` | Interface constants, error classification, stream parsing |
| `test_invoker.py` | Last-chunk answer extraction, usage summing, JSON unwrapping, cancellation |
| `test_metrics.py` | Unknown-metric rejection, executor grouping, unavailability reasons, `argument_match` discrimination, profile selection |

```bash
cd backend && python -m pytest -q
```

Not covered: live GCP calls (they need credentials and cost money), the FastAPI
route layer, and the frontend.

---

## 16. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GCP_PROJECT_ID` | — | Project containing the agents |
| `GCP_REGION` | `us-central1` | Comma-separated list is accepted |
| `DATABASE_URL` | — | `postgresql+asyncpg://…` |
| `INVOKE_CONCURRENCY` | `8` | Concurrent agent invocations |
| `JUDGE_CONCURRENCY` | `6` | Concurrent judge calls |
| `JUDGE_MODEL` | `gemini-2.5-flash` | Shared evaluation judge |
| `JUDGE_TEMPERATURE` | `0.0` | |
| `METRIC_PASS_THRESHOLD` | `0.7` | Mean judged score for a sample to count as passed |
| `EVALUATION_TIMEOUT_SECONDS` | `120` | Per-invocation timeout |
| `CORS_ORIGINS` | empty | Comma-separated; empty means `*` in dev, none in prod |
| `ORPHANED_RUN_TIMEOUT_MINUTES` | `60` | Runs still `running` this long after a restart are failed on boot |

Authentication is **ADC only** — `gcloud auth application-default login`. No
service-account keys are stored anywhere.

---

## 17. Commit history

| Commit | Contents |
|---|---|
| `032acc3` | Phase 1 — invocation compatibility gate |
| `6e7783c` | Phase 2 — deployments inventory and onboarding |
| `0bf887e` | Phase 3 — canonical trace pipeline and invoker |
| `a7aa608` | Phase 4 — datasets from production sessions |
| `38f7f28` | Phase 5 — real DeepEval metrics |
| `8cb6101` | Ops hygiene — orphaned runs, CORS, error leakage, log labelling |
