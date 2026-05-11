# Repository Structure

## Purpose

This document defines the physical repository organization, monorepo topology, package boundaries, infrastructure layout, and dependency organization for AegisFlow.

The repository structure exists to:
- preserve architectural clarity
- enforce operational boundaries
- improve developer onboarding
- support AI-assisted development
- reduce coupling
- improve scalability of engineering workflows
- centralize architectural visibility

The repository layout intentionally mirrors enterprise platform engineering practices.

---

# Repository Philosophy

## Monorepo Over Polyrepo

AegisFlow uses a modular monorepo architecture.

The monorepo approach provides:
- centralized architecture visibility
- shared contract consistency
- easier replay testing
- simplified dependency management
- unified CI/CD orchestration
- improved AI-assisted development context

The repository is organized around:
- independently deployable services
- shared platform packages
- governed AI assets
- infrastructure-as-code
- centralized documentation

---

# High-Level Repository Layout

```text
aegisflow/
├── apps/
├── packages/
├── prompts/
├── docs/
├── infrastructure/
├── tests/
├── scripts/
└── .github/
```

---

# Top-Level Directories

# /apps

## Purpose

Contains independently deployable runtime services and applications.

Each application should:
- own a bounded operational responsibility
- expose explicit interfaces
- emit observability telemetry
- support isolated deployment

---

## Example Applications

Examples include:
- gateway-api
- workflow-engine
- agent-runtime
- tool-runtime
- audit-service
- evaluation-service
- operator-console

---

# /packages

## Purpose

Contains reusable shared platform libraries.

Packages provide:
- shared schemas
- workflow contracts
- observability utilities
- security utilities
- event definitions

---

## Package Principles

Packages should:
- remain framework-light
- avoid business orchestration logic
- remain reusable across services

---

## Dependency Constraints

Packages may not:
- depend on apps
- contain service-specific orchestration
- contain deployment-specific logic

---

# /prompts

## Purpose

Contains governed prompt assets and evaluation prompts.

Prompts are treated as:
- versioned operational artifacts

---

## Prompt Categories

Examples:
- agent prompts
- evaluator prompts
- classifier prompts
- summarization prompts

---

## Prompt Naming Convention

Suggested format:

```text
<agent-name>.v<version>.md
```

Example:

```text
document-analysis-agent.v3.md
```

---

## Prompt Principles

Prompts should:
- remain modular
- support replayability
- support evaluation
- remain version-controlled

---

# /docs

## Purpose

Contains architectural, operational, governance, and engineering documentation.

Documentation is treated as:
- part of the platform itself

---

## Documentation Categories

Examples:
- architecture
- workflows
- security
- observability
- AI governance
- evaluation
- integrations

---

# /infrastructure

## Purpose

Contains infrastructure-as-code and local development infrastructure definitions.

---

## Infrastructure Categories

Examples:
- Terraform
- Kubernetes manifests
- Docker Compose
- local bootstrap scripts

---

# /tests

## Purpose

Contains cross-service testing infrastructure.

---

## Test Categories

Examples:
- integration tests
- replay tests
- contract tests
- evaluation tests

---

# /scripts

## Purpose

Contains operational utility scripts.

Examples:
- local environment bootstrap
- replay execution helpers
- database reset scripts
- environment setup tooling

---

# /.github

## Purpose

Contains CI/CD workflow definitions and repository automation.

---

# Applications Layout

# Application Structure Philosophy

Applications should follow consistent internal organization patterns.

---

# Suggested Structure

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

## Suggested Structure

```text
/src
├── api/
├── domain/
├── services/
├── workflows/
├── events/
├── telemetry/
├── security/
├── models/
├── config/
└── tests/
```

---

# Shared Package Layout

# Package Structure Philosophy

Shared packages should remain:
- lightweight
- reusable
- operationally focused

---

# Suggested Structure

```text
/packages/shared-events/
/packages/shared-models/
/packages/shared-observability/
/packages/shared-security/
/packages/shared-workflow-sdk/
```

---

# Shared Package Responsibilities

# shared-events

Contains:
- event schemas
- event contracts
- event validation utilities

---

# shared-models

Contains:
- shared DTOs
- common schemas
- typed interfaces

---

# shared-observability

Contains:
- tracing utilities
- logging helpers
- telemetry middleware

---

# shared-security

Contains:
- authentication helpers
- authorization middleware
- security utilities

---

# shared-workflow-sdk

Contains:
- workflow orchestration helpers
- replay utilities
- workflow contracts

---

# Infrastructure Layout

# Infrastructure Philosophy

Infrastructure should remain:
- declarative
- reproducible
- environment-isolated

---

# Suggested Layout

```text
/infrastructure
├── docker/
├── terraform/
├── kubernetes/
└── local-dev/
```

---

# Docker Infrastructure

Contains:
- local development stack
- compose definitions
- local observability stack
- mock integrations

---

# Terraform Infrastructure

Contains:
- cloud infrastructure definitions
- environment modules
- reusable infrastructure components

---

# Kubernetes Infrastructure

Contains:
- deployment manifests
- Helm charts
- ingress definitions
- scaling policies

---

# Local Development Infrastructure

Contains:
- local bootstrap tooling
- seed data
- replay datasets
- environment initialization

---

# Testing Structure

# Testing Philosophy

Testing infrastructure should support:
- replayability
- cross-service validation
- workflow verification
- AI evaluation

---

# Suggested Layout

```text
/tests
├── integration/
├── replay/
├── contract/
└── evaluation/
```

---

# Integration Tests

Validate:
- cross-service workflows
- orchestration correctness
- integration behavior

---

# Replay Tests

Validate:
- deterministic workflow replay
- event ordering
- prompt regression behavior

---

# Contract Tests

Validate:
- API contracts
- event schemas
- integration compatibility

---

# Evaluation Tests

Validate:
- AI quality
- hallucination rates
- workflow correctness
- structured outputs

---

# Dependency Model

# Dependency Philosophy

Dependencies should flow inward toward shared contracts and utilities.

---

# Allowed Dependency Flow

```text
apps → packages
apps → prompts
apps → infrastructure contracts

packages → packages
```

---

# Forbidden Dependency Flow

```text
packages → apps
apps → direct database sharing
apps → hidden internal service contracts
```

---

# Service Isolation Principles

Services should:
- communicate through APIs/events
- avoid shared persistence ownership
- expose explicit contracts

---

# AI Asset Organization

# AI Asset Philosophy

AI assets are operational platform components.

AI artifacts should remain:
- versioned
- replayable
- observable
- testable

---

# AI Asset Categories

Examples:
- prompts
- evaluators
- replay datasets
- evaluation baselines

---

# CI/CD Repository Integration

# CI/CD Philosophy

The repository should support:
- automated testing
- replay validation
- evaluation pipelines
- contract validation

---

# Suggested Pipeline Categories

Examples:
- linting
- integration testing
- replay testing
- evaluation validation
- security scanning

---

# Local Development Philosophy

# Local Environment Goals

Local environments should support:
- deterministic workflows
- replay testing
- isolated execution
- observability visibility

---

# Local Infrastructure Stack

Examples:
- Postgres
- Redpanda/Kafka
- Redis
- Grafana
- Tempo
- Loki

---

# Observability Integration

# Repository-Level Observability

All applications should integrate with shared:
- tracing standards
- logging standards
- metric conventions

---

# Security Principles

# Repository Security Model

Sensitive assets should:
- remain isolated
- avoid source control exposure
- support access boundaries

---

# Restricted Assets

Examples:
- secrets
- credentials
- production datasets
- sensitive replay artifacts

---

# Architectural Constraints

## Constraint 1 — Applications Must Remain Isolated

Applications should own bounded operational responsibilities.

---

## Constraint 2 — Shared Packages Must Remain Lightweight

Packages should avoid orchestration or workflow ownership.

---

## Constraint 3 — Prompts Are Governed Assets

Prompts must remain versioned, observable, and replayable.

---

## Constraint 4 — Documentation Is Part of the Platform

Architecture and operational behavior must remain explicitly documented.

---

# Final Principle

The AegisFlow repository structure exists to provide a scalable, observable, governed engineering environment for enterprise AI workflow orchestration systems.

The repository organization prioritizes:
- architectural clarity
- operational isolation
- replayability
- observability
- AI governance
- developer scalability
- long-term maintainability

over ad hoc or loosely structured project organization.