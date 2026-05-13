# Developer Workflow

## Purpose

This document defines the engineering lifecycle, development standards, contribution workflow, deployment gating, and operational expectations for building within the AegisFlow platform.

The developer workflow exists to:
- standardize engineering practices
- preserve architectural consistency
- enforce governance requirements
- reduce operational drift
- improve reliability
- maintain auditability
- support safe AI system evolution
- support scalable monorepo development

This document serves as the operational engineering playbook for the AegisFlow platform.

---

# Engineering Philosophy

## Platform Integrity Over Individual Convenience

AegisFlow is a governed enterprise AI orchestration platform.

Engineering decisions should prioritize:
- reliability
- observability
- auditability
- replayability
- deterministic orchestration
- operational safety

over:
- shortcuts
- hidden abstractions
- ad hoc automation
- ungoverned experimentation

---

## AI Systems Are Production Infrastructure

AI functionality is treated as:
- operational infrastructure

not:
- experimental scripting
- isolated prototypes
- black-box automation

All AI behavior must remain:
- measurable
- observable
- replayable
- governed
- testable

---

## Explicitness Over Cleverness

Code should optimize for:
- operational readability
- debugging clarity
- replayability
- deterministic behavior

Avoid:
- hidden orchestration
- magic abstractions
- implicit workflow mutation
- opaque framework behavior

---

# Repository Structure

## Monorepo Philosophy

AegisFlow is implemented as a modular monorepo.

The monorepo structure exists to:
- centralize architecture visibility
- simplify replay testing
- improve AI-assisted development
- unify workflow orchestration contracts
- reduce integration drift

Repository structure is formally defined in:

- `/docs/architecture/REPOSITORY_STRUCTURE.md`

---

# High-Level Repository Layout

```text
/apps
/packages
/prompts
/docs
/infrastructure
/tests
/scripts
```

---

# Application Development Standards

# Application Ownership

Applications represent bounded operational services.

Each application should:
- own a clearly defined responsibility
- expose explicit interfaces
- emit telemetry independently
- support isolated deployment

---

# Core Applications

Examples include:
- gateway-api
- workflow-engine
- agent-runtime
- tool-runtime
- policy-engine
- audit-service
- evaluation-service
- notification-service
- operator-console

---

# Required Application Structure

Suggested structure:

```text
/apps/<service-name>/
├── src/
├── tests/
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

# Internal Service Layout

Suggested internal structure:

```text
/src
├── api/
├── domain/
├── workflows/
├── services/
├── events/
├── telemetry/
├── security/
├── models/
├── config/
└── tests/
```

---

# Shared Package Development

# Shared Package Philosophy

Shared packages contain:
- reusable contracts
- telemetry utilities
- event schemas
- workflow helpers
- security middleware

Shared packages must remain:
- lightweight
- framework-minimal
- orchestration-independent

---

# Allowed Dependency Rules

Allowed:

```text
apps → packages
apps → prompts
packages → packages
```

Forbidden:

```text
packages → apps
apps → shared databases
apps → hidden internal contracts
```

---

# Workflow Development Workflow

# Workflow Creation Requirements

All workflows must define:
- workflow states
- state transitions
- retry behavior
- timeout handling
- escalation rules
- observability requirements
- replay constraints

---

# Workflow Documentation Requirements

New workflows require updates to:
- WORKFLOW_STATE_MACHINE.md
- EVENT_CATALOG.md
- API_CONTRACTS.md
- AI_EVALUATION_STRATEGY.md (if AI-enabled)

---

# Workflow Implementation Checklist

Before merge:
- deterministic transitions validated
- replay safety reviewed
- escalation logic defined
- telemetry instrumentation added
- workflow events documented

---

# Workflow State Standards

States should:
- remain explicit
- reflect operational meaning
- avoid ambiguity

Avoid:
- ACTIVE
- PROCESSING
- RUNNING_STUFF

Prefer:
- DOCUMENT_ANALYSIS_PENDING
- HUMAN_APPROVAL_REQUIRED
- FRAUD_REVIEW_PENDING

---

# Event Development Workflow

# Event Philosophy

Events are immutable operational facts.

---

# New Event Requirements

All new events require:
- schema definition
- catalog registration
- ownership definition
- replay safety review
- observability metadata

---

# Required Event Metadata

All events must include:
- event_id
- correlation_id
- workflow_id
- timestamp
- source_service
- event_version

---

# Event Review Checklist

Before merge:
- naming conventions validated
- schema compatibility reviewed
- replay safety confirmed
- consumer impact evaluated

---

# AI Agent Development Workflow

# Agent Development Philosophy

Agents are governed workflow participants.

Agents are NOT autonomous actors.

---

# New Agent Requirements

All agents must define:
- operational purpose
- prompt versions
- allowed tools
- output schemas
- escalation thresholds
- evaluation metrics

---

# Required Agent Artifacts

Every agent should include:
- prompt file
- evaluation dataset
- replay scenarios
- structured output schema
- telemetry configuration

---

# Agent Review Checklist

Before merge:
- hallucination risks reviewed
- replay behavior validated
- escalation logic defined
- structured output enforced
- evaluation thresholds passing

---

# Prompt Development Workflow

# Prompt Governance Philosophy

Prompts are versioned operational assets.

Prompt files should exist within:

```text
/prompts
```

---

# Prompt Naming Convention

```text
<agent-name>.v<version>.md
```

Example:

```text
document-analysis-agent.v3.md
```

---

# Prompt Modification Requirements

Prompt changes require:
- replay validation
- regression evaluation
- version increment
- deployment review

---

# Prompt Constraints

Prompts should:
- remain deterministic where possible
- separate instructions from context
- enforce structured outputs
- avoid hidden assumptions

---

# Tool Development Workflow

# Tool Philosophy

Tools are governed operational capabilities exposed to agents.

---

# Tool Requirements

All tools must define:
- input schema
- output schema
- authorization model
- retry semantics
- observability metadata

---

# Tool Constraints

Tools must:
- remain replay-safe
- avoid unrestricted execution
- enforce validation
- emit telemetry

---

# Forbidden Tool Patterns

Avoid tools that:
- execute arbitrary shell commands
- expose unrestricted database access
- bypass workflow governance
- mutate workflow state directly

---

# API Development Workflow

# API Philosophy

APIs are durable operational contracts.

---

# API Requirements

All APIs must:
- expose typed schemas
- validate requests
- emit traces
- include correlation IDs
- expose OpenAPI definitions

---

# API Review Checklist

Before merge:
- schema validation added
- authorization enforced
- telemetry instrumentation added
- error responses standardized

---

# Evaluation Workflow

# Evaluation Philosophy

AI systems require continuous measurable validation.

---

# Required Evaluation Types

AI-enabled systems should include:
- replay testing
- regression testing
- hallucination evaluation
- structured output validation
- escalation accuracy evaluation

---

# Deployment Gates

Deployments should block on:
- hallucination threshold violations
- replay regressions
- evaluation degradation
- schema incompatibilities

---

# Replay-Driven Development

# Replay Philosophy

Replayability is a core engineering requirement.

Replay systems should support:
- debugging
- workflow validation
- regression analysis
- incident reconstruction

---

# Replay Validation Requirements

Replay validation should verify:
- deterministic workflow behavior
- event ordering
- trace propagation
- audit consistency

---

# Testing Strategy

# Required Test Categories

All services should include:
- unit tests
- integration tests
- replay tests
- contract tests
- observability tests

---

# AI Testing Requirements

AI systems additionally require:
- prompt regression testing
- hallucination testing
- evaluation dataset coverage
- structured output validation

---

# Observability Requirements

# Mandatory Telemetry

All services must emit:
- traces
- logs
- metrics
- audit metadata where applicable

---

# Required Telemetry Metadata

Telemetry should include:
- correlation_id
- workflow_id
- service_name
- operation_type
- trace_id

---

# Logging Standards

Logs must:
- remain structured
- expose operational context
- avoid ambiguous messaging

---

# Security Development Standards

# Security Philosophy

Security is mandatory platform infrastructure.

---

# Required Security Controls

All services must enforce:
- authentication
- authorization
- least privilege access
- secret isolation
- input validation

---

# Secret Management Rules

Secrets must never:
- exist in source control
- appear in prompts
- appear in logs

---

# Sensitive Data Handling

Developers should minimize:
- unnecessary PII propagation
- unsafe telemetry exposure
- duplicate sensitive storage

---

# Infrastructure Workflow

# Infrastructure Philosophy

Infrastructure must remain:
- declarative
- reproducible
- observable
- environment-isolated

---

# Infrastructure-as-Code Requirements

Infrastructure changes should use:
- Terraform
- Kubernetes manifests
- Docker Compose

Avoid manual infrastructure drift.

---

# Local Development Workflow

# Local Environment Goals

Local development should support:
- deterministic workflow execution
- replay testing
- observability visibility
- isolated execution

---

# Local Infrastructure Stack

Current local stack:
- Postgres
- Redpanda/Kafka
- Redis
- Temporal
- Temporal UI
- gateway-api
- workflow-engine
- agent-runtime
- tool-runtime
- evaluation-service
- operator-console
- OpenTelemetry Collector
- Jaeger
- Prometheus
- Grafana

Start the local stack from the repository root:

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml up --build -d
```

Common local URLs:

```text
Operator Console: http://localhost:3000
Gateway API: http://localhost:8000
Agent Runtime: http://localhost:8010
Tool Runtime: http://localhost:8020
Workflow Engine Metrics: http://localhost:8030/metrics
Evaluation Service: http://localhost:8040
Evaluation Service Metrics: http://localhost:8040/metrics
Temporal UI: http://localhost:8088
Grafana: http://localhost:3001
Prometheus: http://localhost:9090
Jaeger: http://localhost:16686
```

Grafana local credentials:

```text
Username: admin
Password: aegisflow
```

Local log diagnostics use Docker logs rather than Loki:

```powershell
$correlationId = "postman-manual-test"
docker logs aegisflow-gateway-api --since 15m
docker logs aegisflow-workflow-engine --since 15m
docker logs aegisflow-agent-runtime --since 15m
docker logs aegisflow-tool-runtime --since 15m
docker logs aegisflow-evaluation-service --since 15m
```

Filter structured JSON logs by `correlation_id` when investigating a workflow. Loki is deferred from the local Docker Compose stack to avoid host-specific log collection setup.

---

# Local Evaluation Validation

Phase 7 adds a local evaluation-service for deterministic AI quality scoring, dataset comparison, and evaluation telemetry.

Run the evaluation-service test suite from the repository root:

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml run --rm --no-deps `
  -v "${PWD}\apps\evaluation-service\tests:/app/tests" `
  evaluation-service sh -c "pip install --no-cache-dir -e '.[dev]' && pytest"
```

Expected current result:

```text
36 passed
```

Run the gateway-api test suite when changing workflow evaluation retrieval:

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml run --rm --no-deps `
  -v "${PWD}\apps\gateway-api\tests:/app/tests" `
  gateway-api sh -c "pip install --no-cache-dir -e '.[dev]' && pytest"
```

Expected current result:

```text
17 passed
```

Local Postman validation lives in:

```text
postman/AegisFlow_Local_Runtime.postman_collection.json
```

The collection includes evaluation-service health/readiness, dataset listing, approval and rejection dataset replay runs, evaluation run retrieval, workflow evaluation retrieval through gateway-api, Prometheus metric checks, Jaeger trace checks, Grafana dashboard checks, and bounded structured log checks.

Useful local observability checks:
- Prometheus query: `aegisflow_evaluation_service_evaluation_runs_total`
- Jaeger service: `evaluation-service`
- Grafana dashboard: `AegisFlow - Evaluation Quality`

Evaluation validation is quality telemetry only. It must not approve workflows, reject workflows, complete workflows, bypass human review, mutate workflow records, or replace approval records.

---

# CI/CD Workflow

# Pipeline Philosophy

CI/CD exists to enforce:
- replay safety
- evaluation quality
- contract consistency
- operational reliability

---

# Required Pipeline Stages

```text
Lint
    ↓
Unit Tests
    ↓
Integration Tests
    ↓
Replay Tests
    ↓
Evaluation Validation
    ↓
Security Scanning
    ↓
Build
    ↓
Deploy
```

---

# Deployment Gates

Deployments should block on:
- replay failures
- evaluation regressions
- contract violations
- security scan failures

---

# Code Review Standards

# Review Philosophy

Reviews should prioritize:
- operational clarity
- replay safety
- governance integrity
- observability completeness

---

# Required Review Categories

Review:
- architecture alignment
- telemetry completeness
- failure handling
- replay compatibility
- AI evaluation impact

---

# Documentation Requirements

# Documentation Philosophy

Architecture and operational behavior must remain explicitly documented.

---

# Required Documentation Updates

Changes require documentation updates when modifying:
- workflows
- events
- APIs
- agents
- integrations
- prompts
- security models
- evaluation behavior

---

# Failure Handling Expectations

# Failure Philosophy

Failures must remain:
- visible
- traceable
- replayable
- diagnosable

Avoid:
- silent retries
- swallowed exceptions
- hidden degradation

---

# Production Readiness Checklist

# Minimum Production Criteria

Services are not production-ready unless they include:
- observability instrumentation
- structured logging
- tracing
- replay safety
- evaluation coverage
- security validation
- documented contracts

---

# Architectural Constraints

## Constraint 1 — Workflow Engine Owns State

Workflow state transitions must only occur through the workflow engine.

---

## Constraint 2 — Replayability Is Mandatory

Workflow changes must support replay validation.

---

## Constraint 3 — AI Systems Require Evaluation

AI modifications require measurable evaluation before deployment.

---

## Constraint 4 — Governance Overrides Convenience

Governance and operational safety take precedence over rapid iteration shortcuts.

---

# Final Principle

The AegisFlow developer workflow exists to ensure enterprise AI workflow orchestration systems remain observable, replayable, governed, secure, and operationally reliable throughout the engineering lifecycle.

The workflow prioritizes:
- operational discipline
- deterministic orchestration
- replayability
- observability
- governance
- reliability
- AI safety
- long-term maintainability

over ad hoc or ungoverned development practices.
