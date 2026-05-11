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
```

The gateway-api remains the primary API surface for workflow initiation and operational query access.

The `agent-executions` endpoint returns persisted agent execution records associated with a workflow. It must not expose unrestricted prompt input, sensitive borrower payloads, secrets, or internal persistence entities directly.

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
