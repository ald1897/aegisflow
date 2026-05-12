# API Contracts

## Purpose

This document defines the API design standards, endpoint structure, request/response conventions, and contract expectations for AegisFlow.

The API layer exists to provide:
- explicit workflow interaction boundaries
- stable service contracts
- operationally observable interfaces
- strongly typed request/response schemas
- secure system access patterns

APIs should prioritize:
- consistency
- explicitness
- observability
- backward compatibility
- operational clarity

All platform APIs must conform to the standards defined in this document.

---

# API Philosophy

## APIs Are Durable Contracts

APIs represent stable operational interfaces between:
- frontend applications
- orchestration systems
- integrations
- operational tooling

APIs should be treated as long-lived contracts rather than implementation details.

---

## Explicitness Over Convenience

APIs should:
- expose explicit schemas
- use deterministic payload structures
- return structured errors
- surface operational metadata

Avoid:
- hidden side effects
- loosely typed payloads
- overloaded endpoint behavior
- ambiguous response structures

---

## Workflow-Centric Design

The API layer exists primarily to:
- initiate workflows
- inspect workflow state
- manage approvals
- retrieve operational history
- support observability

The API layer is not intended to expose unrestricted AI execution interfaces.

---

# Architectural Context

## Primary API Layer

The primary external API surface is:
- gateway-api

Core technology:
- FastAPI
- OpenAPI
- Pydantic
- Async Python

---

## API Responsibilities

The API layer is responsible for:
- request validation
- authentication
- authorization
- workflow initiation
- orchestration coordination
- operational querying
- streaming updates
- frontend interaction

---

# API Design Standards

# Base Path Convention

All APIs should use versioned base paths.

---

## Example

```text
/api/v1/workflows
/api/v1/approvals
/api/v1/audit
```

---

# Implemented Local API Surface

The current local implementation exposes the following operational endpoints.

## gateway-api

```text
GET /health
GET /ready
POST /api/v1/workflows
GET /api/v1/workflows/{workflow_id}
GET /api/v1/workflows/{workflow_id}/timeline
GET /api/v1/workflows/{workflow_id}/agent-executions
GET /api/v1/workflows/{workflow_id}/tool-invocations
GET /api/v1/reviews/human-review-queue
GET /api/v1/workflows/{workflow_id}/review-context
GET /api/v1/workflows/{workflow_id}/approvals
POST /api/v1/workflows/{workflow_id}/approvals
GET /api/v1/workflows/{workflow_id}/evaluations
```

The gateway-api remains the primary API surface for workflow initiation and operational query access.

The `agent-executions` endpoint returns persisted agent execution records associated with a workflow. It must not expose unrestricted prompt input, sensitive borrower payloads, secrets, or internal persistence entities directly.

The `tool-invocations` endpoint returns persisted governed tool invocation records associated with a workflow. It must expose DTOs containing operational status, validation status, permission status, correlation metadata, and validated output summaries. It must not expose persistence models, secrets, raw document content, or unrestricted borrower PII.

The human review queue endpoint returns workflows currently in `HUMAN_REVIEW_REQUIRED` state for operator review. It must not include completed, failed, approved, rejected, or non-reviewable workflows.

The review context endpoint aggregates workflow-owned review data for an operator:
- workflow record
- timeline entries
- agent execution records
- tool invocation records
- approval records

The approvals retrieval endpoint returns persisted approval records for a workflow through DTOs.

The approval decision endpoint accepts approval or rejection decisions from a human operator. It must require `X-Actor-ID`, reject non-reviewable workflows with structured errors, and route workflow state changes through workflow-engine-owned Temporal decision execution. Gateway handlers must not directly mutate workflow state for approval outcomes.

Current approval decision behavior:
- accepted decisions return the refreshed workflow record, persisted approval record, and workflow-engine decision result
- approved decisions transition the local workflow through `APPROVED` to `COMPLETED`
- rejected decisions transition the local workflow through `REJECTED` to `COMPLETED`
- duplicate or non-reviewable workflow decisions are rejected by workflow review validation
- approval and rejection requests are available to the operator-console and Postman validation collection through gateway-api only

The workflow evaluations endpoint returns persisted evaluation runs and bounded evaluation results associated with a workflow. It is read-only gateway access for operator and Postman ergonomics. It must not create evaluation runs, mutate workflow state, approve or reject workflows, or expose raw prompt content, document contents, borrower PII, secrets, approval comments, or full model outputs.

---

## agent-runtime

```text
GET /health
GET /ready
GET /api/v1/agents
POST /api/v1/agents/{agent_id}/executions
```

The agent-runtime API is an internal service boundary used by workflow-engine activities.

It is not intended as an unrestricted public AI execution interface.

Agent execution requests must:
- include `workflow_id`
- include `correlation_id`
- identify the current workflow state
- use a registered agent identifier
- produce schema-validated structured output

Agent execution responses must:
- identify the agent
- identify the prompt version
- identify the model or deterministic execution profile
- expose validation status
- expose confidence metadata
- preserve whether human review is required
- include governed tool invocation references in telemetry when tools are used

Current Phase 4 agent-runtime tool behavior:
- `intake_agent` may invoke `borrower_profile_lookup`
- `document_analysis_agent` may invoke `document_fetch`
- tool invocations must occur through tool-runtime
- tool invocation telemetry must include tool identifier, invocation identifier, validation status, permission status, and correlation metadata
- tool output remains supporting context and must not be interpreted as final mortgage decision authority

---

## tool-runtime

```text
GET /health
GET /ready
GET /api/v1/tools
POST /api/v1/tools/{tool_id}/invocations
```

The tool-runtime API is an internal governed execution boundary used by agent-runtime.

It is not intended as an unrestricted public integration, database, shell, or HTTP execution interface.

Tool invocation requests must:
- include `workflow_id`
- include `correlation_id`
- identify the requesting `agent_id`
- target a registered `tool_id`
- provide input matching the registered tool schema
- use idempotency metadata where retry safety is required

Tool invocation responses must:
- identify the tool invocation
- identify the requesting agent
- expose execution status
- expose permission status
- expose input and output validation status
- return validated synthetic or masked output
- include telemetry metadata required for workflow persistence and audit correlation

---

## evaluation-service

```text
GET /health
GET /ready
GET /metrics
POST /api/v1/evaluations/workflows/{workflow_id}/runs
GET /api/v1/evaluations/runs/{evaluation_run_id}
GET /api/v1/evaluations/workflows/{workflow_id}/runs
GET /api/v1/evaluations/datasets
GET /api/v1/evaluations/datasets/{dataset_id}/cases
```

The evaluation-service API is an internal quality-governance boundary for local AI evaluation.

Evaluation run creation must:
- read workflow, timeline, agent execution, tool invocation, and approval evidence from persisted workflow records
- execute deterministic local evaluators by default
- persist evaluation run and evaluation result records
- support explicit `evaluation_run_id` idempotency for repeated local validation
- reject missing workflows with `workflow_not_found`
- reject incomplete workflows with `workflow_not_ready_for_evaluation`

Evaluation responses expose run metadata and bounded result records. They must not expose prompt content, raw document contents, borrower PII, secrets, approval comments as scoring metadata, or full model outputs.

Current dataset behavior:
- `mortgage-exception-local-v1` is seeded as the initial local Mortgage Exception Review dataset
- dataset cases include approval, rejection, and human-review scenarios
- evaluation run requests may include `dataset_case_id` to persist `dataset-replay-contract` comparison results
- dataset replay evaluates persisted evidence only and does not invoke workflow replay, agent execution, tool execution, approval dispatch, or recovery behavior

Evaluation results are quality signals only. They must not mutate workflow state, approve or reject workflows, bypass human review, or replace workflow timelines, approval records, or audit records.
