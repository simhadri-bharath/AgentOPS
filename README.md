# AgentOps

Evaluate AI agents deployed to **Google Vertex AI Agent Engine**.

Browse what is deployed, onboard an agent in one click, and score it — not just
on its final answer, but on the tools it called, the documents it retrieved, and
each sub-agent inside it.

```
Deployments  →  Onboard  →  Test  →  Dataset  →  Evaluate  →  Scores per sub-agent
```

- **[Getting started](#getting-started)** — running it for the first time
- **[User guide](docs/USER_GUIDE.md)** — how to operate it and what it can tell you
- **[Implementation](docs/IMPLEMENTATION.md)** — architecture, decisions, roadmap
- **[Invocation compatibility](docs/invocation_compatibility.md)** — how the Agent
  Engine interface was chosen, and what was measured

---

## What it does

| | |
|---|---|
| **Discovers** | Reads Agent Engines live from your GCP project — no registry to maintain |
| **Classifies** | Infers agent type and capabilities from tools and sub-agents actually observed in its sessions |
| **Invokes** | Calls the real deployed agent and harvests the full execution trace |
| **Scores** | Real DeepEval judged metrics, deterministic checks, and trace health |
| **Attributes** | Scores each sub-agent, so a low result names a component rather than "the agent" |
| **Bootstraps** | Builds evaluation datasets from the agent's own production sessions |
| **Red-teams** | Adversarial scans via DeepTeam |

It requires **no changes to your agent**. Nothing is instrumented, nothing
redeployed. It reads what Agent Engine already records.

---

## Getting started

### 1. Prerequisites

| | |
|---|---|
| Python | 3.11+ |
| Node | 18+ |
| PostgreSQL | 14+, reachable |
| GCP | A project with Agent Engines, and `roles/aiplatform.user` |

### 2. Authenticate

```bash
gcloud auth application-default login
```

There are **no API keys to create**. No OpenAI key, no service-account JSON file.
The evaluation judge is Gemini on Vertex AI and runs on the same credentials.

> Tokens expire. When they do, every evaluation fails with `AUTH_ERROR` and a
> message telling you to run this again.

### 3. Configure

```bash
cd backend
cp .env.example .env
```

Set at minimum:

```ini
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/agentops
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1          # comma-separated list also accepted
```

> **Most common mistake:** the wrong project. If Deployments is empty, check the
> project shown in the sidebar first.

### 4. Install and run

```bash
# Backend — from backend/
pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000

# Frontend — from frontend/, in a second terminal
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). The dev server
proxies `/api` and `/health` to port 8000, so no frontend config is needed.

### 5. Check it is healthy

```bash
curl http://127.0.0.1:8000/health
```

```json
{
  "status": "healthy",
  "database": "ok",
  "gcp_auth": "ok",
  "details": { "gcp_project": "your-project-id", "gcp_region": "us-central1" }
}
```

`gcp_auth: ok` and the right project means you are ready.

### 6. First run, in five minutes

1. **Deployments** — your Agent Engines appear, with the tools and sub-agents
   observed in their recent sessions.
2. **Onboard** — pick an environment (required), confirm the proposed type, and
   **Run test** *before* saving. A green result with the tools you expect means
   the agent is reachable and understood.
3. **Agents → your agent → Build dataset from sessions** — turns real traffic
   into evaluation cases, including the documents the agent retrieved.
4. **Datasets → Review** — fill in what a correct answer should say. Promotion to
   golden is refused until every row is decided.
5. **New Evaluation** — the metric pack for your agent's type is pre-selected.
   Run it.
6. **Job details** — scores with the judge's reasoning, cost, and a breakdown per
   sub-agent.

Start with a handful of samples. A retrieval turn takes 30–45 seconds and every
run spends real tokens.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Deployments empty | Wrong project or region | Check `/health` → `details.gcp_project` |
| Everything `AUTH_ERROR` | ADC expired | `gcloud auth application-default login` |
| Traces / Logs return 502 | `google-cloud-trace` missing | `pip install -r requirements.txt` |
| Agent shows `conversational` but is RAG | Retrieval is internal, so no tool call is visible | Agent page → **Edit profile** → set `rag` + `retrieval` |
| RAG metrics unavailable | No retrieval context | Run a test invoke; if it retrieved 0 documents, the tool response shape is unrecognised |
| Run stuck after a restart | Background tasks die with the process | The startup sweep fails it; use **Retry** |
| Cannot promote to golden | Rows missing expected output | Datasets → Review. The gate is deliberate |

Fuller table in the [user guide](docs/USER_GUIDE.md#part-6--troubleshooting).

---

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | Async Postgres URL |
| `GCP_PROJECT_ID` | — | Project containing the agents |
| `GCP_REGION` | `us-central1` | Comma-separated list accepted |
| `INVOKE_CONCURRENCY` | `8` | Concurrent agent invocations |
| `JUDGE_MODEL` | `gemini-2.5-flash` | Evaluation judge |
| `JUDGE_CONCURRENCY` | `6` | Concurrent judge calls |
| `METRIC_PASS_THRESHOLD` | `0.7` | Mean score for a sample to pass |
| `EVALUATION_TIMEOUT_SECONDS` | `120` | Per-invocation timeout |
| `CORS_ORIGINS` | empty | Comma-separated; empty means `*` in dev |

---

## Tests

```bash
cd backend && python -m pytest -q
```

Covers trace normalization against a real session fixture, tool classification,
the metric registry, invoker behaviour, and run comparison. Live GCP calls are
not covered — they need credentials and cost money.

---

## Project layout

```
backend/
  app/api/v1/routes/     HTTP endpoints
  app/services/
    gcp/                 Agent Engine REST client
    invokers/            Invocation, trace harvest, cancellation
    discovery/           Live deployment inventory
    evaluation/          Normalizer, metric registry, executors, runner
    datasets/            Upload, validation, session bootstrap, row review
  alembic/versions/      Migrations
  tests/
frontend/src/
  pages/                 Deployments, Agents, Datasets, Evaluation, Jobs, Traces, Red team
  components/            Shared UI
  api/                   Backend client
docs/
```
