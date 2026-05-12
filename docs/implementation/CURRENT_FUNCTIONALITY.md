# Current Functionality

## Purpose

This document summarizes the AegisFlow functionality currently implemented and describes how to manually validate it in the local development environment.

The current implementation includes Phase 1, Phase 2, Phase 3, and initial Phase 4 capabilities:
- local runtime foundation
- workflow persistence
- Temporal workflow orchestration
- deterministic workflow state progression
- workflow timeline storage
- workflow event publication
- governed LangGraph agent runtime
- structured agent output validation
- agent execution record persistence
- governed tool-runtime service boundary
- approved tool registry and schema validation
- deterministic mock tool execution
- workflow-integrated tool invocation persistence

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
- tool-runtime

---

## gateway-api

The gateway API currently supports:
- service health checks
- dependency readiness checks
- workflow creation
- workflow retrieval
- workflow timeline retrieval
- workflow agent execution retrieval
- workflow tool invocation retrieval
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
GET /api/v1/workflows/{workflow_id}/tool-invocations
```

---

## agent-runtime

The agent-runtime currently supports governed local agent execution using LangGraph.

It provides:
- agent registry lookup
- versioned prompt loading
- deterministic local prompt execution simulation
- governed tool-runtime client support
- agent-to-tool permission metadata
- structured output validation
- confidence metadata
- human review requirement metadata

Implemented agents:
- `intake_agent` with approved access to `borrower_profile_lookup`
- `document_analysis_agent` with approved access to `document_fetch`

Implemented endpoints:

```text
GET /health
GET /ready
GET /api/v1/agents
POST /api/v1/agents/{agent_id}/executions
```

The agent-runtime is an internal workflow participant. It does not approve, reject, complete, or mutate workflows directly.

Current Phase 4 agent-runtime capability:
- agents can request approved tools through tool-runtime when `ENABLE_TOOL_RUNTIME` is enabled
- agent outputs remain schema-validated after tool context is used
- agent execution telemetry includes tool invocation references
- tool failures degrade safely without granting agents decision authority

---

## tool-runtime

The tool-runtime currently supports governed internal tool execution for approved mock tools.

It provides:
- registered tool discovery
- agent-to-tool permission enforcement
- request schema validation
- response schema validation
- deterministic mock tool handlers
- replay-safe invocation telemetry
- masked and synthetic operational outputs

Implemented tools:
- `borrower_profile_lookup`
- `document_fetch`
- `fraud_signal_lookup`

Implemented endpoints:

```text
GET /health
GET /ready
GET /api/v1/tools
POST /api/v1/tools/{tool_id}/invocations
```

The tool-runtime is an internal mediation boundary. It does not mutate workflow state, approve mortgage actions, expose arbitrary tools, or call production mortgage systems.

Current Phase 4 capability:
- gateway-api exposes workflow tool invocation history through a DTO-based query endpoint

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

During current workflow execution:
- `intake_agent` runs during `INTAKE_IN_PROGRESS`
- `document_analysis_agent` runs during `DOCUMENT_ANALYSIS_PENDING`
- agent outputs are validated before workflow progression uses them
- agent execution records are persisted for operational traceability
- approved agent tool invocations are persisted as workflow-owned tool invocation records
- tool invocation records produce timeline entries and outbox events

---

# Implemented Persistence

Postgres is the system of record for current workflow data.

Implemented persistence tables include:
- `workflow_records`
- `workflow_state_transitions`
- `workflow_timeline_entries`
- `workflow_event_outbox`
- `agent_execution_records`
- `tool_invocation_records`

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
- tool invocation identity
- tool permission status
- tool input validation status
- tool output validation status
- tool execution metadata

Current tool invocation persistence boundary:
- workflow-engine can idempotently record tool invocation results
- tool invocation records can produce workflow timeline entries
- tool invocation records can produce workflow event outbox records
- agent-produced tool invocation telemetry is persisted during the standard Mortgage Exception Review path
- gateway-api can retrieve persisted workflow tool invocation history

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
- `tool.invocation_completed`
- `tool.invocation_failed`

Current tool invocation event boundary:
- tool invocation events are produced when workflow-engine records agent-produced tool invocation telemetry
- tool invocation events are persisted through the outbox model

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
- tool-runtime health check
- tool-runtime readiness check
- registered tool lookup
- direct governed tool invocation checks
- readiness check
- workflow creation
- workflow retrieval
- polling until `HUMAN_REVIEW_REQUIRED`
- workflow timeline retrieval
- workflow agent execution retrieval
- workflow tool invocation retrieval
- missing workflow error validation

The collection uses `http://localhost:8000` as the default `baseUrl`.
The collection uses `http://localhost:8010` as the default `agentRuntimeUrl`.
The collection uses `http://localhost:8020` as the default `toolRuntimeUrl`.

Recommended collection variables:
- `baseUrl`: `http://localhost:8000`
- `agentRuntimeUrl`: `http://localhost:8010`
- `toolRuntimeUrl`: `http://localhost:8020`
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
- `aegisflow-tool-runtime`

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

## 7. Run Tool Runtime Health

Run the Postman request:

```text
Tool Runtime Health
```

Expected result:
- HTTP status is `200`
- `status` is `ok`
- `service` is `tool-runtime`

---

## 7. Run Tool Runtime Ready

Run the Postman request:

```text
Tool Runtime Ready
```

Expected result:
- HTTP status is `200`
- `status` is `ok`
- `checks.tool_registry` is `ok`
- `registered_tools` is `3`

---

## 8. List Registered Tools

Run the Postman request:

```text
List Registered Tools
```

Expected result:
- HTTP status is `200`
- `borrower_profile_lookup` is registered
- `document_fetch` is registered
- `fraud_signal_lookup` is registered

---

## 9. Invoke Governed Tools Directly

Run the following Postman requests:

```text
Invoke Borrower Profile Lookup
Invoke Document Fetch
Invoke Fraud Signal Lookup
```

Expected result:
- HTTP status is `201`
- `permission_status` is `AUTHORIZED`
- `input_validation_status` is `VALIDATED`
- `output_validation_status` is `VALIDATED`
- output payloads contain synthetic and masked operational data only

---

## 10. Create A Workflow

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

## 11. Poll Workflow Progression

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

## 12. Retrieve The Workflow Timeline

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
- `TOOL_INVOCATION_COMPLETED` entries for governed tool activity
- `EVENT_PUBLISHED` entries for published workflow events

---

## 13. Retrieve Workflow Agent Executions

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
- agent execution telemetry includes governed tool invocation references

---

## 14. Retrieve Workflow Tool Invocations

Run the Postman request:

```text
Get Workflow Tool Invocations
```

Expected result:
- HTTP status is `200`
- `borrower_profile_lookup` invocation is present
- `document_fetch` invocation is present
- each invocation has `status` set to `COMPLETED`
- each invocation has `permission_status` set to `AUTHORIZED`
- each invocation has input and output validation status set to `VALIDATED`

---

## 15. Validate Missing Workflow Behavior

Run the Postman request:

```text
Missing Workflow Returns 404
```

Expected result:
- HTTP status is `404`
- response includes an error detail for the missing workflow

---

## 16. Run The Collection

The collection can be run end-to-end in Postman Collection Runner.

Recommended request order:
- `Health`
- `Agent Runtime Health`
- `List Registered Agents`
- `Tool Runtime Health`
- `Tool Runtime Ready`
- `List Registered Tools`
- `Invoke Borrower Profile Lookup`
- `Invoke Document Fetch`
- `Invoke Fraud Signal Lookup`
- `Ready`
- `Create Mortgage Exception Review Workflow`
- `Poll Until Human Review Required`
- `Get Workflow Timeline`
- `Get Workflow Agent Executions`
- `Get Workflow Tool Invocations`
- `Missing Workflow Returns 404`

---

## 17. Open Temporal UI

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

## 18. Manual Validation Coverage

The Postman collection validates:
- gateway health and readiness
- agent-runtime health
- agent registry availability
- tool-runtime health and readiness
- tool registry availability
- direct governed tool invocation
- database connectivity through the readiness endpoint
- workflow creation persistence
- Temporal workflow startup metadata
- governed agent execution persistence
- governed tool invocation persistence
- deterministic state progression to `HUMAN_REVIEW_REQUIRED`
- workflow timeline retrieval
- workflow agent execution retrieval
- workflow tool invocation retrieval
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
9 passed
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
7 passed
```

---

## tool-runtime Tests

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml run --rm --no-deps `
  -v "${PWD}\apps\tool-runtime\tests:/app/tests" `
  tool-runtime sh -c "pip install --no-cache-dir -e '.[dev]' && pytest"
```

Expected result:

```text
7 passed
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
5 passed
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
