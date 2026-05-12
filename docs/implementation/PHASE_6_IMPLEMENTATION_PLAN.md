# Phase 6 Implementation Plan

## Purpose

This document defines the continuous implementation plan for Phase 6 of AegisFlow.

Phase 6 introduces production-grade observability integration for the local platform simulation.

The plan exists to:
- guide implementation work across multiple development sessions
- preserve architectural alignment with existing platform documentation
- make workflow, agent, tool, approval, and API execution observable across service boundaries
- support operational debugging without weakening workflow determinism
- provide clear validation checkpoints before Phase 6 is considered complete

This document must be updated as implementation progresses.

---

# Phase 6 Objective

Phase 6 will add distributed observability across the completed Mortgage Exception Review workflow.

The platform must support operational visibility for:
- API requests
- workflow orchestration
- Temporal activities
- agent execution
- governed tool invocation
- approval and rejection decisions
- event publication
- service health and readiness

Observability must:
- preserve correlation ID propagation
- introduce trace ID propagation where practical
- expose service-level and workflow-level metrics
- support local dashboards
- avoid storing secrets, raw document contents, or unrestricted borrower PII in telemetry
- remain secondary to authoritative workflow, approval, event, and audit records in PostgreSQL

Observability data may support investigation and operations.

Observability data must not:
- become the system of record
- mutate workflow state
- bypass workflow-engine ownership
- replace workflow timelines or approval records
- expose sensitive payloads unnecessarily
- introduce non-deterministic behavior into replayable workflow logic

---

# Business Context

## Current Business Capability

AegisFlow can currently demonstrate a governed Mortgage Exception Review workflow from creation through AI-assisted preparation, human review, approval or rejection, and local workflow completion.

Current Phase 5 capability proves:
- mortgage exception review cases can be created and persisted
- Temporal can run durable workflow execution
- governed agents can produce validated structured outputs
- approved tools can provide synthetic supporting context
- workflow evidence can be inspected in the operator-console
- human approval or rejection can be captured with comments
- approval records, timeline entries, and outbox events are persisted
- Postman can validate both approval and rejection paths

## Phase 6 Business Goal

Phase 6 will demonstrate how mortgage operations and platform teams can monitor the health, flow, and performance of governed mortgage exception workflows.

For mortgage stakeholders, this means AegisFlow will begin to show operational oversight beyond individual case review.

Examples of business value:
- identify where exception workflows spend time
- inspect service-level health across the workflow path
- trace a case across gateway-api, workflow-engine, agent-runtime, tool-runtime, and operator decisions
- detect service errors, latency spikes, retry patterns, and event publication problems
- provide leadership-facing evidence that governed AI workflows are observable and operationally controllable

## Business Boundary

Phase 6 will not connect to production mortgage observability systems.

Phase 6 will not implement production incident response, paging, SIEM integration, or compliance reporting.

Phase 6 will not make AI evaluation judgments.

Phase 6 will not implement replay and recovery workflows.

Observability will support local operational insight for the simulated Mortgage Exception Review process.

---

# Current Implementation Baseline

Phase 6 starts from the completed Phase 5 baseline.

Implemented runtime services:
- `gateway-api`
- `workflow-engine`
- `agent-runtime`
- `tool-runtime`
- `operator-console`
- Postgres
- Redpanda
- Redis
- Temporal
- Temporal UI

Implemented workflow behavior:
- `NEW`
- `INTAKE_IN_PROGRESS`
- `DOCUMENT_ANALYSIS_PENDING`
- `RISK_REVIEW_PENDING`
- `HUMAN_REVIEW_REQUIRED`
- `APPROVED`
- `REJECTED`
- `COMPLETED`

Implemented query and action APIs:
- workflow creation
- workflow retrieval
- workflow timeline retrieval
- workflow agent execution retrieval
- workflow tool invocation retrieval
- human review queue retrieval
- workflow review context retrieval
- workflow approval record retrieval
- workflow approval and rejection decision submission

Implemented persisted records:
- `workflow_records`
- `workflow_state_transitions`
- `workflow_timeline_entries`
- `workflow_event_outbox`
- `agent_execution_records`
- `tool_invocation_records`
- `approval_records`

Existing observability foundation:
- correlation ID middleware in gateway-api
- structured JSON logs for workflow creation
- workflow timelines persisted in PostgreSQL
- workflow event outbox records
- Temporal execution history
- service health and readiness endpoints

Phase 6 must extend this baseline without weakening workflow-engine ownership of state transitions or treating telemetry as authoritative data.

---

# Target Phase 6 Scope

## In Scope

Phase 6 should implement:
- local observability stack in Docker Compose
- OpenTelemetry collector configuration
- distributed tracing for service boundaries
- trace context propagation across HTTP calls
- correlation ID to trace metadata mapping where practical
- service metrics for API requests, workflow activity, agent execution, tool invocation, and approval decisions
- structured log enrichment with correlation and trace metadata
- Grafana dashboards for local operational inspection
- local manual validation for trace and metric visibility
- documentation updates

---

## Out Of Scope

Phase 6 must not implement:
- production alert routing
- production incident management
- SIEM integration
- cloud-managed observability services
- production data retention policies
- AI evaluation scoring
- replay and failure recovery tooling
- production identity provider integration
- production RBAC enforcement
- production mortgage system integration
- telemetry capture of raw document contents, secrets, or unrestricted borrower PII

---

# Proposed Runtime Architecture

## Local Observability Stack

The local stack should add:
- OpenTelemetry Collector
- Prometheus
- Grafana
- Tempo or Jaeger for traces
- Loki only if local log collection can be implemented without fragile host-specific behavior

Preferred initial local flow:

```text
Services
    ->
OpenTelemetry Collector
    ->
Tempo or Jaeger

Services
    ->
Prometheus Metrics Endpoint
    ->
Prometheus
    ->
Grafana
```

Structured application logs may remain container logs in early workstreams if trace and metric coverage are implemented first.

---

## Telemetry Ownership

Each service owns telemetry emission for its own execution boundary.

Expected service ownership:
- gateway-api owns API request telemetry
- workflow-engine owns workflow activity and decision telemetry
- agent-runtime owns agent execution telemetry
- tool-runtime owns tool invocation telemetry
- operator-console owns frontend request and user action telemetry where practical

PostgreSQL remains the authoritative system of record for operational data.

Temporal remains the authoritative durable workflow execution history.

Kafka/Redpanda events remain immutable operational facts, not metrics storage.

Observability tools provide operational views over execution behavior.

---

# Telemetry Model

## Required Identifiers

Telemetry should include:
- `service.name`
- `deployment.environment`
- `workflow_id` when available
- `correlation_id` when available
- `trace_id` when available
- `actor_id` only when needed for approval or operator action telemetry
- `agent_id` when observing agent execution
- `tool_id` when observing tool invocation
- `approval_id` when observing approval records

Telemetry must avoid:
- borrower PII
- raw document content
- secrets
- full prompt content
- unbounded model output
- unrestricted tool input or output payloads

---

## Trace Requirements

Traces should show:
- gateway workflow creation request
- Temporal workflow start request
- workflow-engine activity execution
- agent-runtime execution request
- tool-runtime invocation request
- workflow timeline and outbox persistence activities
- approval or rejection submission through gateway-api
- human review decision execution through workflow-engine

Trace spans should use bounded attributes.

Span events may describe operational milestones, but must not duplicate full persistence records.

---

## Metric Requirements

Metrics should expose:
- API request count
- API request latency
- API error count
- workflow creation count
- workflow state transition count
- workflow completion count
- workflow failure count
- agent execution count
- agent execution latency
- agent validation failure count
- tool invocation count
- tool invocation latency
- tool authorization failure count
- approval decision count
- approval decision latency
- event publication count
- event publication failure count

Metrics should support labels for low-cardinality dimensions only.

Allowed low-cardinality labels may include:
- service name
- endpoint route
- HTTP method
- HTTP status class
- workflow type
- workflow state
- agent ID
- tool ID
- approval decision
- environment

Metrics must not use high-cardinality labels such as raw workflow IDs, trace IDs, approval IDs, or borrower-specific values.

---

## Log Requirements

Structured logs should include:
- timestamp
- severity
- service name
- environment
- correlation ID
- trace ID when available
- workflow ID when available
- event name or operation name

Logs must remain concise and redacted.

Logs must not become the primary audit store.

---

# Implementation Workstreams

## Workstream 1 - Local Observability Stack

Status: Not Started

Tasks:
- add OpenTelemetry Collector service to local Docker Compose
- add trace backend service, preferably Tempo or Jaeger
- add Prometheus service
- add Grafana service
- add local observability configuration files under `infrastructure/local-dev`
- expose stable local ports for Grafana, Prometheus, and trace inspection
- document local observability startup URLs

Completion criteria:
- local Docker Compose stack starts with observability services
- Grafana is reachable locally
- Prometheus is reachable locally
- trace backend is reachable locally
- existing application services continue to start successfully

---

## Workstream 2 - Shared Telemetry Configuration

Status: Not Started

Tasks:
- add OpenTelemetry dependencies to Python services
- define common telemetry environment variables
- create service-local telemetry configuration helpers or a shared internal helper where practical
- configure resource attributes including service name and environment
- configure OTLP export to the OpenTelemetry Collector
- preserve no-op behavior when telemetry is disabled
- add trace context propagation utilities for outbound HTTP clients

Completion criteria:
- each Python service can enable or disable telemetry through environment variables
- services can export traces to the OpenTelemetry Collector
- local tests can run without requiring observability infrastructure
- telemetry configuration does not change business behavior

---

## Workstream 3 - gateway-api Instrumentation

Status: Not Started

Tasks:
- instrument FastAPI request handling
- include correlation ID in trace attributes and logs
- expose Prometheus metrics endpoint or compatible metrics export
- instrument Temporal workflow start calls
- instrument approval decision dispatch calls
- instrument event publication calls
- add tests for correlation ID preservation where practical

Completion criteria:
- gateway-api emits request traces
- workflow creation requests include correlation metadata
- approval and rejection requests include bounded operator decision telemetry
- gateway-api metrics are visible in Prometheus
- existing gateway-api tests continue to pass

---

## Workstream 4 - workflow-engine And Temporal Instrumentation

Status: Not Started

Tasks:
- instrument workflow-engine worker startup telemetry
- instrument Temporal activities without introducing workflow replay nondeterminism
- instrument workflow state transition activities
- instrument agent execution activity calls
- instrument tool invocation persistence activities
- instrument approval decision activities
- instrument event outbox publication from workflow-engine
- document replay-safety rules for tracing inside workflow code

Completion criteria:
- workflow-engine emits activity traces
- state transition, agent execution, tool invocation, and approval decision activity spans are visible
- Temporal workflow replay safety is preserved
- workflow-engine metrics are visible in Prometheus
- existing workflow-engine tests continue to pass

---

## Workstream 5 - agent-runtime And tool-runtime Instrumentation

Status: Not Started

Tasks:
- instrument agent-runtime FastAPI request handling
- instrument agent graph execution spans
- record bounded agent metadata such as agent ID, prompt ID, prompt version, validation status, and human review requirement
- instrument tool-runtime FastAPI request handling
- instrument tool permission checks
- instrument tool input and output validation results
- instrument deterministic mock tool handler latency
- expose service metrics for agent and tool execution

Completion criteria:
- agent-runtime traces show agent execution boundaries
- tool-runtime traces show governed tool invocation boundaries
- tool invocation telemetry does not include sensitive payloads
- agent-runtime and tool-runtime metrics are visible in Prometheus
- existing agent-runtime and tool-runtime tests continue to pass

---

## Workstream 6 - Dashboards And Operational Views

Status: Not Started

Tasks:
- create Grafana datasource provisioning for Prometheus and trace backend
- create initial workflow operations dashboard
- create service health and latency dashboard
- create agent and tool execution dashboard
- create approval decision dashboard
- add dashboard import/provisioning files to local infrastructure
- optionally add operator-console links to Grafana or trace views if stable URLs are available

Completion criteria:
- Grafana starts with provisioned datasources
- dashboards load without manual setup
- dashboards show API, workflow, agent, tool, and approval telemetry after a local workflow run
- dashboards avoid borrower-specific or sensitive data

---

## Workstream 7 - Logs And Local Diagnostics

Status: Not Started

Tasks:
- enrich structured logs with trace ID where available
- confirm correlation ID appears consistently in service logs
- decide whether to add Loki and log collection in local Docker Compose
- if Loki is added, configure log collection in a Docker Desktop-compatible manner
- document fallback log validation through Docker logs if Loki is deferred

Completion criteria:
- logs support correlation-based local debugging
- trace IDs are visible in logs where available
- log collection decision is documented
- no sensitive payloads are emitted into logs

---

## Workstream 8 - Postman, Manual Validation, And Documentation

Status: Not Started

Tasks:
- update Postman collection with observability validation requests where applicable
- update manual validation documentation with Grafana, Prometheus, and trace backend checks
- update `CURRENT_FUNCTIONALITY.md`
- update `IMPLEMENTATION_ROADMAP.md`
- update `OBSERVABILITY_STRATEGY.md` if implementation decisions refine the strategy
- update `DEVELOPER_WORKFLOW.md` if startup or diagnostics commands change
- add Phase 6 completion log after validation

Completion criteria:
- manual tester can create a workflow and inspect related traces
- manual tester can view metrics in Prometheus or Grafana
- manual tester can validate approval and rejection paths remain observable
- documentation describes implemented behavior, not aspirational behavior
- business-facing boundary remains clear for mortgage stakeholders

---

# Validation Plan

## Automated Tests

Expected test suites:
- gateway-api tests
- workflow-engine tests
- agent-runtime tests
- tool-runtime tests
- operator-console build where impacted

Minimum validation:
- telemetry configuration defaults do not require observability stack during tests
- services still start without telemetry infrastructure when telemetry is disabled
- correlation ID propagation behavior remains intact
- workflow creation still starts Temporal workflow execution
- approval and rejection actions still route through workflow-engine-owned decision execution
- metrics endpoints or exporters do not expose sensitive payloads

---

## Manual Observability Validation

Expected manual flow:
- start local Docker Compose stack with observability services
- open Grafana
- open Prometheus
- open trace backend UI
- run the Postman happy path through workflow creation, human review, approval, separate rejection, and approval retrieval
- inspect traces for gateway-api, workflow-engine, agent-runtime, and tool-runtime activity
- inspect metrics for API requests, workflow execution, agent execution, tool invocation, and approval decisions
- inspect logs for correlation ID and trace ID linkage

Expected manual result:
- workflow reaches `HUMAN_REVIEW_REQUIRED`
- review context is retrievable
- one workflow is approved and completed
- a separate workflow is rejected and completed
- traces show cross-service execution boundaries
- metrics update after workflow activity
- logs can be correlated to workflow execution

---

# Risk Register

## Risk 1 - Telemetry Breaks Workflow Replay Safety

Mitigation:
- do not introduce non-deterministic telemetry behavior inside replayed workflow logic
- prefer instrumentation around activities, service boundaries, and workers
- document any Temporal-specific tracing constraints before implementation

---

## Risk 2 - Sensitive Data Leaks Into Telemetry

Mitigation:
- use bounded span attributes and metric labels
- avoid raw prompt, document, borrower, tool input, and tool output payloads
- review telemetry attributes before enabling dashboards

---

## Risk 3 - High-Cardinality Metrics Degrade Observability

Mitigation:
- do not label metrics with workflow IDs, trace IDs, approval IDs, or borrower values
- use workflow IDs in traces and logs, not metric dimensions
- keep dashboards focused on operational aggregates

---

## Risk 4 - Local Observability Stack Becomes Too Heavy

Mitigation:
- start with the smallest stack that proves traces and metrics
- defer Loki if local log collection becomes host-specific or fragile
- preserve simple Docker Compose startup

---

## Risk 5 - Observability Is Mistaken For Audit

Mitigation:
- preserve PostgreSQL records as authoritative operational history
- keep workflow timeline, approval records, and outbox events as durable facts
- document observability as operational telemetry, not system of record

---

# Phase 6 Completion Criteria

Phase 6 is complete when:
- local observability services start through Docker Compose
- services emit traces to the configured trace backend
- Prometheus or compatible metrics collection captures service metrics
- Grafana dashboards are available for workflow and service inspection
- correlation ID and trace ID metadata can be used for local debugging
- workflow creation, agent execution, tool invocation, human review, approval, and rejection paths are observable
- telemetry avoids sensitive payload exposure
- automated tests pass for impacted services
- manual Postman validation confirms observable approval and rejection workflows
- documentation and roadmap are updated

---

# Running Status Log

## 2026-05-12

Status:
- Phase 6 planning started
- Continuous implementation plan created

Next step:
- implement Workstream 1: Local Observability Stack

---

# Decision Log

## Decision 1 - Observability Is Operational Telemetry, Not System Of Record

Decision:
- Phase 6 telemetry will support debugging, monitoring, and operational insight, but authoritative workflow and approval facts remain in PostgreSQL, Temporal history, and workflow events.

Reason:
- regulated workflows require durable operational records
- observability systems may sample, expire, or aggregate data
- auditability must not depend on transient telemetry stores

---

## Decision 2 - Trace And Metric Coverage Before Log Aggregation

Decision:
- Phase 6 will prioritize traces, metrics, and Grafana dashboards before adding a local log aggregation service.

Reason:
- distributed workflow diagnosis depends first on cross-service traces
- metrics provide the first operational dashboard surface
- local Docker log collection can be host-specific and should not delay core observability capability

---

## Decision 3 - Preserve Temporal Replay Safety

Decision:
- Phase 6 instrumentation must avoid non-deterministic tracing behavior inside replay-sensitive workflow logic.

Reason:
- Temporal workflow determinism is a core AegisFlow architecture constraint
- telemetry must not affect workflow replay or state progression
- activity-level and service-boundary instrumentation provides observability without weakening orchestration guarantees
