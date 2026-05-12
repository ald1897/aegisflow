# Phase 4 Implementation Plan

## Purpose

This document defines the continuous implementation plan for Phase 4 of AegisFlow.

Phase 4 introduces the Tool Runtime MVP.

The plan exists to:
- guide implementation work across multiple development sessions
- preserve architectural alignment with existing platform documentation
- keep tool execution governed, observable, and replay-aware
- prevent AI agents from accessing integrations directly
- provide clear validation checkpoints before Phase 4 is considered complete

This document must be updated as implementation progresses.

---

# Phase 4 Objective

Phase 4 will introduce governed AI-to-system interaction.

The platform must support approved tools that agents may request through controlled runtime mediation.

The Tool Runtime must:
- expose a registry of approved tools
- validate tool inputs and outputs
- enforce agent-to-tool permissions
- mediate access to mock enterprise integrations
- persist auditable tool invocation records
- emit workflow timeline entries and events
- preserve workflow-engine ownership of workflow state

Agents may use tools as constrained workflow participants.

Agents must not:
- discover arbitrary tools dynamically
- call integrations directly
- mutate workflow state
- approve, reject, or complete mortgage workflows
- bypass workflow-engine orchestration

---

# Business Context

## Current Business Capability

AegisFlow can currently demonstrate governed mortgage exception workflow intake, local deterministic agent execution, and durable progression to human review.

Current Phase 3 capability proves:
- a mortgage exception review case can be created
- the workflow can run durably through Temporal
- intake and document analysis agents can produce validated structured outputs
- agent execution metadata can be persisted and retrieved
- human review remains required before critical business action

## Phase 4 Business Goal

Phase 4 will demonstrate how AI assistance can safely retrieve supporting mortgage context through approved business tools.

For mortgage stakeholders, this means AegisFlow will begin to show how an exception review workflow can gather relevant case context without allowing AI to operate as an uncontrolled system actor.

Examples of business context to simulate:
- borrower profile summary
- supporting document availability
- fraud or compliance signal summary

## Business Boundary

Phase 4 will not connect to real mortgage production systems.

Phase 4 will not perform final underwriting, exception approval, denial, or compliance decisions.

Mock integrations will be used to simulate enterprise systems while preserving the architecture expected for future real adapters.

---

# Current Implementation Baseline

Phase 4 starts from the completed Phase 3 baseline.

Implemented runtime services:
- `gateway-api`
- `workflow-engine`
- `agent-runtime`
- Postgres
- Redpanda
- Redis
- Temporal
- Temporal UI

Implemented persisted records:
- `workflow_records`
- `workflow_state_transitions`
- `workflow_timeline_entries`
- `workflow_event_outbox`
- `agent_execution_records`

Implemented workflow behavior:
- `NEW`
- `INTAKE_IN_PROGRESS`
- `DOCUMENT_ANALYSIS_PENDING`
- `RISK_REVIEW_PENDING`
- `HUMAN_REVIEW_REQUIRED`

Implemented agents:
- `intake_agent`
- `document_analysis_agent`

Phase 4 must extend this baseline without replacing existing workflow ownership boundaries.

---

# Target Phase 4 Scope

## In Scope

Phase 4 should implement:
- `tool-runtime` service
- tool registry
- tool execution endpoint
- tool permission enforcement
- input schema validation
- output schema validation
- deterministic mock tool handlers
- tool invocation persistence
- tool invocation retrieval API
- workflow timeline entries for tool activity
- tool invocation events through the existing outbox pattern
- agent-runtime integration with approved tools
- workflow-engine orchestration updates where needed
- Postman requests for manual validation
- automated tests for tool-runtime, agent-runtime, gateway-api, and workflow-engine impacts
- documentation updates

---

## Out Of Scope

Phase 4 must not implement:
- real mortgage system connectivity
- real borrower data retrieval
- unrestricted database access tools
- arbitrary HTTP tools
- shell or infrastructure execution tools
- autonomous agent tool discovery
- human approval UI
- approve or reject workflow actions
- workflow completion after human review
- production identity provider integration
- full distributed tracing stack
- AI evaluation scoring

---

# Proposed Runtime Architecture

## Service Addition

Add a new service:

```text
apps/tool-runtime
```

The service should be containerized and added to:

```text
infrastructure/local-dev/docker-compose.yml
```

Expected local endpoint:

```text
http://localhost:8020
```

---

## Service Responsibilities

The `tool-runtime` service owns:
- registered tool definitions
- tool permission checks
- request schema validation
- response schema validation
- deterministic mock tool execution
- tool execution telemetry metadata

The `tool-runtime` service must not:
- mutate workflow state
- call workflow-engine state transition APIs directly
- expose unrestricted infrastructure or database access
- allow agents to execute unregistered tools
- persist authoritative workflow state

---

## Initial Communication Flow

```text
Workflow Engine
    ->
Agent Runtime
    ->
Tool Runtime
    ->
Mock Integration Handler
```

The workflow-engine remains responsible for:
- workflow sequencing
- state transitions
- Temporal execution
- replay-safe orchestration
- persistence coordination for workflow-owned records

The agent-runtime remains responsible for:
- agent execution
- context assembly
- prompt version usage
- structured agent outputs
- requesting approved tools through tool-runtime

The tool-runtime remains responsible for:
- validating and executing approved tools
- returning structured tool results
- exposing tool telemetry metadata

---

# Initial Tool Set

## borrower_profile_lookup

Purpose:
- simulate retrieval of borrower profile context needed during mortgage exception review

Initial input:
- `workflow_id`
- `correlation_id`
- `case_reference`

Initial output:
- borrower profile status
- masked borrower reference
- occupancy type
- loan channel
- profile completeness
- validation status

Constraints:
- must not expose real PII
- must use deterministic mock data
- must return only minimum operational context required for workflow demonstration

---

## document_fetch

Purpose:
- simulate retrieval of available mortgage document metadata

Initial input:
- `workflow_id`
- `correlation_id`
- `case_reference`
- requested document types

Initial output:
- available document types
- missing document types
- document metadata summary
- validation status

Constraints:
- must not store or return raw document content
- must not perform OCR or production document parsing
- must return metadata only

---

## fraud_signal_lookup

Purpose:
- simulate retrieval of high-level fraud or compliance signals relevant to risk review preparation

Initial input:
- `workflow_id`
- `correlation_id`
- `case_reference`

Initial output:
- signal status
- risk indicators
- review recommendation
- validation status

Constraints:
- must not make final fraud determinations
- must not approve or reject a workflow
- must preserve human review for critical decisions

---

# Data Model Additions

## Tool Invocation Records

Phase 4 should add a durable record aligned with `DATA_MODEL.md`.

Suggested table:

```text
tool_invocation_records
```

Required conceptual fields:
- `tool_invocation_id`
- `workflow_id`
- `correlation_id`
- `agent_execution_id`
- `agent_id`
- `tool_id`
- `status`
- `permission_status`
- `input_validation_status`
- `output_validation_status`
- `input_metadata`
- `output_payload`
- `execution_metadata`
- `error_message`
- `created_by`
- `started_at`
- `completed_at`
- `created_at`

The table should store operational metadata and validated outputs.

It must not store:
- secrets
- unrestricted borrower PII
- raw document contents
- unclassified integration payloads

---

# Event Additions

Phase 4 should add events through the existing outbox model.

Expected event types:

```text
tool.invocation_completed
tool.invocation_failed
```

Events must include:
- `event_id`
- `event_type`
- `event_version`
- `workflow_id`
- `correlation_id`
- `tool_invocation_id`
- `agent_execution_id`
- `agent_id`
- `tool_id`
- validation status
- execution status

Tool events must describe operational facts.

They must not be commands or hidden implementation signals.

---

# API Additions

## tool-runtime Internal API

Expected endpoints:

```text
GET /health
GET /ready
GET /api/v1/tools
POST /api/v1/tools/{tool_id}/invocations
```

The tool-runtime API is an internal service boundary.

It is not intended as a public unrestricted tool execution API.

---

## gateway-api Operational Query API

Expected endpoint:

```text
GET /api/v1/workflows/{workflow_id}/tool-invocations
```

This endpoint should return persisted tool invocation records for a workflow.

The response must use DTOs and must not expose persistence models directly.

---

# Agent Runtime Changes

Phase 4 should update agent-runtime so agents can request approved tools.

Expected changes:
- add tool client configuration
- add tool permission metadata to agent registry
- invoke tool-runtime only for registered tools
- validate tool responses before using them in agent output
- include tool invocation references in agent execution telemetry

Initial agent tool access:
- `intake_agent` may use `borrower_profile_lookup`
- `document_analysis_agent` may use `document_fetch`
- future risk review behavior may use `fraud_signal_lookup`

Agents must continue to produce structured outputs.

Tool output must support agent reasoning, but must not become final business truth without validation and human review where required.

---

# Workflow Engine Changes

Phase 4 should preserve the existing workflow states unless implementation evidence shows a state addition is required.

Expected workflow behavior:
- workflow-engine starts the Mortgage Exception Review workflow
- workflow enters `INTAKE_IN_PROGRESS`
- intake agent executes and may request approved tools through agent-runtime
- workflow enters `DOCUMENT_ANALYSIS_PENDING`
- document analysis agent executes and may request approved tools through agent-runtime
- workflow enters `RISK_REVIEW_PENDING`
- workflow enters `HUMAN_REVIEW_REQUIRED`

The workflow-engine must remain the only component that advances workflow state.

Tool results must not directly mutate workflow state.

---

# Implementation Workstreams

## Workstream 1 - Tool Runtime Service

Status: Completed

Tasks:
- create `apps/tool-runtime` - Complete
- add FastAPI application - Complete
- add service configuration - Complete
- add Dockerfile - Complete
- add health endpoint - Complete
- add readiness endpoint - Complete
- add tool registry endpoint - Complete
- add tool invocation endpoint - Complete
- add unit tests - Complete

Completion criteria:
- service builds in Docker - Met
- service starts locally on port `8020` - Met
- tests validate tool registry and invocation behavior - Met

---

## Workstream 2 - Tool Registry And Contracts

Status: Completed

Tasks:
- define tool registry model - Complete
- define tool permission model - Complete
- define request and response schemas - Complete
- implement input validation - Complete
- implement output validation - Complete
- define deterministic mock handlers - Complete

Completion criteria:
- each initial tool has explicit input and output schemas - Met
- invalid input fails safely - Met
- unregistered tool invocation is rejected - Met
- unauthorized agent-to-tool pairing is rejected - Met

---

## Workstream 3 - Persistence And Events

Status: Completed

Tasks:
- add Alembic migration for `tool_invocation_records` - Complete
- add persistence models to gateway-api and workflow-engine as needed - Complete
- add tool invocation timeline entry type - Complete
- add tool invocation event types - Complete
- persist tool invocation records - Complete
- add outbox records for completed and failed tool invocations - Complete

Completion criteria:
- tool invocation records are queryable by workflow - Met
- tool invocation completion emits an outbox event - Met
- timeline includes tool invocation entries - Met
- writes are idempotent for retry-safe execution - Met

---

## Workstream 4 - Agent Runtime Integration

Status: Completed

Tasks:
- add tool-runtime client to agent-runtime - Complete
- add tool access metadata to agent registry - Complete
- update intake agent to request `borrower_profile_lookup` - Complete
- update document analysis agent to request `document_fetch` - Complete
- include tool invocation references in agent execution telemetry - Complete
- preserve structured output validation - Complete

Completion criteria:
- agents only call tools listed in their registry permissions - Met
- agent outputs remain schema-valid - Met
- tool failures degrade safely - Met
- agent execution records retain tool context references - Met

---

## Workstream 5 - Workflow Integration

Status: Completed

Tasks:
- update workflow-engine configuration for tool-runtime where needed - Complete
- ensure Temporal activity retry behavior remains bounded - Complete
- ensure workflow progression remains deterministic - Complete
- ensure tool invocation side effects are replay-safe - Complete

Completion criteria:
- Mortgage Exception Review workflow completes Phase 4 path to `HUMAN_REVIEW_REQUIRED` - Met
- workflow state progression remains owned by workflow-engine - Met
- duplicate activity execution does not duplicate completed tool invocation records - Met

---

## Workstream 6 - Gateway API And Postman

Status: Not Started

Tasks:
- add `GET /api/v1/workflows/{workflow_id}/tool-invocations`
- update Postman collection with tool-runtime health and registry requests
- update Postman collection with workflow tool invocation retrieval
- update manual validation documentation

Completion criteria:
- Postman can validate tool-runtime availability
- Postman can validate registered tools
- Postman can validate persisted workflow tool invocation records

---

## Workstream 7 - Documentation And Roadmap Updates

Status: Not Started

Tasks:
- update `CURRENT_FUNCTIONALITY.md`
- update `IMPLEMENTATION_ROADMAP.md`
- update `API_CONTRACTS.md`
- update `EVENT_CATALOG.md`
- update `INTEGRATION_MODEL.md` if implementation details refine the tool mediation model
- update `SECURITY_MODEL.md` if new enforcement decisions are added

Completion criteria:
- documentation describes implemented behavior, not aspirational behavior
- Phase 4 completion log is added after validation
- business-facing boundary remains clear for mortgage stakeholders

---

# Validation Plan

## Automated Tests

Expected test suites:
- tool-runtime tests
- agent-runtime tests
- gateway-api tests
- workflow-engine tests

Minimum validation:
- registered tools are listed
- unregistered tools are rejected
- unauthorized tool access is rejected
- valid tool invocations return schema-valid output
- invalid tool input returns structured errors
- tool invocation records are persisted
- gateway can retrieve workflow tool invocation records
- workflow reaches `HUMAN_REVIEW_REQUIRED`
- agent outputs remain validated after tool use

---

## Manual Postman Validation

Expected Postman requests:
- Tool Runtime Health
- List Registered Tools
- Invoke Borrower Profile Lookup
- Invoke Document Fetch
- Invoke Fraud Signal Lookup
- Create Mortgage Exception Review Workflow
- Poll Until Human Review Required
- Get Workflow Timeline
- Get Workflow Agent Executions
- Get Workflow Tool Invocations

Expected manual result:
- workflow reaches `HUMAN_REVIEW_REQUIRED`
- timeline includes tool invocation activity
- agent execution records remain validated
- tool invocation records are persisted and retrievable

---

# Risk Register

## Risk 1 - Tool Runtime Becomes An Unrestricted Execution Surface

Mitigation:
- only registered tools are executable
- tool requests must match explicit schemas
- agent-to-tool permissions must be enforced
- arbitrary HTTP, shell, database, or infrastructure tools are prohibited

---

## Risk 2 - Tool Results Are Treated As Final Business Truth

Mitigation:
- tool outputs remain supporting context
- workflow-engine owns progression
- human review remains required
- documentation and response models must distinguish tool signals from decisions

---

## Risk 3 - Mock Integrations Drift From Future Enterprise Boundaries

Mitigation:
- mock handlers must emulate adapter boundaries
- mock outputs must use stable schemas
- integration metadata must be captured
- no workflow logic should depend on unmediated mock internals

---

## Risk 4 - Sensitive Data Is Over-Collected

Mitigation:
- use masked and synthetic data only
- store metadata summaries, not raw documents
- avoid borrower PII in logs, events, and tool payloads
- classify data fields before persistence

---

## Risk 5 - Replay Creates Duplicate Tool Side Effects

Mitigation:
- use stable idempotency keys
- persist tool invocation records with deterministic identifiers where practical
- keep Phase 4 tools read-only and deterministic
- avoid irreversible external actions

---

# Phase 4 Completion Criteria

Phase 4 is complete when:
- `tool-runtime` runs in local Docker Compose
- initial tool registry is implemented
- initial mock tools execute with schema validation
- agent-runtime invokes approved tools through tool-runtime
- tool invocation records are persisted
- gateway-api exposes workflow tool invocation history
- workflow timeline includes tool invocation activity
- tool invocation events are written through the outbox model
- Mortgage Exception Review reaches `HUMAN_REVIEW_REQUIRED`
- Postman validates the Phase 4 path
- automated tests pass for impacted services
- documentation and roadmap are updated

---

# Running Status Log

## 2026-05-11

Status:
- Phase 4 planning started
- Continuous implementation plan created

Next step:
- implement Workstream 1: Tool Runtime Service

## 2026-05-12

Status:
- implemented `tool-runtime` as a dedicated FastAPI service
- added Docker Compose support for local execution on port `8020`
- implemented health, readiness, tool registry, and governed invocation endpoints
- implemented explicit tool registry entries for `borrower_profile_lookup`, `document_fetch`, and `fraud_signal_lookup`
- implemented agent-to-tool permission enforcement
- implemented input and output schema validation for all initial tools
- implemented deterministic mock tool handlers using synthetic and masked operational data
- validated local service startup, readiness, tool discovery, and borrower profile invocation through HTTP
- validated tool-runtime automated tests with 7 passing tests

Completed workstreams:
- Workstream 1 - Tool Runtime Service
- Workstream 2 - Tool Registry And Contracts

Next step:
- implement Workstream 3: Persistence And Events

## 2026-05-12 - Workstream 3

Status:
- added Alembic migration `20260512_0004` for `tool_invocation_records`
- added gateway-api and workflow-engine persistence models for tool invocation records
- added tool invocation event types `tool.invocation_completed` and `tool.invocation_failed`
- added tool invocation timeline entry types `TOOL_INVOCATION_COMPLETED` and `TOOL_INVOCATION_FAILED`
- added workflow-engine `record_tool_invocation` activity for idempotent record, timeline, and outbox creation
- added workflow service query support for tool invocation records by workflow
- applied the migration successfully against local Postgres
- validated the local table shape in Postgres
- validated gateway-api automated tests with 8 passing tests
- validated workflow-engine automated tests with 4 passing tests

Completed workstream:
- Workstream 3 - Persistence And Events

Boundary:
- agent-runtime does not yet invoke tool-runtime during workflow execution
- gateway-api does not yet expose the workflow tool invocation retrieval endpoint
- end-to-end workflow production of tool invocation records remains assigned to Workstreams 4, 5, and 6

Next step:
- implement Workstream 4: Agent Runtime Integration

## 2026-05-12 - Workstream 4

Status:
- added agent-runtime tool client configuration for `TOOL_RUNTIME_URL` and `ENABLE_TOOL_RUNTIME`
- added governed tool-runtime client to agent-runtime
- updated agent registry tool permissions for `intake_agent` and `document_analysis_agent`
- updated `intake_agent` to request `borrower_profile_lookup`
- updated `document_analysis_agent` to request `document_fetch`
- preserved registered tool access only; dynamic tool discovery remains prohibited
- added tool invocation references to agent execution telemetry
- preserved structured Pydantic output validation after tool context use
- wired local Docker Compose agent-runtime to tool-runtime
- validated agent-runtime automated tests with 7 passing tests
- validated live agent-runtime HTTP execution against tool-runtime for intake and document analysis agents

Completed workstream:
- Workstream 4 - Agent Runtime Integration

Boundary:
- workflow-engine does not yet record agent-produced tool invocation telemetry into `tool_invocation_records`
- standard Mortgage Exception Review execution can receive agent telemetry with tool references, but Workstream 5 must connect that telemetry to workflow persistence
- gateway-api workflow tool invocation retrieval remains assigned to Workstream 6

Next step:
- implement Workstream 5: Workflow Integration

## 2026-05-12 - Workstream 5

Status:
- connected agent-produced tool invocation telemetry to workflow-engine persistence
- recorded governed tool invocations immediately after agent execution records are committed
- preserved workflow-engine ownership of all workflow state progression
- preserved replay safety through idempotent `tool_invocation_id` record writes
- added regression coverage for telemetry-backed tool invocation record, timeline, and outbox creation
- validated workflow-engine automated tests with 5 passing tests
- validated local end-to-end Mortgage Exception Review execution to `HUMAN_REVIEW_REQUIRED`
- confirmed local workflow execution produced persisted records for `borrower_profile_lookup` and `document_fetch`

Completed workstream:
- Workstream 5 - Workflow Integration

Boundary:
- gateway-api workflow tool invocation retrieval remains assigned to Workstream 6
- Postman coverage for tool-runtime and workflow tool invocation retrieval remains assigned to Workstream 6

Next step:
- implement Workstream 6: Gateway API And Postman

---

# Decision Log

## Decision 1 - Use Mock Integrations In Phase 4

Decision:
- Phase 4 will use deterministic mock integration handlers.

Reason:
- real enterprise integrations are out of scope
- mock handlers allow validation of tool mediation, contracts, and auditability
- deterministic behavior supports local development and replay safety

---

## Decision 2 - Keep Tool Runtime Separate From Agent Runtime

Decision:
- implement `tool-runtime` as a separate service boundary.

Reason:
- existing architecture defines tool-runtime as the governed execution layer for agent-accessible tools
- separation preserves least privilege and clear ownership
- future integration mediation can evolve without embedding tool logic inside agents

---

## Decision 3 - Preserve Human Review As Phase 4 Terminal Boundary

Decision:
- Phase 4 workflows will still stop at `HUMAN_REVIEW_REQUIRED`.

Reason:
- approval UI and approve/reject actions belong to Phase 5
- tool output is supporting context, not final mortgage decision authority
- critical mortgage actions must remain human-governed
