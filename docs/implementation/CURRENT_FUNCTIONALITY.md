# Current Functionality

## Purpose

This document summarizes the AegisFlow functionality currently implemented and describes how to manually validate it in the local development environment.

The current implementation includes Phase 1, Phase 2, and Phase 3 capabilities:
- local runtime foundation
- workflow persistence
- Temporal workflow orchestration
- deterministic workflow state progression
- workflow timeline storage
- workflow event publication
- governed LangGraph agent runtime
- structured agent output validation
- agent execution record persistence

---

# Implemented Runtime Components

## Local Infrastructure

The local Docker Compose stack currently runs:
- Postgres
- Redpanda/Kafka-compatible event streaming
- Redis
- Temporal
- Temporal UI
- gateway-api
- workflow-engine
- agent-runtime

---

## gateway-api

The gateway API currently supports:
- service health checks
- dependency readiness checks
- workflow creation
- workflow retrieval
- workflow timeline retrieval
- workflow agent execution retrieval
- correlation ID propagation
- structured JSON logs
- Temporal workflow startup
- workflow event publication for workflow creation

Implemented endpoints:

```text
GET /health
GET /ready
POST /api/v1/workflows
GET /api/v1/workflows/{workflow_id}
GET /api/v1/workflows/{workflow_id}/timeline
GET /api/v1/workflows/{workflow_id}/agent-executions
```

---

## agent-runtime

The agent-runtime currently supports governed local agent execution using LangGraph.

It provides:
- agent registry lookup
- versioned prompt loading
- deterministic local prompt execution simulation
- structured output validation
- confidence metadata
- human review requirement metadata

Implemented agents:
- `intake_agent`
- `document_analysis_agent`

Implemented endpoints:

```text
GET /health
GET /ready
GET /api/v1/agents
POST /api/v1/agents/{agent_id}/executions
```

The agent-runtime is an internal workflow participant. It does not approve, reject, complete, or mutate workflows directly.

---

## workflow-engine

The workflow-engine currently runs as a Temporal worker.

It supports the Mortgage Exception Review workflow, invokes governed agents, and advances workflows deterministically through:

```text
NEW
INTAKE_IN_PROGRESS
DOCUMENT_ANALYSIS_PENDING
RISK_REVIEW_PENDING
HUMAN_REVIEW_REQUIRED
```

The workflow stops at `HUMAN_REVIEW_REQUIRED` because human approval handling is not implemented yet.

During Phase 3 execution:
- `intake_agent` runs during `INTAKE_IN_PROGRESS`
- `document_analysis_agent` runs during `DOCUMENT_ANALYSIS_PENDING`
- agent outputs are validated before workflow progression uses them
- agent execution records are persisted for operational traceability

---

# Implemented Persistence

Postgres is the system of record for current workflow data.

Implemented persistence tables include:
- `workflow_records`
- `workflow_state_transitions`
- `workflow_timeline_entries`
- `workflow_event_outbox`
- `agent_execution_records`

Current persisted data includes:
- workflow identity
- workflow type
- current workflow state
- priority
- workflow metadata
- correlation ID
- Temporal workflow ID
- Temporal run ID
- state transition history
- timeline entries
- workflow event publication status
- agent identity
- prompt version
- agent validation status
- agent confidence score
- agent output metadata

---

# Implemented Events

Workflow events are persisted through an outbox table and published to Redpanda.

Current event topic:

```text
workflow-events
```

Current event types:
- `workflow.created`
- `workflow.state_changed`
- `agent.execution_completed`

Event publication status is tracked in:

```text
workflow_event_outbox
```

Successful local publication sets outbox records to:

```text
PUBLISHED
```

---

# Not Implemented Yet

The following capabilities are intentionally not implemented yet:
- tool-runtime mediation
- human approval UI
- approve/reject actions
- workflow completion after human review
- distributed tracing stack
- AI evaluation
- authentication and RBAC
- advanced replay tooling

---

# Manual Local Test With Postman

## Postman Collection

An importable Postman collection is available at:

```text
postman/AegisFlow_Local_Runtime.postman_collection.json
```

The collection includes:
- health check
- agent-runtime health check
- registered agent lookup
- readiness check
- workflow creation
- workflow retrieval
- polling until `HUMAN_REVIEW_REQUIRED`
- workflow timeline retrieval
- workflow agent execution retrieval
- missing workflow error validation

The collection uses `http://localhost:8000` as the default `baseUrl`.
The collection uses `http://localhost:8010` as the default `agentRuntimeUrl`.

Recommended collection variables:
- `baseUrl`: `http://localhost:8000`
- `agentRuntimeUrl`: `http://localhost:8010`
- `correlationId`: `postman-manual-test`
- `actorId`: `postman-operator`

The collection automatically captures:
- `workflowId`
- `temporalWorkflowId`
- `temporalRunId`

---

## 1. Start The Local Runtime

From the repository root:

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml up --build -d
```

Confirm all containers are running:

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml ps
```

Expected services:
- `aegisflow-postgres`
- `aegisflow-redpanda`
- `aegisflow-redis`
- `aegisflow-temporal`
- `aegisflow-temporal-ui`
- `aegisflow-gateway-api`
- `aegisflow-workflow-engine`
- `aegisflow-agent-runtime`

---

## 2. Import The Collection

Import the following collection into Postman:

```text
postman/AegisFlow_Local_Runtime.postman_collection.json
```

Confirm the `baseUrl` collection variable is set to:

```text
http://localhost:8000
```

---

## 3. Run Health

Run the Postman request:

```text
Health
```

Expected result:
- HTTP status is `200`
- `status` is `ok`
- `service` is `gateway-api`
- `environment` is `local`

---

## 4. Run Ready

Run the Postman request:

```text
Ready
```

Expected result:
- HTTP status is `200`
- `status` is `ok`
- `service` is `gateway-api`
- `checks.database` is `ok`

---

## 5. Run Agent Runtime Health

Run the Postman request:

```text
Agent Runtime Health
```

Expected result:
- HTTP status is `200`
- `status` is `ok`
- `service` is `agent-runtime`

---

## 6. List Registered Agents

Run the Postman request:

```text
List Registered Agents
```

Expected result:
- HTTP status is `200`
- `intake_agent` is registered
- `document_analysis_agent` is registered

---

## 7. Create A Workflow

Run the Postman request:

```text
Create Mortgage Exception Review Workflow
```

Expected result:
- HTTP status is `201`
- `workflow_id` is present
- `workflow_type` is `MORTGAGE_EXCEPTION_REVIEW`
- `state` is initially `NEW`
- `correlation_id` matches the Postman `correlationId` variable
- `temporal_workflow_id` is present
- `temporal_run_id` is present

The request test script stores the created `workflow_id` as the `workflowId` collection variable.

---

## 8. Poll Workflow Progression

Run the Postman request:

```text
Poll Until Human Review Required
```

Expected final result:
- HTTP status is `200`
- `workflow_id` matches the captured `workflowId`
- `state` becomes `HUMAN_REVIEW_REQUIRED`

When run through the Postman Collection Runner, this request will poll until the workflow reaches `HUMAN_REVIEW_REQUIRED` or the configured retry limit is reached.

When running requests manually with Send, use:

```text
Get Workflow
```

Repeat the request until `state` is:

```text
HUMAN_REVIEW_REQUIRED
```

---

## 9. Retrieve The Workflow Timeline

Run the Postman request:

```text
Get Workflow Timeline
```

Expected timeline entries include:
- `WORKFLOW_CREATED`
- `STATE_TRANSITION` to `INTAKE_IN_PROGRESS`
- `STATE_TRANSITION` to `DOCUMENT_ANALYSIS_PENDING`
- `STATE_TRANSITION` to `RISK_REVIEW_PENDING`
- `STATE_TRANSITION` to `HUMAN_REVIEW_REQUIRED`
- `AGENT_EXECUTION_COMPLETED` entries for governed agent activity
- `EVENT_PUBLISHED` entries for published workflow events

---

## 10. Retrieve Workflow Agent Executions

Run the Postman request:

```text
Get Workflow Agent Executions
```

Expected result:
- HTTP status is `200`
- `intake_agent` execution is present
- `document_analysis_agent` execution is present
- each execution has `validation_status` set to `VALIDATED`
- each execution references prompt version metadata

---

## 11. Validate Missing Workflow Behavior

Run the Postman request:

```text
Missing Workflow Returns 404
```

Expected result:
- HTTP status is `404`
- response includes an error detail for the missing workflow

---

## 12. Run The Collection

The collection can be run end-to-end in Postman Collection Runner.

Recommended request order:
- `Health`
- `Agent Runtime Health`
- `List Registered Agents`
- `Ready`
- `Create Mortgage Exception Review Workflow`
- `Poll Until Human Review Required`
- `Get Workflow Timeline`
- `Get Workflow Agent Executions`
- `Missing Workflow Returns 404`

---

## 13. Open Temporal UI

Open:

```text
http://localhost:8088
```

Expected:
- Temporal UI loads
- namespace `default` is available
- workflow executions are visible
- Mortgage Exception Review workflow executions can be inspected

---

## 14. Manual Validation Coverage

The Postman collection validates:
- gateway health and readiness
- agent-runtime health
- agent registry availability
- database connectivity through the readiness endpoint
- workflow creation persistence
- Temporal workflow startup metadata
- governed agent execution persistence
- deterministic state progression to `HUMAN_REVIEW_REQUIRED`
- workflow timeline retrieval
- workflow agent execution retrieval
- missing workflow error behavior

Direct Postgres, Redpanda, and Temporal history inspection is not required for routine manual API testing.

---

# Automated Test Commands

## gateway-api Tests

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml run --rm --no-deps `
  -e ENABLE_TEMPORAL_START=false `
  -e ENABLE_EVENT_PUBLISHING=false `
  -v "${PWD}\apps\gateway-api\tests:/app/tests" `
  gateway-api sh -c "pip install --no-cache-dir -e '.[dev]' && pytest"
```

Expected result:

```text
7 passed
```

---

## agent-runtime Tests

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml run --rm --no-deps `
  -v "${PWD}\apps\agent-runtime\tests:/app/tests" `
  agent-runtime sh -c "pip install --no-cache-dir -e '.[dev]' && pytest"
```

Expected result:

```text
5 passed
```

---

## workflow-engine Tests

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml run --rm --no-deps `
  -v "${PWD}\apps\workflow-engine\tests:/app/tests" `
  workflow-engine sh -c "pip install --no-cache-dir -e '.[dev]' && pytest"
```

Expected result:

```text
2 passed
```

---

# Stop The Local Runtime

To stop containers while preserving local volumes:

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml down
```

To stop containers and remove local volumes:

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml down -v
```

Use `down -v` only when local database and event data can be discarded.
