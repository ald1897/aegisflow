# AegisFlow

AegisFlow is a production-style simulation of an enterprise AI orchestration platform for regulated financial workflows.

## Local Runtime

The local runtime currently provides:
- local Postgres persistence
- Redpanda Kafka-compatible event infrastructure
- Redis for future ephemeral coordination
- Temporal workflow orchestration
- Temporal UI
- `gateway-api` with workflow creation and retrieval
- `workflow-engine` with deterministic workflow progression
- workflow timeline retrieval
- workflow event outbox publishing
- structured JSON logging
- correlation ID propagation

## Start Local Infrastructure

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml up --build
```

The Gateway API listens on:

```text
http://localhost:8000
```

Temporal UI listens on:

```text
http://localhost:8088
```

## Manual Smoke Test

Import the Postman collection:

```text
postman/AegisFlow_Local_Runtime.postman_collection.json
```

Use the default collection variable:

```text
baseUrl = http://localhost:8000
```

Recommended request order:
- `Health`
- `Ready`
- `Create Mortgage Exception Review Workflow`
- `Poll Until Human Review Required`
- `Get Workflow Timeline`
- `Missing Workflow Returns 404`

After creation, the Temporal worker advances the workflow to:

```text
HUMAN_REVIEW_REQUIRED
```

See `docs/implementation/CURRENT_FUNCTIONALITY.md` for the full manual validation flow.

## Run Gateway Tests Locally

The host machine must use Python 3.12 or newer for the service package.

```powershell
cd apps/gateway-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## Run Workflow Engine Tests Locally

```powershell
cd apps/workflow-engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```
