# AgentOPS — Evaluation & Red-Teaming Platform for AI Agents

AgentOPS evaluates AI agents deployed on **Google Vertex AI Agent Engine** (Reasoning Engines).
It finds the agents you have deployed, runs them with real prompts, collects the full execution trace,
and scores both the final answer and every sub-agent inside it. It can also attack an agent with
red-team prompts and report which ones got through.

> **Latest code:** the current version of AgentOPS (the rebuilt trace pipeline, DeepEval/RAGAS metrics and DeepTeam red-teaming)
> is on the [`feature/agent-engine-eval`](https://github.com/simhadri-bharath/AgentOPS/tree/feature/agent-engine-eval) branch. `main` still holds an earlier version.

Nothing in the agent has to change: no instrumentation, no redeploy, no API keys.
Everything runs on Google Application Default Credentials, and the judge is Gemini on Vertex AI.

## What it does

- **Discovers deployed agents** across regions and onboards them in one click, after checking that each one can actually be invoked.
- **Invokes agents and collects traces**, then converts Google's event schema into one framework-agnostic format: agent, tool and LLM spans.
- **Scores answers and each sub-agent** with DeepEval and RAGAS metrics, plus deterministic trace-health checks that need no LLM.
- **Builds evaluation datasets from production sessions**, so you don't need a hand-written test set to start.
- **Red-teams agents** with the DeepTeam attack catalogue, classifying each response with rule checks plus a Gemini judge, and links every failure to its trace.
- **Compares runs** and records token usage and estimated cost for every run.

## How it works

```
Vertex AI Agent Engine
        │
AgentEngineClient  ──►  AgentEngineInvoker   (invoke · batch · cancel · harvest trace)
        │
   AgentEvent[]  ──►  TraceNormalizer  ──►  Trace + Spans (agent / tool / LLM)
        │
  EvaluationCase   ← the only thing metric executors see
        │
 ┌──────────────┬───────────────┬──────────────┐
 deterministic   trace health     DeepEval / RAGAS
 └──────────────┴───────────────┴──────────────┘
        │
  EvaluationRun + EvaluationResult  (PostgreSQL)
```

Only one module understands Google's event schema. Everything after the normalizer works on
the standard trace types, so supporting another agent platform means writing a new normalizer,
not new metrics.

## Tech stack

| Layer | Technologies |
|---|---|
| Backend | Python, FastAPI (async), SQLAlchemy 2.0, Alembic, PostgreSQL |
| Agents & tracing | Vertex AI Agent Engine, Google ADK, Cloud Trace |
| Evaluation | DeepEval, RAGAS, Gemini as LLM judge |
| Red teaming | DeepTeam |
| Frontend | React, Vite, TanStack Query, React Flow, Recharts, Tailwind CSS |
| Testing | pytest |

## Getting started

Clone the latest branch first:

```bash
git clone -b feature/agent-engine-eval https://github.com/simhadri-bharath/AgentOPS.git
cd AgentOPS
```

**You need:** Python 3.11+, Node.js, PostgreSQL 14+, the gcloud CLI, and a GCP project with
agents deployed on Vertex AI Agent Engine.

```bash
# 1. Authenticate with Google (the only auth the platform uses)
gcloud auth application-default login

# 2. Backend
cd backend
cp .env.example .env          # set DATABASE_URL, GCP_PROJECT_ID, GCP_REGION
pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd ../frontend
cp .env.example .env
npm install
npm run dev
```

Open the app, check `GET /health` (it shows the configured project and region), then go to
**Deployments** to onboard your first agent.

> The most common problem is pointing at the wrong GCP project. If Deployments is empty, check that first.
> Every run costs agent and judge tokens, so start with a small dataset.

## Documentation

- [User guide](https://github.com/simhadri-bharath/AgentOPS/blob/feature/agent-engine-eval/docs/USER_GUIDE.md): setup, onboarding, running evaluations and red-team scans
- [Implementation notes](https://github.com/simhadri-bharath/AgentOPS/blob/feature/agent-engine-eval/docs/IMPLEMENTATION.md): architecture, metric layer, data model, roadmap
- [Red-team architecture](https://github.com/simhadri-bharath/AgentOPS/blob/feature/agent-engine-eval/docs/redteam_architecture.md)
- [Backend setup](https://github.com/simhadri-bharath/AgentOPS/blob/feature/agent-engine-eval/backend/README.md)

## Running tests

```bash
cd backend
pytest
```
