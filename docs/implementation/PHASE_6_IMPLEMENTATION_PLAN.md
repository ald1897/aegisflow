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

## Current Local Observability Endpoints

Workstream 1 exposes the following local endpoints:
- Grafana: `http://localhost:3001`
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686`
- OpenTelemetry Collector OTLP gRPC: `localhost:4317`
- OpenTelemetry Collector OTLP HTTP: `http://localhost:4318`
- OpenTelemetry Collector internal metrics: `http://localhost:8888/metrics`
- OpenTelemetry Collector exported metrics: `http://localhost:8889/metrics`

Grafana local credentials:

```text
Username: admin
Password: aegisflow
```

---

## Application Telemetry Configuration

Workstream 2 adds the following common telemetry environment variables to Python services:
- `ENABLE_TELEMETRY`
- `OTEL_EXPORTER_OTLP_ENDPOINT`

Default local behavior:
- telemetry is disabled by default in service settings
- Docker Compose enables telemetry for local application containers
- OTLP HTTP traces are exported to the OpenTelemetry Collector at `http://otel-collector:4318`
- service resource attributes include `service.name` and `deployment.environment`

Telemetry configuration must remain no-op when disabled.

Local automated tests must be able to run without the observability stack.

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

Status: Completed

Tasks:
- add OpenTelemetry Collector service to local Docker Compose - Complete
- add trace backend service, preferably Tempo or Jaeger - Complete
- add Prometheus service - Complete
- add Grafana service - Complete
- add local observability configuration files under `infrastructure/local-dev` - Complete
- expose stable local ports for Grafana, Prometheus, and trace inspection - Complete
- document local observability startup URLs - Complete

Completion criteria:
- local Docker Compose stack starts with observability services - Met
- Grafana is reachable locally - Met
- Prometheus is reachable locally - Met
- trace backend is reachable locally - Met
- existing application services continue to start successfully - Met

---

## Workstream 2 - Shared Telemetry Configuration

Status: Completed

Tasks:
- add OpenTelemetry dependencies to Python services - Complete
- define common telemetry environment variables - Complete
- create service-local telemetry configuration helpers or a shared internal helper where practical - Complete
- configure resource attributes including service name and environment - Complete
- configure OTLP export to the OpenTelemetry Collector - Complete
- preserve no-op behavior when telemetry is disabled - Complete
- add trace context propagation utilities for outbound HTTP clients - Complete

Completion criteria:
- each Python service can enable or disable telemetry through environment variables - Met
- services can export traces to the OpenTelemetry Collector - Met
- local tests can run without requiring observability infrastructure - Met
- telemetry configuration does not change business behavior - Met

---

## Workstream 3 - gateway-api Instrumentation

Status: Completed

Tasks:
- instrument FastAPI request handling - Complete
- include correlation ID in trace attributes and logs - Complete
- expose Prometheus metrics endpoint or compatible metrics export - Complete
- instrument Temporal workflow start calls - Complete
- instrument approval decision dispatch calls - Complete
- instrument event publication calls - Complete
- add tests for correlation ID preservation where practical - Complete

Completion criteria:
- gateway-api emits request traces - Met
- workflow creation requests include correlation metadata - Met
- approval and rejection requests include bounded operator decision telemetry - Met
- gateway-api metrics are visible in Prometheus - Met
- existing gateway-api tests continue to pass - Met

---

## Workstream 4 - workflow-engine And Temporal Instrumentation

Status: Completed

Tasks:
- instrument workflow-engine worker startup telemetry - Complete
- instrument Temporal activities without introducing workflow replay nondeterminism - Complete
- instrument workflow state transition activities - Complete
- instrument agent execution activity calls - Complete
- instrument tool invocation persistence activities - Complete
- instrument approval decision activities - Complete
- instrument event outbox publication from workflow-engine - Complete
- document replay-safety rules for tracing inside workflow code - Complete

Completion criteria:
- workflow-engine emits activity traces - Met
- state transition, agent execution, tool invocation, and approval decision activity spans are visible - Met
- Temporal workflow replay safety is preserved - Met
- workflow-engine metrics are visible in Prometheus - Met
- existing workflow-engine tests continue to pass - Met

---

## Workstream 5 - agent-runtime And tool-runtime Instrumentation

Status: Completed

Tasks:
- instrument agent-runtime FastAPI request handling - Complete
- instrument agent graph execution spans - Complete
- record bounded agent metadata such as agent ID, prompt ID, prompt version, validation status, and human review requirement - Complete
- instrument tool-runtime FastAPI request handling - Complete
- instrument tool permission checks - Complete
- instrument tool input and output validation results - Complete
- instrument deterministic mock tool handler latency - Complete
- expose service metrics for agent and tool execution - Complete

Completion criteria:
- agent-runtime traces show agent execution boundaries - Met
- tool-runtime traces show governed tool invocation boundaries - Met
- tool invocation telemetry does not include sensitive payloads - Met
- agent-runtime and tool-runtime metrics are visible in Prometheus - Met
- existing agent-runtime and tool-runtime tests continue to pass - Met

---

## Workstream 6 - Dashboards And Operational Views

Status: Completed

Tasks:
- create Grafana datasource provisioning for Prometheus and trace backend - Complete
- create initial workflow operations dashboard - Complete
- create service health and latency dashboard - Complete
- create agent and tool execution dashboard - Complete
- create approval decision dashboard - Complete
- add dashboard import/provisioning files to local infrastructure - Complete
- optionally add operator-console links to Grafana or trace views if stable URLs are available - Deferred

Completion criteria:
- Grafana starts with provisioned datasources - Met
- dashboards load without manual setup - Met
- dashboards show API, workflow, agent, tool, and approval telemetry after a local workflow run - Met
- dashboards avoid borrower-specific or sensitive data - Met

---

## Workstream 7 - Logs And Local Diagnostics

Status: Completed

Tasks:
- enrich structured logs with trace ID where available - Complete
- confirm correlation ID appears consistently in service logs - Complete
- decide whether to add Loki and log collection in local Docker Compose - Complete
- if Loki is added, configure log collection in a Docker Desktop-compatible manner - Deferred
- document fallback log validation through Docker logs if Loki is deferred - Complete

Completion criteria:
- logs support correlation-based local debugging - Met
- trace IDs are visible in logs where available - Met
- log collection decision is documented - Met
- no sensitive payloads are emitted into logs - Met

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

## 2026-05-12 - Workstream 1

Status:
- added OpenTelemetry Collector to local Docker Compose
- added Jaeger trace backend for local trace inspection
- added Prometheus for local metrics collection
- added Grafana on port `3001` to avoid collision with operator-console on port `3000`
- added OpenTelemetry Collector configuration under `infrastructure/local-dev/observability`
- added Prometheus scrape configuration for Prometheus, OpenTelemetry Collector, Collector-exported metrics, and Jaeger
- added Grafana datasource provisioning for Prometheus and Jaeger
- added local observability README with URLs and local credentials
- validated Docker Compose configuration
- started observability services locally
- validated Grafana health endpoint
- validated Prometheus readiness endpoint
- validated Jaeger UI endpoint
- validated OpenTelemetry Collector metrics endpoints
- validated Prometheus target health for all initial observability scrape targets
- validated Grafana datasource provisioning
- validated existing gateway-api, agent-runtime, tool-runtime, and operator-console local endpoints after adding observability services

Completed workstream:
- Workstream 1 - Local Observability Stack

Boundary:
- application services are not instrumented yet
- Jaeger may not contain AegisFlow traces until later workstreams emit telemetry
- Grafana has datasource provisioning but Phase 6 dashboards remain assigned to Workstream 6
- Loki and local log aggregation remain deferred

Next step:
- implement Workstream 2: Shared Telemetry Configuration

## 2026-05-12 - Workstream 2

Status:
- added OpenTelemetry dependencies to `gateway-api`, `workflow-engine`, `agent-runtime`, and `tool-runtime`
- added common telemetry settings for `ENABLE_TELEMETRY` and `OTEL_EXPORTER_OTLP_ENDPOINT`
- added service-local telemetry helpers for OTLP HTTP trace export
- configured telemetry resource attributes for service name and deployment environment
- preserved disabled-by-default telemetry behavior in service settings
- enabled telemetry for Python application containers in local Docker Compose
- added trace context injection utilities for outbound HTTP clients
- propagated trace context from `workflow-engine` to `agent-runtime`
- propagated trace context from `agent-runtime` to `tool-runtime`
- rebuilt Python service images with telemetry dependencies installed
- validated gateway-api, workflow-engine, agent-runtime, and tool-runtime tests against rebuilt images
- validated synthetic gateway-api span export through OpenTelemetry Collector into Jaeger
- recreated local Python service containers with telemetry enabled
- validated gateway-api, agent-runtime, and tool-runtime health endpoints after telemetry enablement
- validated workflow-engine container startup after telemetry enablement

Completed workstream:
- Workstream 2 - Shared Telemetry Configuration

Boundary:
- automatic FastAPI request instrumentation is assigned to later workstreams
- service metrics endpoints are assigned to later workstreams
- Temporal activity instrumentation is assigned to Workstream 4
- agent and tool execution span design is assigned to Workstream 5
- telemetry remains operational metadata and is not authoritative workflow or audit data

Next step:
- implement Workstream 3: gateway-api Instrumentation

## 2026-05-12 - Workstream 3

Status:
- added gateway HTTP telemetry middleware for request spans and request metrics
- added `/metrics` endpoint for Prometheus-compatible gateway metrics
- added gateway HTTP request counters, latency histograms, and error counters
- added workflow creation counter with low-cardinality workflow type and status labels
- added Temporal workflow start spans and metrics for Mortgage Exception Review workflow creation
- added Temporal human review decision dispatch spans and metrics for approval and rejection decisions
- added Kafka workflow event publication spans and metrics for gateway-published events
- added trace ID enrichment to gateway structured logs where an active span is available
- added correlation ID as bounded request and operation span metadata
- added Prometheus scrape configuration for `gateway-api`
- added gateway metrics endpoint test coverage
- rebuilt the gateway-api image with the Prometheus client dependency
- validated gateway-api automated tests against the rebuilt image
- validated local gateway-api health after recreating the service container
- validated local `/metrics` output includes gateway request metrics
- validated Prometheus reports the `gateway-api` scrape target as `up`
- validated Jaeger contains gateway-api request spans

Completed workstream:
- Workstream 3 - gateway-api Instrumentation

Boundary:
- gateway instrumentation is limited to API, Temporal dispatch, approval decision dispatch, and gateway-published event boundaries
- workflow-engine Temporal activity instrumentation remains assigned to Workstream 4
- agent-runtime and tool-runtime execution instrumentation remains assigned to Workstream 5
- metrics use low-cardinality labels and do not include workflow IDs, trace IDs, approval IDs, borrower values, prompts, or document contents
- traces include workflow and approval identifiers where operationally useful, but telemetry remains non-authoritative

Next step:
- implement Workstream 4: workflow-engine And Temporal Instrumentation

## 2026-05-12 - Workstream 4

Status:
- added workflow-engine Prometheus metrics dependency
- added workflow-engine metrics endpoint on port `8030`
- added worker startup metric
- added shared Temporal activity instrumentation helper for workflow-engine activities
- added bounded activity spans for state transition, agent execution, tool invocation, approval recording, and human review decision activities
- added activity execution counters and latency histograms
- added workflow state transition metrics with low-cardinality prior state, new state, and status labels
- added agent execution metrics with bounded agent, status, validation status, and human review labels
- added tool invocation metrics with bounded tool, status, and permission labels
- added approval decision metrics with decision and status labels
- added workflow-engine event publication spans and metrics
- added outbound agent-runtime client span inside workflow-engine agent activity
- propagated W3C trace context from gateway-api Temporal workflow starts into workflow-engine activity payloads
- passed trace context through deterministic workflow payload fields without calling telemetry APIs inside workflow definitions
- exposed workflow-engine metrics port in local Docker Compose
- added Prometheus scrape target for `workflow-engine`
- rebuilt gateway-api and workflow-engine images
- validated gateway-api tests against rebuilt image
- validated workflow-engine tests against rebuilt image
- validated local workflow-engine metrics endpoint
- validated a Mortgage Exception Review workflow reaches `HUMAN_REVIEW_REQUIRED`
- validated workflow-engine activity, state transition, agent, tool, and event publication metrics
- validated approval path reaches `COMPLETED`
- validated approval decision activity metrics and spans
- validated Prometheus reports the `workflow-engine` scrape target as `up`
- validated Jaeger contains workflow-engine activity and event publication spans
- validated Jaeger contains a joined trace with both `gateway-api` and `workflow-engine`

Completed workstream:
- Workstream 4 - workflow-engine And Temporal Instrumentation

Replay safety:
- workflow definitions do not call OpenTelemetry or metrics APIs
- workflow definitions only pass trace context as deterministic payload data
- instrumentation is limited to activities, worker startup, outbound HTTP calls, and event publication side effects
- telemetry does not alter workflow state, approval records, timelines, outbox records, or Temporal decisions

Boundary:
- agent-runtime and tool-runtime request handling and internal execution instrumentation remain assigned to Workstream 5
- Grafana dashboards remain assigned to Workstream 6
- log aggregation remains assigned to Workstream 7
- telemetry remains operational metadata and is not authoritative workflow, approval, event, or audit data

Next step:
- implement Workstream 5: agent-runtime And tool-runtime Instrumentation

## 2026-05-12 - Workstream 5

Status:
- added agent-runtime HTTP telemetry middleware for request spans and request metrics
- added agent-runtime `/metrics` endpoint with request, agent execution, graph step, and tool-runtime client metrics
- added bounded agent execution spans with workflow ID, correlation ID, workflow type, workflow state, agent ID, prompt ID, prompt version, validation status, human review requirement, and tool invocation count
- added LangGraph step spans and metrics for context assembly, agent execution, and output validation
- added outbound tool-runtime client spans and metrics from agent-runtime, with W3C trace context propagation
- added tool-runtime HTTP telemetry middleware for request spans and request metrics
- added tool-runtime `/metrics` endpoint with request, governed tool invocation, and deterministic handler latency metrics
- added bounded tool invocation spans for permission checks, input validation, output validation, handler execution, and invocation outcomes
- added Prometheus scrape targets for `agent-runtime` and `tool-runtime`
- rebuilt agent-runtime and tool-runtime images
- validated agent-runtime automated tests with 8 passing tests
- validated tool-runtime automated tests with 8 passing tests
- validated local agent-runtime and tool-runtime `/metrics` endpoints
- reloaded Prometheus and validated `agent-runtime` and `tool-runtime` scrape targets as `up`
- executed a local intake agent request through agent-runtime to tool-runtime
- validated Jaeger contains agent-runtime request, agent execution, graph step, outbound tool-runtime client, tool-runtime request, and governed tool invocation spans in the same trace

Completed workstream:
- Workstream 5 - agent-runtime And tool-runtime Instrumentation

Boundary:
- Workstream 5 telemetry uses bounded span attributes and low-cardinality metric labels
- telemetry does not include raw document contents, borrower PII, secrets, prompt content, or unrestricted tool payloads
- Grafana dashboards remain assigned to Workstream 6
- log enrichment and local diagnostics remain assigned to Workstream 7
- Postman observability validation and phase documentation closeout remain assigned to Workstream 8
- telemetry remains operational metadata and is not authoritative workflow, approval, event, or audit data

Next step:
- implement Workstream 6: Dashboards And Operational Views

## 2026-05-12 - Workstream 6

Status:
- added Grafana dashboard provider provisioning under local observability infrastructure
- added `AegisFlow - Workflow Operations` dashboard for workflow creation, completion, human review, state transitions, activity latency, and event publication telemetry
- added `AegisFlow - Service Health And Latency` dashboard for scrape health, HTTP request rate, HTTP p95 latency, HTTP error rate, and trace inspection guidance
- added `AegisFlow - Agent And Tool Execution` dashboard for agent executions, tool invocations, validation failures, authorization failures, execution rates, and execution latency
- added `AegisFlow - Approval Decisions` dashboard for approval and rejection decision counts, decision rate, decision latency, and terminal workflow transition telemetry
- updated local observability README with provisioned dashboard names and telemetry-label boundaries
- validated dashboard JSON parsing locally
- restarted Grafana with dashboard provisioning enabled
- validated Grafana datasource provisioning for Prometheus and Jaeger
- validated Grafana API lists all four AegisFlow dashboards in the `AegisFlow` folder
- executed a local intake agent request through agent-runtime to tool-runtime
- validated dashboard Prometheus queries for service, agent, and tool telemetry return data

Completed workstream:
- Workstream 6 - Dashboards And Operational Views

Boundary:
- operator-console links to Grafana and trace views are deferred because stable per-workflow trace URLs require a later UI integration decision
- dashboards use low-cardinality labels only and avoid borrower-specific values, raw document contents, prompt content, comments, workflow IDs, approval IDs, and trace IDs as metric labels
- dashboards are operational telemetry views only and do not replace PostgreSQL workflow, approval, timeline, or event records
- log enrichment and local diagnostics remain assigned to Workstream 7
- Postman observability validation and final documentation closeout remain assigned to Workstream 8

Next step:
- implement Workstream 7: Logs And Local Diagnostics

## 2026-05-12 - Workstream 7

Status:
- added structured JSON logging helpers to workflow-engine, agent-runtime, and tool-runtime
- enriched gateway-api structured logs with bounded operational fields beyond workflow ID
- added active trace ID enrichment to workflow-engine, agent-runtime, and tool-runtime JSON logs
- bound correlation ID and route context around agent-runtime and tool-runtime HTTP requests
- bound workflow, correlation, activity, agent, tool, and approval context around workflow-engine activity execution
- propagated `X-Correlation-ID` from workflow-engine to agent-runtime and from agent-runtime to tool-runtime
- added correlation-aware execution logs for agent starts, completions, and failures
- added correlation-aware invocation logs for tool starts, denials, validation failures, output validation failures, and completions
- enriched workflow-engine activity, state transition, event publication, and approval logs with bounded operational context
- enriched gateway workflow creation and approval decision logs with bounded operational context
- deferred Loki and Docker log collection from the local stack
- documented Docker logs as the supported Workstream 7 local log diagnostics path
- rebuilt gateway-api, workflow-engine, agent-runtime, and tool-runtime images
- validated gateway-api automated tests with 16 passing tests
- validated workflow-engine automated tests with 12 passing tests
- validated agent-runtime automated tests with 8 passing tests
- validated tool-runtime automated tests with 8 passing tests
- executed a local Mortgage Exception Review workflow through approval to `COMPLETED`
- validated Docker logs contain correlation-matched JSON entries for gateway-api, workflow-engine, agent-runtime, and tool-runtime
- validated all correlation-matched Docker log entries from the local workflow included trace IDs

Completed workstream:
- Workstream 7 - Logs And Local Diagnostics

Boundary:
- Loki is deferred because Docker Desktop-compatible log collection adds host-specific complexity that is not required for Phase 6 local diagnostics
- local log validation uses Docker logs and structured JSON filtering by correlation ID
- logs include bounded operational identifiers and statuses, but do not include borrower PII, raw document contents, secrets, prompt content, full model output, approval comments, or unrestricted payloads
- logs remain operational diagnostics only and do not replace PostgreSQL workflow, approval, timeline, or event records
- Postman observability validation and final documentation closeout remain assigned to Workstream 8

Next step:
- implement Workstream 8: Postman, Manual Validation, And Documentation

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

---

## Decision 4 - Use Jaeger As Initial Local Trace Backend

Decision:
- Workstream 1 uses Jaeger as the initial local trace backend.

Reason:
- Jaeger provides a lightweight trace inspection UI for local development
- the OpenTelemetry Collector can export traces to Jaeger through OTLP
- the stack remains simple while Phase 6 establishes trace and metric plumbing
- Grafana can still be provisioned with a Jaeger datasource for later dashboards and trace links

---

## Decision 5 - Defer Loki In Local Development

Decision:
- Workstream 7 defers Loki and Docker log collection from the local Docker Compose stack.
- Local log diagnostics use `docker logs` and structured JSON filtering by correlation ID.

Reason:
- Docker Desktop-compatible log collection introduces host-specific configuration and operational overhead
- Phase 6 already provides cross-service trace inspection through Jaeger and operational metrics through Prometheus and Grafana
- Docker logs are sufficient for local correlation-based debugging when services emit JSON logs with correlation IDs and trace IDs
- deferring Loki keeps local observability reproducible while preserving a clear path for future log aggregation
