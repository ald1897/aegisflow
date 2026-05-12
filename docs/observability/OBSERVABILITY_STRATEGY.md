# Observability Strategy

## Purpose

This document defines the observability architecture, telemetry standards, tracing model, logging strategy, and operational visibility requirements for AegisFlow.

Observability exists to provide:
- operational transparency
- workflow traceability
- AI execution visibility
- distributed system diagnostics
- governance visibility
- replay analysis
- production reliability insights

All platform components must emit telemetry consistent with the standards defined in this document.

---

# Observability Philosophy

## Observability Is a Core Platform Capability

Observability is not optional infrastructure.

It is a foundational operational requirement necessary for:
- workflow governance
- AI system debugging
- auditability
- replayability
- production operations
- incident response

---

## Workflow Visibility Is Mandatory

All workflow execution must remain:
- traceable
- inspectable
- replayable
- measurable

Operational stakeholders should always be able to determine:
- current workflow state
- execution history
- agent activity
- escalation reasons
- failure causes

---

## AI Systems Must Remain Explainable

AI-assisted systems introduce operational uncertainty.

The platform must therefore maximize:
- execution visibility
- reasoning traceability
- model attribution
- prompt traceability
- tool invocation transparency

Opaque AI execution is unacceptable.

---

# Observability Pillars

The platform observability model is built around:

- Logs
- Metrics
- Distributed Traces
- Audit Events
- Workflow Timelines

---

# High-Level Observability Architecture

## Core Components

The observability stack consists of:

- OpenTelemetry instrumentation
- Structured logging pipelines
- Distributed tracing
- Metrics aggregation
- Workflow timeline persistence
- Audit event storage
- Operational dashboards
- Alerting systems

---

## Example Stack

Examples may include:
- OpenTelemetry
- Prometheus
- Grafana
- Loki
- Tempo
- Jaeger

Technology choices may evolve while preserving observability contracts.

---

## Current Local Stack

The Phase 6 local implementation uses:
- OpenTelemetry Collector for local OTLP intake
- Jaeger for local trace inspection
- Prometheus for local metrics collection
- Grafana for local operational dashboards
- Docker logs for local structured log diagnostics

Local URLs:
- Grafana: `http://localhost:3001`
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686`
- OpenTelemetry Collector OTLP HTTP: `http://localhost:4318`
- OpenTelemetry Collector OTLP gRPC: `localhost:4317`

Loki is intentionally deferred from the local Docker Compose stack. Local log diagnostics use structured JSON service logs and `docker logs` filtering by correlation ID.

---

# Distributed Tracing Strategy

# Tracing Philosophy

Distributed tracing is mandatory across all critical workflows.

Traces should expose:
- workflow progression
- service boundaries
- agent execution
- tool invocation
- external integrations
- retry behavior

---

## Current Trace Coverage

The current local implementation emits spans for:
- gateway-api HTTP requests
- gateway workflow creation
- gateway Temporal workflow start dispatch
- gateway human review decision dispatch
- gateway workflow event publication
- workflow-engine Temporal activities
- workflow-engine state transitions
- workflow-engine agent-runtime client calls
- workflow-engine event publication
- agent-runtime HTTP requests
- agent-runtime agent execution
- agent-runtime LangGraph execution steps
- agent-runtime tool-runtime client calls
- tool-runtime HTTP requests
- tool-runtime governed tool invocation
- tool-runtime permission checks, input validation, handler execution, and output validation
- evaluation-service HTTP requests
- evaluation-service evaluation run creation
- evaluation-service workflow evidence loading
- evaluation-service evaluator execution
- evaluation-service evaluation result persistence

Trace context propagates from gateway-api into workflow-engine deterministic payload fields and then across internal HTTP calls to agent-runtime and tool-runtime.

Temporal workflow definitions must not call tracing APIs directly. Instrumentation belongs at service boundaries, worker startup, activities, and side-effecting clients.

---

# Metrics Strategy

Metrics provide aggregate operational visibility and must use low-cardinality labels.

The current local implementation exposes Prometheus metrics for:
- gateway HTTP requests, errors, latency, workflow creation, Temporal dispatch, approval dispatch, and event publication
- workflow-engine worker startup, activity execution, state transitions, agent execution, tool invocation, approval decisions, and event publication
- agent-runtime HTTP requests, agent execution, graph steps, and tool-runtime client calls
- tool-runtime HTTP requests, governed tool invocations, and handler latency
- evaluation-service HTTP requests, evaluation run counts, run duration, evaluation result counts, evidence-consistency signal counts, and prompt-attributed result status

Metric labels must not include:
- borrower values
- workflow IDs
- approval IDs
- trace IDs
- prompt content
- document content
- comments
- raw request or response payloads

Workflow IDs and trace IDs may appear in traces and structured logs where operationally useful, but not as metric labels.

---

# Dashboard Strategy

The current local Grafana stack provisions:
- `AegisFlow - Workflow Operations`
- `AegisFlow - Service Health And Latency`
- `AegisFlow - Agent And Tool Execution`
- `AegisFlow - Approval Decisions`
- `AegisFlow - Evaluation Quality`

Dashboards are operational views only. They do not replace PostgreSQL records, Temporal history, workflow timeline entries, approval records, or outbox events.

---

# Logging Strategy

Structured logs support local debugging and incident investigation.

Current local service logs include bounded operational fields such as:
- `service`
- `environment`
- `correlation_id`
- `trace_id`
- `workflow_id`
- `agent_id`
- `tool_id`
- `approval_id`
- `operation`
- `status`

Logs must not include:
- borrower PII
- raw document contents
- secrets
- prompt content
- full model output
- approval comments
- unrestricted tool input or output payloads

For local diagnostics, use `docker logs` and filter JSON entries by `correlation_id`.

---

# System Of Record Boundary

Observability data is operational telemetry.

It must not become authoritative for:
- workflow state
- approval decisions
- audit history
- timeline history
- event facts

Authoritative facts remain in PostgreSQL, Temporal history, workflow timeline entries, approval records, and workflow event records.

---

# Correlation ID Model

## Purpose

Correlation IDs provide end-to-end operational traceability.

---

## Requirements

Every workflow must generate:
- a globally unique correlation ID

This ID must propagate across:
- services
- events
- logs
- traces
- integrations
- agent executions

---

## Example

```text id="jkk8v2"
correlation_id = 550e8400-e29b-41d4-a716-446655440000
```
