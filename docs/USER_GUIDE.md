# AgentOps — User Guide

How to run the platform, what it can tell you about your agents, and what you need
to have in hand before you start.

For architecture and roadmap, see [IMPLEMENTATION.md](IMPLEMENTATION.md).

---

## Part 1 — What you need before you start

### 1.1 Access and credentials

| What | Why | How to check |
|---|---|---|
| **Google ADC** with `aiplatform.user` on the project | Every call to the agent and to the judge runs on it | `gcloud auth application-default print-access-token` |
| **The GCP project ID** containing your Agent Engines | Nothing appears if this is wrong | `gcloud config get-value project` |
| **The region** your agents are deployed in | Default `us-central1`; a comma-separated list is accepted | Vertex AI console → Agent Engine |
| **PostgreSQL** reachable | Stores agents, datasets, runs, results | `psql "$DATABASE_URL" -c 'select 1'` |

There are **no API keys to obtain**. No OpenAI key, no service-account JSON. The
judge is Gemini on Vertex AI and runs on the same ADC.

> **The single most common failure is pointing at the wrong project.** The sidebar
> shows the configured project; if the Deployments page is empty, check that first.

### 1.2 Knowledge you need about each agent

The platform infers what it can, but three things are judgement calls only you can
make. Have answers ready before onboarding:

| Question | Why it matters | Default if you skip it |
|---|---|---|
| **What is this agent for?** (one or two sentences) | Feeds the judge's criteria and, later, red-team targeting | A description derived from the display name |
| **Which environment is it?** dev / staging / production | Required at onboarding. Red-team gating keys off it. | None — you must choose |
| **What type is it?** RAG / tool-calling / conversational / task / multi-agent | Decides the recommended metric pack | Inferred from observed tool calls; see §2.3 |

### 1.3 What you do NOT need

- A test dataset. You can build one from the agent's own production sessions.
- Reference trajectories. Same — they are seeded from real traffic.
- Any change to the deployed agent. Nothing is instrumented, nothing redeployed.
- A public URL. There isn't one; the reasoning engine ID is the whole address.

### 1.4 What it costs

Two kinds of spend, both real:

- **Agent invocations.** One per sample. A retrieval turn on the live chat agent
  used ~28,000 input and ~1,900 output tokens.
- **Judge calls.** One per LLM-judged metric per sample, **plus** one per
  sub-agent span for span-capable metrics. Six metrics over six samples with two
  spans each produced 25 metric evaluations and 10 span evaluations.

Every run records both and shows an estimated cost. **Start with a small dataset.**

---

## Part 2 — Running it

### 2.1 Start

```bash
# Backend
cd backend
pip install -r requirements.txt   # google-cloud-trace is easy to miss; without
                                  # it the Traces and Logs pages return 502
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm run dev
```

Check `GET /health` — it reports the database, ADC, and **which project and region
are configured**.

### 2.1a Finding your way around

The sidebar has five groups. **Deployments → Agents → Datasets → Evaluations**
is the whole path from "nothing set up" to "first score".

| Group | What is there |
|---|---|
| Platform | Dashboard, Deployments, Agents |
| Evaluation | Datasets, Evaluations, Compare runs |
| Security | Red team |
| Observability | Traces, Logs |
| Setup | Getting started, Settings |

Creating things happens from buttons on the page that lists them — **New
evaluation** on Evaluations, **Configure scan** on Red team — rather than from
separate menu entries.

On a fresh install the Dashboard shows a three-step guide instead of empty
charts, and marks off each step as you complete it.

### 2.2 See what is deployed

Open **Deployments**. It reads Vertex AI live and writes nothing.

```
DEPLOYMENTS · Agent Engine        steptoe-surplus-lines-499008 · us-central1

  Steptoe Chat Agent V1           google-adk   50+ sessions   active 2d ago
      multi_agent · retrieval, tool_use, multi_agent
      tools: search_documents                                    [Onboard]

  Survey Analysis Agent V2        google-adk   50+ sessions   active 3d ago
      conversational · none in 3 session(s)                      [Onboard]

  Survey  Agent v1 dev            google-adk    2 sessions   never used
      conversational · none in 2 session(s)                      [Onboard]
```

Each row shows what the platform could observe:

- **Framework** from the engine spec
- **Session count and last activity**, newest first
- **Observed tools**, read from up to 3 recent sessions
- **Proposed type and capabilities**, inferred from those tools and the sub-agent
  authors seen in the traces

### 2.3 Onboard an agent

Click **Onboard**. The drawer is pre-filled from what was observed; you confirm or
correct it.

**Read the proposal critically.** It reports only what is *observable*:

- The chat agent proposes `multi_agent` with `[retrieval, tool_use]` because
  `search_documents` calls and a `research_agent → formatter_agent` handoff are
  visible in its traces. That is correct.
- The Survey agents propose `conversational` with no capabilities, because their
  retrieval happens **inside** the agent (Discovery Engine grounding) and never
  surfaces as a `functionCall` event. **If you know they are RAG agents, set
  `rag` and tick `retrieval` manually.** The platform will not guess without
  evidence.

**Environment is required and has no default.** Pick honestly — it is the gate
that later protects production agents from destructive red-team runs.

**Run test before saving.** The drawer takes a prompt and invokes the live
deployment without writing anything, so you can confirm the agent is reachable
and behaves as expected before it enters the registry. After saving, the drawer
stays open so you can test again immediately.

**If the proposal is wrong, fix it.** Type and capabilities are editable at
onboarding and afterwards on the agent page under **Edit profile**. They decide
which metrics are recommended, so an agent left as `unknown` will only ever be
offered baseline metrics.

### 2.4 Test before you commit to a run

Test in the onboard drawer **before** you save, or later from the agent page.
Either way you get the whole trace back from one real prompt:

```
state: SUCCESS · latency: 30086 ms · tokens 28447 / 1905
agent_path: research_agent → formatter_agent
trajectory: search_documents(states=["Illinois"], query="surplus lines premium tax…")
retrieval docs: 39
spans: tool/research_agent/retrieval · agent/research_agent · agent/formatter_agent
health: tool_success 1.0 · no_redundant_calls 1.0 · no_loop 1.0 · step_efficiency 0.67
```

**Check three things here:**

1. `state` is `SUCCESS`, not `AUTH_ERROR` or `AGENT_ERROR`
2. `retrieval docs` is non-zero **if this is a RAG agent** — zero means the tool
   response shape was not recognised, and RAG metrics will report themselves
   unavailable
3. `trajectory` lists the tools you expect

A misconfiguration caught here costs one invocation. Caught during a 50-sample run
it costs 50.

### 2.5 Build a dataset from production traffic

On the agent page, **Build dataset from sessions**.

It walks recent sessions and extracts one case per turn:

| Field | Where it comes from |
|---|---|
| `input` | What the user actually asked |
| `actual_output` | What the agent answered |
| `retrieval_context` | Documents the agent actually retrieved |
| `reference_trajectory` | Tools it actually called, in order |
| `conversation` | Earlier turns in the same session |
| `category` | Auto-labelled: `happy_path`, `multi_turn`, `long_context`, `edge_case`, `tool_failure`, `retrieval_failure`, `failure_case` |
| `expected_output` | **Blank — you fill this in** |

Sessions created by AgentOps itself are excluded automatically. On the live agent
this skipped 8 of 25 sessions; without it, the platform's own test traffic would
be scored as production usage.

**The category distribution is shown for a reason.** A set that is 40 happy paths
will score 95% and tell you nothing. Aim for a spread: happy paths, edge cases,
and the failures you already know about. Twenty to fifty well-chosen cases beat
hundreds of near-duplicates.

#### Why `expected_output` is blank

A captured trajectory records what the agent **did**, not what it **should have
done**. The dataset saves as `needs_review`, and **promotion to `golden` is
refused while any row lacks `expected_output`**. Otherwise a bug the agent had
last Tuesday becomes the baseline you measure against forever.

Lifecycle:

```
BOOTSTRAPPED → NEEDS_REVIEW → HUMAN_REVIEWED → GOLDEN
```

### 2.6 Run an evaluation

**New Evaluation** → pick agent → pick dataset → pick framework → metrics.

The metrics step loads the catalogue from the backend and pre-selects the pack for
your agent's type and capabilities:

```
Recommended for multi_agent · retrieval, tool_use, multi_agent
An end-to-end score says something broke, not which sub-agent broke it,
so the pack is scored per span as well as per trace.
```

Each metric is labelled:

- **recommended** — in this agent's pack
- **needs reference** — requires `expected_output` or a reviewed
  `reference_trajectory`
- **per sub-agent** — will also be scored on each span
- **cost** — free / low / medium / high

Override freely. The pack is a default, not a gate.

### 2.7 Read the results

#### Run level

```
avg_answer_relevancy        0.9773
avg_faithfulness            0.9458
avg_tool_correctness        0.55
avg_argument_match          0.55
avg_trace_no_redundant_calls 1.0

p50_latency_ms   39027      p95_latency_ms   47614
total_samples    6          total_invoked    5      total_failed  1
total_passed     5          pass_threshold   0.7
states           SUCCESS 5 · AGENT_ERROR 1
```

**`states` is the first thing to read.** One sample here failed to invoke at all —
that is an agent availability problem, not an answer-quality problem, and it is not
scored.

#### Run profile

The panel at the top of a job shows what the run cost and how it went:
invoked/total, passed, latency p50/p95, estimated cost, agent tokens, tool and
LLM calls, and judge evaluations split into metric and per-sub-agent.

**When any sample failed to reach the agent, that is shown first.** Clean
averages over a partly failed run hide exactly that. `JUDGE_ERROR` is called out
separately because it is a scoring failure, not an agent failure.

Underneath is the run snapshot — judge model, invocation interface, dataset
version and review status, metric config version — which is what makes the score
interpretable months later.

#### Sample level

Each sample shows scores with the judge's reasoning:

> **faithfulness 0.9615** — *"the actual output incorrectly implies the Fire
> Marshal Tax is due within 30 days after filing the report for direct
> procurement…"*

That is a judgement about content. The old implementation returned `0.0` or `1.0`
from a substring check — this is the difference.

#### Per sub-agent

```
Whole trace     answer_relevancy 0.9688
research_agent  answer_relevancy 0.4062   faithfulness 1.0
formatter_agent answer_relevancy 1.0      faithfulness 1.0
```

**This is the most useful panel in the product.** The trace looks fine; the
research step is weak and the formatter is covering for it. Fix the research
prompt, not the formatter.

#### Controls on a run

A running job can be **cancelled** — it keeps what it completed. Any
non-running job can be **deleted** with its results. On **History**,
**Compare runs** diffs two runs metric by metric, per sub-agent and per sample,
and warns when the harness moved between them.

#### Not scored

Metrics whose inputs were missing appear separately, with the reason:

> **Contextual precision** — *expected_output is missing. Add it to the dataset,
> or review a bootstrapped dataset and fill it in.*

**Unavailable is never reported as zero.** "No expected output" and "the agent got
it wrong" are different findings.

---

## Part 3 — What you can identify with this

### 3.1 Answer quality

| Question | Metric |
|---|---|
| Does it answer what was asked? | `answer_relevancy` |
| Is the answer supported by what it retrieved? | `faithfulness` |
| Does it contradict its own sources? | `hallucination` |
| Does it match the known-correct answer? | `correctness` |
| Did it achieve the user's goal? | `task_completion` |

### 3.2 Retrieval quality — RAG agents

Two frameworks measure this, by different methods. DeepEval metrics are
unprefixed; RAGAS metrics are prefixed `ragas_`. They are kept separate on
purpose — averaging them would hide which produced a number. Running both on
the same dataset is a useful cross-check when a score looks surprising.

| Question | Metric |
|---|---|
| Are the relevant documents ranked above the irrelevant ones? | `contextual_precision` |
| Did retrieval find everything the answer needed? | `contextual_recall` |
| Did retrieval return anything usable at all? | Case category `retrieval_failure` |
| Same questions, second opinion | `ragas_faithfulness`, `ragas_context_precision`, `ragas_context_recall`, `ragas_answer_relevancy`, `ragas_response_groundedness` |

### 3.3 Tool use and trajectory

| Question | Metric |
|---|---|
| Did it call the right tools, in the right order? | `tool_correctness`, `trajectory_in_order_match` |
| Did it call them with the **right arguments**? | `argument_match` |
| Did it call tools it shouldn't have? | `trajectory_precision` |
| Did it miss tools it should have called? | `trajectory_recall` |

`argument_match` is the one people miss. Two calls to `search_documents` score
identically on every name-based metric whether the query was right or wrong — and
for a search agent, the query it chose *is* most of the quality signal.

### 3.4 Execution health — no reference data needed

These run on every sample, cost nothing, and need no dataset work:

| Question | Metric |
|---|---|
| Did any tool call fail? | `trace_tool_success_rate` |
| Did it call the same tool twice with identical arguments? | `trace_no_redundant_calls` |
| Is it stuck in a loop? | `trace_no_loop` |
| Is it taking more steps than the task needs? | `trace_step_efficiency` |
| Did it answer at all? | `trace_answered` |

`trace_no_redundant_calls` already has something to find in production — the chat
agent calls `search_documents` twice within one turn on some questions.

### 3.5 Which component is at fault

For multi-agent systems, span scores attribute a low result to a specific
sub-agent. This is what an end-to-end number cannot do.

### 3.6 Operational profile

| Question | Where |
|---|---|
| How slow is it, really? | `p50_latency_ms` / `p95_latency_ms` — measured per request |
| How many tokens does a turn cost? | `usage.agent_tokens_in` / `out` |
| How many tool and LLM calls per turn? | `usage.agent_tool_calls` / `agent_llm_calls` |
| What did evaluating it cost? | `usage.agent_cost_usd_estimate`, `judge_metric_evaluations` |
| Is the agent reachable and healthy? | `states` breakdown on the run |

### 3.7 Security posture

| Question | Where |
|---|---|
| Can the agent be talked out of its instructions? | Red team, jailbreak and prompt-injection vulnerabilities |
| Will it leak its system prompt or user PII? | `PromptLeakage`, `PIILeakage` |
| Can its tools be abused? | `ToolOrchestrationAbuse`, `ExcessiveAgency`, `UnexpectedCodeExecution` |
| Can it be made to act as another agent? | `AgentIdentityAbuse` |
| Does it meet a published standard? | Framework presets — OWASP, NIST, MITRE, EU AI Act |

### 3.8 What it cannot tell you

Be clear about the boundaries:

- **Whether the agent is *right* in the real world.** The judge compares against
  retrieved context and your `expected_output`. If both are wrong, the score is
  confidently wrong too.
- **Whether a bootstrapped reference is correct.** It records what happened, not
  what should have.
- **Anything about a metric reported unavailable.** That is a gap in the dataset,
  not a result.
- **Regression over time** — not yet. The run snapshot makes it possible; the
  comparison view is not built.

---

## Part 4 — Reading a run correctly

### 4.1 Check the states first

`states: SUCCESS 5 · AGENT_ERROR 1` means one sample never got an answer. That is
an availability problem. Quality metrics on the other five say nothing about it.

| State | Means | Do |
|---|---|---|
| `SUCCESS` | Invoked and harvested | Read the scores |
| `AGENT_ERROR` | Agent errored or returned nothing | Check agent logs in GCP |
| `AUTH_ERROR` | ADC or IAM | Re-run `gcloud auth application-default login` |
| `RATE_LIMITED` | Quota | Lower `INVOKE_CONCURRENCY` |
| `TIMEOUT` | Exceeded the per-invocation limit | Raise `EVALUATION_TIMEOUT_SECONDS` |
| `HARVEST_ERROR` | Answered, but events unreadable | Scores may be missing trajectory |
| `JUDGE_ERROR` | Agent fine, **judge** failed | **Not an agent problem.** Check judge model and quota. |

`JUDGE_ERROR` is called out separately for a reason: it used to be indistinguishable
from an agent failure, which sends you debugging the wrong system.

### 4.2 Check the run snapshot before comparing runs

Every run records the judge model, framework versions, dataset version and review
status, and the invocation interface. **If any of those differ between two runs,
the difference in scores may be the harness, not the agent.**

### 4.3 Check the dataset's review status

A run against a `needs_review` dataset is a *baseline capture*, not a quality
verdict. Only a `golden` set — where every row has a human-approved
`expected_output` — supports statements like "quality dropped".

### 4.4 Check the category mix

If the run is 90% `happy_path`, a high score means the easy cases pass. It does
not mean the agent is good.

---

## Part 5 — Red teaming

Evaluation asks whether the agent is *good*. Red teaming asks whether it can be
*made to misbehave*. Both run against the live deployed agent.

### 5.1 Pick a standard, not a checklist

The scan wizard offers 37 vulnerabilities and 28 attacks, derived from the
installed DeepTeam rather than a hand-maintained list. Assembling those by hand
is rarely what you want.

**Choose a framework preset instead.** DeepTeam maps the standard to its own
vulnerabilities and attacks:

| Preset | Covers |
|---|---|
| `OWASPTop10` | OWASP Top 10 for LLMs 2025 |
| `OWASP_ASI_2026` | OWASP Top 10 for Agentic Applications 2026 |
| `NIST` | NIST AI Risk Management Framework |
| `MITRE` | MITRE ATLAS |
| `EUAIAct` | EU Artificial Intelligence Act |
| `Aegis`, `BeaverTails` | Dataset-based safety suites |

Picking one drops the wizard from six steps to four. **For a tool-using agent,
`OWASP_ASI_2026` is the one to start with** — it targets the agentic
vulnerabilities (goal theft, recursive hijacking, tool orchestration abuse,
unexpected code execution, agent identity abuse) that a generic LLM standard
does not cover.

### 5.2 The two scan modes

| Mode | What it does | When |
|---|---|---|
| **Custom** | Runs a fixed library of attack prompts, judged by rules plus an LLM | Fast, repeatable, cheap. Good for regression. |
| **Dynamic** (DeepTeam) | Generates attacks tailored to the agent's stated purpose, including multi-turn | Thorough. Slower and costs more. |

Dynamic mode uses `agent.purpose`, so an agent with a vague purpose gets vague
attacks. Set it properly on the agent page.

### 5.3 Scans are long, and stoppable

Every attack is a full agent round-trip plus judge calls. Against a 40-second
retrieval agent, a broad scan takes a long time. Two things follow:

- Attacks run concurrently, tuned by `REDTEAM_CONCURRENCY`.
- **A running scan can be cancelled.** It stops, keeps the findings it already
  produced, and reports `cancelled` with how far it got — for example
  *"Cancelled after 1 of 5 attack(s)"*. A stopped scan is never reported as
  completed, because partial coverage must not read as a clean result.

**Start narrow.** One category, or one framework, against a dev agent.

### 5.4 Reading findings

Each finding carries the attack prompt, the agent's answer, a classification,
a severity, the judge's reasoning, and the **real invocation trace** — the
sub-agent path and the tools that were called. A finding is a place to look,
not just a verdict.

| Classification | Meaning |
|---|---|
| `PASS` | The agent resisted |
| `FAIL` | The agent complied with the attack |
| `UNCERTAIN` | The judge could not decide — read it yourself |

Severity comes from the same thresholds that produce the classification, served
by `GET /api/v1/redteam/meta/scoring`, so the colour on a finding always agrees
with its verdict:

```
critical >= 85    high >= 65    medium >= 45    low >= 35
```

### 5.5 Safety

These scans send hostile prompts to a **real deployed agent**. They run under a
dedicated `agentops-redteam` user and delete their sessions afterwards, so they
do not pollute production session history — but the agent really does receive
them, and any tool it calls really executes.

Set `environment` honestly at onboarding, and prefer a dev or staging agent for
your first scan.

---

## Part 6 — Recommended first week

**Day 1 — See and verify**
1. Set `GCP_PROJECT_ID`, run migrations, start both services
2. Open Deployments; confirm all your agents appear
3. Onboard one agent; correct its type if the inference was conservative
4. Test invoke — confirm `SUCCESS`, non-zero retrieval docs, expected tools

**Day 2 — Baseline with zero dataset effort**
5. Run with trace-health metrics only. Free, no reference data, and it will tell
   you about failed tool calls, redundant calls and loops immediately.

**Day 3 — Build the golden set**
6. Build a dataset from sessions, 20–50 cases
7. Open **Datasets**, click **Review**, and fill in `expected_output` per row.
   Rows that still block promotion are highlighted, and the filter shows only
   unreviewed ones.
8. **Promote to golden.** It is refused, naming the count, until every row is
   decided.

**Day 4 — Full evaluation**
9. Run the recommended pack against the golden set
10. Read span scores; identify the weak sub-agent
11. Record the run's aggregate scores as your baseline

**Day 5 — Security**
14. Run a red-team scan with `OWASP_ASI_2026` against a **dev** agent first.
    Start narrow and cancel it if it runs longer than you expected.
15. Read the findings: each carries the real trace, so a `FAIL` points at the
    sub-agent and tool that let it through.

**Ongoing**
12. Re-run after every agent change, against the same dataset version
13. On **History**, use **Compare runs** to diff against the baseline. Read the
    warnings first: if the judge model or dataset version changed, the delta is
    the harness moving, not the agent.

Two controls worth knowing: a running job can be **cancelled** from its detail
page (partial results are kept, not discarded), and any non-running job can be
**deleted** with its results.

---

## Part 7 — Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Deployments page empty | Wrong project or region | Check `/health` → `details.gcp_project` |
| `AUTH_ERROR` on every sample | ADC expired | `gcloud auth application-default login` |
| RAG metrics all unavailable | Retrieval context empty | Test invoke; if `retrieval docs: 0`, the tool response shape is unrecognised — see `tool_kinds.py` |
| Agent type proposed as `conversational` for a known RAG agent | Retrieval happens inside the agent, not as a tool call | Set `rag` + `retrieval` at onboarding, or later via agent page → **Edit profile** |
| Everything `TIMEOUT` | Agent slower than the limit | Raise `EVALUATION_TIMEOUT_SECONDS` |
| `RATE_LIMITED` | Too much concurrency | Lower `INVOKE_CONCURRENCY` and `JUDGE_CONCURRENCY` |
| Run stuck in `running` after a restart | Background tasks die with the process | The startup sweep fails it automatically; use **Retry** |
| `400 Unknown metric(s)` | A metric name not in the registry | Read `GET /api/v1/evaluations/meta/metrics` for valid names |
| Cannot promote to `golden` | Rows missing `expected_output` | Datasets → Review → fill each row. The gate is deliberate |
| Comparison says "not directly comparable" | Judge, dataset version or metric config differs between the runs | Re-run the baseline under current settings, or treat the delta as indicative only |
| Dataset version jumped several numbers | Every row edit is a new version | Expected — a run snapshots the version it used |
| Red-team catalogue returns 503 | `deepteam` not installed | `pip install -r requirements.txt` |
| RAGAS metrics all report an error | `ragas` not installed | `pip install -r requirements.txt` |
| `ragas_context_recall` unavailable | It needs `expected_output` | Review the dataset and fill it in |
| Scan rejected with "Unknown vulnerability" | A name not in the installed DeepTeam | The error lists the valid names; or pick a framework preset instead |
| Severity colours changed on old findings | The UI used its own thresholds and disagreed with the backend | Expected — bands now come from `GET /redteam/meta/scoring` |
| Scan runs for a very long time | Every attack is an agent round-trip plus judge calls | Cancel it; narrow the scope; raise `REDTEAM_CONCURRENCY` |
| Agent missing from a run/scan dropdown | It is inactive — usually from a different GCP project | It stays on the Agents page; re-onboard it if the project is right |
| App feels hung on first load | Was a blocking health check; fixed | If it recurs, check `/health` response time |
| Judge errors on `tool_correctness` | Judge not passed to the metric | Fixed; if it recurs, check `JUDGE_MODEL` is reachable in your region |
| Traces / Logs pages show 502 | `google-cloud-trace` not installed | `pip install -r requirements.txt` — it is declared but easy to miss |

---

## Part 8 — Glossary

| Term | Meaning |
|---|---|
| **Deployment** | An Agent Engine as it exists in GCP. Read-only until onboarded. |
| **Agent** | An onboarded deployment with type, capabilities, purpose and environment. |
| **Trace** | One turn: the prompt, every tool call and sub-agent step, and the final answer. Grouped by `invocationId`. |
| **Span** | One step inside a trace — a sub-agent, a tool call, or an LLM call. Scoreable in its own right. |
| **Trajectory** | The ordered list of tool calls and their arguments. |
| **Retrieval context** | Documents the agent retrieved, harvested from retrieval-classified tool responses. |
| **Reference trajectory** | The tool sequence an ideal agent would have used. Seeded from production, then reviewed. |
| **Golden dataset** | A dataset where every row has a human-approved `expected_output`. |
| **Judge** | Gemini on Vertex AI, scoring LLM-judged metrics. |
| **Span metric** | A metric scored on individual sub-agents as well as the whole trace. |
| **`ragas_` prefix** | The metric is computed by RAGAS rather than DeepEval. Kept separate so the two are never averaged together. |
| **Framework preset** | A published standard (OWASP, NIST, MITRE, EU AI Act) that DeepTeam maps to its own vulnerabilities and attacks. |
| **Custom / Dynamic scan** | Fixed attack library versus attacks generated for the agent's stated purpose. |
| **Classification** | A red-team verdict: `PASS` resisted, `FAIL` complied, `UNCERTAIN` undecided. |
| **Invocation state** | Why a sample did or did not produce a result: `SUCCESS`, `AGENT_ERROR`, `AUTH_ERROR`, `JUDGE_ERROR`, `TIMEOUT`, `RATE_LIMITED`, `HARVEST_ERROR`, `CANCELLED`. |
