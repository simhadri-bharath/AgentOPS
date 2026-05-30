# AgentOps Platform — Backend (MVP)

FastAPI + PostgreSQL backend for the AI AgentOps Platform. This MVP focuses on **Vertex AI Reasoning Engine discovery**, agent metadata persistence, and REST APIs for the frontend.

## Features

- Async FastAPI with modular `/api/v1` routes
- PostgreSQL via SQLAlchemy 2.0 async (`asyncpg`)
- Alembic migrations
- Vertex AI Reasoning Engine discovery (`reasoning_engines.ReasoningEngine.list`)
- GCP auth via **Application Default Credentials** (`gcloud auth application-default login`)
- Repository pattern for agents
- Structured logging

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| PostgreSQL | 14+ |
| gcloud CLI | Latest |
| GCP project | With Vertex AI Reasoning Engines enabled |

No Docker required for local development.

---

## 1. Project setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On macOS/Linux:

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 2. PostgreSQL setup

### Option A — Local PostgreSQL (Windows)

Install PostgreSQL, then in `psql`:

```sql
CREATE USER agentops WITH PASSWORD 'agentops';
CREATE DATABASE agentops OWNER agentops;
GRANT ALL PRIVILEGES ON DATABASE agentops TO agentops;
```

### Option B — Existing instance

Update `DATABASE_URL` in `.env` to match your instance.

**Connection string format (async):**

```
postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE
```

---

## 3. Environment variables

```powershell
copy .env.example .env
```

Edit `.env`:

```env
APP_NAME=AgentOps Platform
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://agentops:agentops@localhost:5432/agentops

GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1
```

`GCP_PROJECT_ID` must match the project where your Reasoning Engines are deployed (e.g. `ragmanageddb-vertexai` from the reference notebook).

---

## 4. gcloud CLI & GCP authentication

### Install gcloud

https://cloud.google.com/sdk/docs/install

### Login and set project

```powershell
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID
```

### Application Default Credentials (required)

```powershell
gcloud auth application-default login
```

This is the **only** auth method used by the backend. No service account JSON keys.

### Verify ADC

```powershell
gcloud auth application-default print-access-token
```

If this prints a token, ADC is configured.

---

## 5. Database migrations

From `backend/` with venv activated:

```powershell
alembic upgrade head
```

Expected output includes applying revision `001` (agents table).

---

## 6. Run the backend

```powershell
python run.py
```

Or:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

OpenAPI docs: http://127.0.0.1:8000/docs

---

## 7. API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | DB + GCP auth health |
| GET | `/api/v1/agents` | List agents |
| GET | `/api/v1/agents/{agent_id}` | Get agent by UUID |
| POST | `/api/v1/discovery/vertex-ai/sync` | Discover & upsert Reasoning Engines |
| GET | `/api/v1/discovery/vertex-ai/test` | Test Vertex AI connectivity (no DB write) |
| POST | `/api/v1/datasets/upload` | Upload evaluation dataset |
| GET | `/api/v1/datasets` | List datasets |
| POST | `/api/v1/evaluations/run` | Queue evaluation (BackgroundTasks) |
| GET | `/api/v1/evaluations/{id}/results` | Per-sample results |

### Sample: Health check

```powershell
curl http://127.0.0.1:8000/health
```

```json
{
  "status": "healthy",
  "database": "ok",
  "gcp_auth": "ok",
  "version": "0.1.0",
  "details": {
    "database": "ok",
    "gcp_auth": "ok"
  }
}
```

### Sample: Test Vertex AI (no sync)

```powershell
curl http://127.0.0.1:8000/api/v1/discovery/vertex-ai/test
```

```json
{
  "authenticated": true,
  "project_id": "your-gcp-project-id",
  "region": "us-central1",
  "engine_count": 1,
  "message": "Successfully connected. Found 1 reasoning engine(s).",
  "sample_engines": [
    {
      "name": "Travel Planner Agent",
      "endpoint_url": "projects/936666675765/locations/us-central1/reasoningEngines/1913161777202331648",
      "status": "healthy"
    }
  ]
}
```

### Sample: Sync Reasoning Engines

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/discovery/vertex-ai/sync
```

```json
{
  "discovered": 1,
  "created": 1,
  "updated": 0,
  "unchanged": 0,
  "errors": [],
  "agents": [
    {
      "id": "a1b2c3d4-e5f6-5789-a012-3456789abcde",
      "name": "travel-planner-agent",
      "display_name": "Travel Planner Agent",
      "deployment_type": "vertex_ai",
      "endpoint_url": "projects/936666675765/locations/us-central1/reasoningEngines/1913161777202331648",
      "model_name": "gemini-1.5-pro",
      "region": "us-central1",
      "gcp_project": "your-gcp-project-id",
      "status": "healthy",
      "source": "vertex_ai",
      "metadata": {
        "gcp_engine_id": "1913161777202331648",
        "resource_name": "projects/.../reasoningEngines/1913161777202331648",
        "labels": {}
      },
      "discovered_at": "2026-05-29T12:00:00+00:00",
      "last_seen_at": "2026-05-29T12:00:00+00:00",
      "created_at": "2026-05-29T12:00:00+00:00",
      "updated_at": "2026-05-29T12:00:00+00:00"
    }
  ]
}
```

### Sample: List agents

```powershell
curl "http://127.0.0.1:8000/api/v1/agents?limit=100&offset=0"
```

```json
{
  "items": [ ... ],
  "total": 1
}
```

---

## 8. Vertex AI permissions

Your Google account (used with ADC) needs IAM roles on the target project:

| Role | Purpose |
|------|---------|
| `roles/aiplatform.user` | List and access Vertex AI resources |
| `roles/aiplatform.viewer` | Read-only discovery (minimum for list) |

Optional for future evaluation features:

- `roles/storage.objectViewer` (GCS staging)
- `roles/logging.viewer` (Cloud Logging)

Enable APIs:

```powershell
gcloud services enable aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID
```

Reasoning Engines must be deployed in the region set by `GCP_REGION` (default `us-central1`).

---

## 9. Architecture overview

```
backend/
├── app/
│   ├── api/v1/routes/     # HTTP handlers
│   ├── core/              # config, database, logging
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic DTOs
│   ├── services/
│   │   ├── discovery/     # Vertex AI, Cloud Run (stub)
│   │   ├── gcp/           # ADC validation
│   │   └── health/
│   ├── repositories/      # Data access
│   └── main.py
├── alembic/
└── run.py
```

**Discovery flow:**

1. `POST /api/v1/discovery/vertex-ai/sync`
2. Validate ADC → `vertexai.init(project, location)`
3. `reasoning_engines.ReasoningEngine.list()` (same as reference notebook)
4. Parse `resource_name`, `display_name`, labels → `AgentCreate`
5. Upsert into PostgreSQL by `endpoint_url`
6. Mark engines not seen in sync as `inactive`

Agent `id` is a deterministic UUID5 derived from the GCP resource name for stable upserts.

---

## 10. Troubleshooting

### `GCP Application Default Credentials not found`

```powershell
gcloud auth application-default login
```

Restart the API after login.

### `PostgreSQL connection failed`

- Confirm PostgreSQL is running
- Test: `psql -U agentops -d agentops -h localhost`
- Verify `DATABASE_URL` uses `postgresql+asyncpg://` (not `postgresql://` alone)

### `Vertex AI discovery failed` / 502

- Confirm `GCP_PROJECT_ID` and `GCP_REGION` match deployed engines
- Check IAM: `gcloud projects get-iam-policy YOUR_PROJECT_ID`
- Enable API: `aiplatform.googleapis.com`
- Run test endpoint first: `GET /api/v1/discovery/vertex-ai/test`

### `No reasoning engines found`

- Engines may be in a different region — update `GCP_REGION`
- List in Cloud Console: Vertex AI → Reasoning Engines

### Alembic errors

Ensure you run commands from `backend/` and `.env` is loaded:

```powershell
$env:PYTHONPATH = "."
alembic upgrade head
```

### Import errors when starting

Run from `backend/` directory or set:

```powershell
$env:PYTHONPATH = "."
```

---

## 11. Development commands (cheat sheet)

```powershell
# venv
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# env
copy .env.example .env

# db
alembic upgrade head

# gcp
gcloud auth application-default login

# run
python run.py
```

---

## 12. Evaluation pipeline (MVP)

### Flow

1. Upload a dataset (CSV or JSON)
2. Discover agents (`POST /api/v1/discovery/vertex-ai/sync`)
3. Start an evaluation run (`POST /api/v1/evaluations/run`) — returns `202` with `status: queued`
4. FastAPI `BackgroundTasks` invokes each sample via Vertex AI `Client.evals.run_inference` (notebook pattern)
5. Simple metrics computed per sample; aggregates stored on `evaluation_runs`
6. Poll `GET /api/v1/evaluations/{id}` and `GET /api/v1/evaluations/{id}/results`

### Required: evaluation dependencies

Agent invocation uses `Client.evals.run_inference` (same as the reference notebook). Install the **evaluation extra**:

```powershell
pip install "google-cloud-aiplatform[evaluation]>=1.74.0"
```

Or reinstall all requirements:

```powershell
pip install -r requirements.txt
```

Without this, evaluations complete with `invocation_error` mentioning `google-cloud-aiplatform[evaluation]` and all metrics score 0.

### Apply migration

```powershell
alembic upgrade head
```

Applies revision `002` (datasets, evaluation_runs, evaluation_results).

### Sample datasets

- `sample_datasets/eval_sample.csv`
- `sample_datasets/eval_sample.json`

### Upload dataset

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/datasets/upload `
  -F "file=@sample_datasets/eval_sample.csv" `
  -F "name=travel-eval-v1" `
  -F "description=Sample travel prompts"
```

```json
{
  "dataset": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "travel-eval-v1",
    "format": "csv",
    "row_count": 3,
    "file_path": "..."
  },
  "message": "Dataset uploaded successfully"
}
```

### Start evaluation

Replace `AGENT_ID` and `DATASET_ID` from list endpoints:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/evaluations/run `
  -H "Content-Type: application/json" `
  -d "{\"agent_id\":\"AGENT_ID\",\"dataset_id\":\"DATASET_ID\",\"framework\":\"vertex_ai\",\"metrics\":[\"exact_match\",\"contains_expected\",\"response_length\",\"latency_ms\"]}"
```

```json
{
  "evaluation_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "queued"
}
```

### Get results

```powershell
curl http://127.0.0.1:8000/api/v1/evaluations/EVALUATION_ID
curl http://127.0.0.1:8000/api/v1/evaluations/EVALUATION_ID/results
curl http://127.0.0.1:8000/api/v1/agents/AGENT_ID/evaluations
```

Example aggregate scores:

```json
{
  "aggregate_scores": {
    "total_passed": 2,
    "total_failed": 1,
    "total_samples": 3,
    "avg_exact_match": 0.33,
    "avg_contains_expected": 0.67,
    "avg_latency_ms": 4200
  }
}
```

### Supported metrics (MVP)

| Metric | Description |
|--------|-------------|
| `exact_match` | 1.0 if actual equals expected (case-insensitive) |
| `contains_expected` | 1.0 if expected substring in actual |
| `response_length` | Character count of response |
| `latency_ms` | Invocation latency per sample |

### Evaluation API routes

| Method | Path |
|--------|------|
| POST | `/api/v1/datasets/upload` |
| GET | `/api/v1/datasets` |
| GET | `/api/v1/datasets/{dataset_id}` |
| DELETE | `/api/v1/datasets/{dataset_id}` |
| POST | `/api/v1/evaluations/run` |
| GET | `/api/v1/evaluations` |
| GET | `/api/v1/evaluations/{evaluation_id}` |
| GET | `/api/v1/evaluations/{evaluation_id}/results` |
| GET | `/api/v1/agents/{agent_id}/evaluations` |

### Status values

`queued` → `running` → `completed` | `failed`

---

## 13. Not in scope (MVP)

- Docker / Kubernetes
- Redis / Celery / Kafka
- User authentication / RBAC
- Ragas / DeepEval / Vertex managed rubric eval (placeholder only)
- Traces / OTEL
- Cloud Run discovery (stub only)

---

## License

Internal PoC — AgentOps Platform.
