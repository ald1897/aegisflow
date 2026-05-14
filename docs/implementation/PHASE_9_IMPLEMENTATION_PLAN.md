# Phase 9 Implementation Plan

# Service Hardening and Governance Boundaries

## Purpose

Phase 9 hardens AegisFlow's service boundaries after Phase 8 replay and recovery completion.

The original roadmap described Phase 9 as service separation. A sanity check on 2026-05-14 found that several target services are already separated locally, while the remaining gaps are governance, authorization, audit, contract validation, and runtime hardening.

This plan updates Phase 9 to focus on the work that still moves the system toward production readiness without introducing premature cloud or Kubernetes complexity.

---

# Current Baseline

Implemented local runtime services:
- gateway-api
- workflow-engine
- agent-runtime
- tool-runtime
- evaluation-service
- operator-console

Implemented platform infrastructure:
- Postgres
- Redpanda
- Redis
- Temporal
- OpenTelemetry Collector
- Jaeger
- Prometheus
- Grafana

Repository directories exist but are currently empty and not deployed in local Docker Compose:
- audit-service
- policy-engine
- notification-service

Current local governance controls:
- approval, replay, and recovery creation require `X-Actor-ID`
- workflow-engine owns workflow state mutation
- tool-runtime enforces registered tools, allowed agents, input validation, and output validation
- evaluation-service is side-effect free with respect to workflow state
- replay does not rerun workflows, agents, tools, approvals, event publication, or integrations
- recovery is bounded to explicit outbox and workflow projection remediation paths

Current local hardening gaps:
- production authentication is not implemented
- production RBAC is not implemented
- `X-Actor-ID` is a development actor boundary, not a security boundary
- policy-engine is not implemented as a runtime service
- audit-service is not implemented as a runtime service
- notification-service is not implemented as a runtime service
- service-to-service authentication is not implemented
- API and event contract validation is mostly implicit through application tests
- local compose does not include audit-service, policy-engine, or notification-service
- production log aggregation, alerting, paging, cloud infrastructure, and external mortgage system mutation remain out of scope

---

# Phase 9 Objective

Create a hardened local platform boundary where privileged actions are authorized, policy decisions are explicit, audit facts are append-only, service contracts are testable, and every implemented service has clear runtime health, observability, and deployment wiring.

---

# Scope

Phase 9 includes:
- service ownership and dependency inventory
- local role and permission model
- gateway authorization enforcement for privileged actions
- policy-engine foundation
- audit-service foundation
- service-to-service actor and correlation propagation
- API and event contract validation
- Docker Compose wiring for implemented governance services
- health, readiness, configuration, and container hardening
- documentation closeout

Phase 9 does not include:
- production OIDC, SAML, or enterprise SSO integration
- production-grade tenant isolation
- production Kubernetes, Terraform, or cloud deployment
- production alerting and paging
- external mortgage system write integrations
- external judge-model provider integration
- autonomous recovery or broad Temporal history mutation
- notification-service implementation unless required by a later explicit workstream

---

# Workstreams

## Workstream 1 - Service Boundary Inventory

Status: Not Started

Goal:
- document the current service ownership, runtime dependencies, trust boundaries, data ownership, and privileged operations

Deliverables:
- service boundary matrix for gateway-api, workflow-engine, agent-runtime, tool-runtime, evaluation-service, operator-console, policy-engine, and audit-service
- dependency map for synchronous calls, event publication, database access, and observability dependencies
- explicit list of privileged actions requiring authorization
- documentation update for any gap between architecture docs and implemented local runtime

Success criteria:
- current implemented services and placeholder service directories are clearly distinguished
- every privileged action has an owning service and target permission
- no Phase 9 implementation begins from stale service-separation assumptions

## Workstream 2 - Local Identity and RBAC Foundation

Status: Not Started

Goal:
- replace ad hoc actor-only checks with a local development identity and role model suitable for future production identity provider integration

Deliverables:
- actor context parser for gateway-api requests
- local role and permission definitions
- authorization middleware or dependency helpers
- structured authorization errors
- tests for missing actor, missing role, insufficient permission, and allowed access

Success criteria:
- approval decisions, replay creation, recovery creation, and future policy/admin actions require role-based authorization
- existing `X-Actor-ID` behavior remains usable locally when accompanied by local role context
- documentation clearly states this is local RBAC scaffolding, not production authentication

## Workstream 3 - Policy Engine Foundation

Status: Not Started

Goal:
- introduce an explicit policy decision boundary for privileged platform actions

Deliverables:
- minimal policy-engine FastAPI service
- policy decision request and response DTOs
- local deterministic policy rules for approval, replay, recovery, evaluation, and tool-governance decisions
- gateway-api client integration for policy checks where practical
- metrics, traces, structured logs, health, and readiness endpoints
- unit tests and local contract tests

Success criteria:
- policy decisions are observable, testable, and explainable
- denied actions return structured errors without mutating workflow state
- policy-engine does not become a workflow state owner

## Workstream 4 - Audit Service Foundation

Status: Not Started

Goal:
- introduce an append-only audit-service boundary for governance-relevant platform facts

Deliverables:
- minimal audit-service FastAPI service
- append-only audit event persistence model
- audit event ingestion API
- audit event retrieval API scoped by workflow and correlation ID
- audit events for approvals, replay run creation, recovery action creation, policy decisions, and authorization failures
- metrics, traces, structured logs, health, and readiness endpoints
- unit tests and local contract tests

Success criteria:
- audit records are append-only
- audit DTOs do not expose raw documents, borrower PII, secrets, prompt content, full model output, or approval comments
- workflow state, approval decisions, replay runs, and recovery actions remain owned by their existing services and tables

## Workstream 5 - Service-to-Service Trust Propagation

Status: Not Started

Goal:
- make actor identity, service identity, correlation ID, and policy/audit context consistent across internal calls

Deliverables:
- shared header conventions for actor, roles, service identity, correlation ID, and trace propagation
- gateway-to-policy and gateway-to-audit clients
- workflow-engine or event publisher audit integration where it preserves ownership boundaries
- tests for propagation and redaction behavior

Success criteria:
- internal calls preserve correlation metadata
- service-originated actions are distinguishable from human-originated actions
- no service trusts arbitrary privileged headers from untrusted external clients without gateway validation

## Workstream 6 - API and Event Contract Validation

Status: Not Started

Goal:
- make service contracts mechanically validated instead of relying only on hand-maintained documentation

Deliverables:
- OpenAPI schema export or snapshot checks for implemented HTTP services
- contract tests for gateway-api, agent-runtime, tool-runtime, evaluation-service, policy-engine, and audit-service
- event schema checks for workflow, agent, tool, approval, recovery, policy, and audit events where implemented
- documented compatibility rules for additive changes

Success criteria:
- contract drift is caught by tests or validation commands
- persisted event and API changes remain backward-compatible unless deliberately versioned
- docs and generated contracts describe the same local runtime surface

## Workstream 7 - Runtime and Container Hardening

Status: Not Started

Goal:
- improve local service runtime behavior and prepare each implemented service for independent deployment later

Deliverables:
- Docker Compose wiring for policy-engine and audit-service after implementation
- health and readiness checks that validate critical dependencies
- environment configuration validation for required service settings
- least-privilege container defaults where practical
- startup ordering and failure behavior review

Success criteria:
- local compose starts every implemented service boundary
- readiness fails when critical dependencies are unavailable
- service containers avoid unnecessary privilege where practical

## Workstream 8 - Observability and Operational Runbooks

Status: Not Started

Goal:
- ensure new governance boundaries are observable and operable in the same style as the rest of the platform

Deliverables:
- Prometheus metrics for policy decisions, authorization failures, audit ingestion, audit retrieval, and service errors
- traces for policy and audit requests
- Grafana dashboard updates or new governance dashboard
- local runbook updates for authorization failures, policy denies, audit ingestion failures, and service readiness failures

Success criteria:
- policy and audit behavior can be diagnosed with logs, traces, metrics, and persisted records
- metrics avoid workflow IDs, event IDs, trace IDs, borrower values, prompt content, approval comments, and raw payloads as labels
- runbooks include local commands and expected healthy signals

## Workstream 9 - CI and Validation Gates

Status: Not Started

Goal:
- define and implement repeatable validation for Phase 9 service-boundary changes

Deliverables:
- documented validation command matrix
- Docker Compose config validation
- service unit tests
- gateway integration tests for authorization, policy, and audit paths
- contract validation command
- local smoke checks for health, readiness, and metrics

Success criteria:
- a contributor can validate Phase 9 locally with documented commands
- CI-ready commands exist even if full hosted CI remains future work
- docs list expected current test results

## Workstream 10 - Documentation Closeout

Status: Not Started

Goal:
- keep system documentation aligned with implemented Phase 9 behavior

Deliverables:
- update Current Functionality
- update API Contracts
- update Security Model
- update Data Model
- update Event Catalog
- update Observability Strategy
- update Developer Workflow
- update Repository Structure if service layout changes

Success criteria:
- docs distinguish local RBAC and governance services from production identity and cloud deployment
- docs state exactly which services run locally
- docs preserve replay, recovery, evaluation, tool, approval, and workflow ownership boundaries

---

# Implementation Order

Recommended order:
1. Service Boundary Inventory
2. Local Identity and RBAC Foundation
3. Policy Engine Foundation
4. Audit Service Foundation
5. Service-to-Service Trust Propagation
6. API and Event Contract Validation
7. Runtime and Container Hardening
8. Observability and Operational Runbooks
9. CI and Validation Gates
10. Documentation Closeout

This order puts authorization and governance foundations ahead of runtime hardening so container and validation work can cover the real service surface.

---

# Phase 9 Completion Criteria

Phase 9 is complete when:
- all Phase 9 workstreams are marked complete with implementation notes
- gateway privileged actions enforce local role-based authorization
- policy-engine is implemented, wired locally, observable, and tested
- audit-service is implemented, wired locally, append-only, observable, and tested
- service-to-service identity and correlation propagation is documented and tested
- contract validation exists for implemented HTTP service boundaries
- local compose includes all implemented services and validates successfully
- docs reflect the final implemented capability set
- all Phase 9 changes are committed and pushed after each completed workstream

---

# Residual Risks After Phase 9

Expected remaining future work:
- production identity provider integration
- production-grade RBAC administration UI
- production tenant isolation
- production cloud or Kubernetes deployment
- production log aggregation and alerting
- external judge-model provider integration
- production mortgage system mutation adapters
- broader autonomous recovery and Temporal activity replay

These items should remain explicit future phases unless the product direction changes.
