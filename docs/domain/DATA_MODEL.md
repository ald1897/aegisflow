# Data Model

## Purpose

This document defines the data model principles, persistence responsibilities, ownership boundaries, and operational data expectations for AegisFlow.

The data model exists to support:
- durable workflow orchestration
- event-driven coordination
- governed AI execution
- human-in-the-loop approvals
- auditability
- replayability
- observability
- regulated financial operations

All platform data design must align with the domain language, workflow lifecycle, security model, event catalog, and architecture constraints defined across the AegisFlow documentation set.

---

# Data Model Philosophy

## Data Supports Governed Workflows

AegisFlow is a workflow orchestration platform augmented by AI capabilities.

The data model must therefore prioritize:
- workflow state integrity
- audit reconstruction
- explicit ownership
- deterministic replay
- operational traceability
- human approval visibility

over convenience-oriented storage or opaque AI memory patterns.

---

## PostgreSQL Is the System of Record

PostgreSQL stores authoritative operational data for the platform.

Authoritative data includes:
- workflow records
- workflow state history
- approval records
- audit records
- agent execution metadata
- tool invocation metadata
- integration exchange metadata
- evaluation results
- prompt version metadata
- platform configuration data

Services may cache or project this data elsewhere, but PostgreSQL remains the authoritative persistence layer unless a future architecture document explicitly defines another durable owner.

---

## Redis Is Ephemeral Only

Redis is used for short-lived operational coordination.

Redis may store:
- cache entries
- rate limit counters
- temporary session state
- transient streaming coordination data
- short-lived workflow UI state
- ephemeral lock metadata

Redis must not store:
- authoritative workflow state
- approval decisions
- audit records
- compliance evidence
- durable agent outputs
- final operational decisions

Loss of Redis data must not cause loss of authoritative workflow history or auditability.

---

## Events Are Operational Facts

Kafka-compatible event streams represent immutable operational facts.

Events support:
- workflow coordination
- asynchronous service communication
- audit propagation
- replay analysis
- observability pipelines

Events are durable operational contracts, but they do not replace the system of record for authoritative query state.

If an event and a persisted workflow record disagree, the discrepancy must be treated as an operational defect requiring investigation.

---

## Temporal Owns Durable Execution History

Temporal stores workflow execution history required for durable orchestration.

Temporal history supports:
- retries
- replay
- long-running execution
- activity recovery
- workflow timeout behavior
- deterministic orchestration analysis

Temporal workflow history is not a substitute for domain persistence.

Domain records must still be persisted where operational querying, audit retrieval, reporting, or compliance reconstruction require stable platform data.

---

# Data Classification

## Classification Model

Platform data should be classified before storage, transmission, logging, or exposure through APIs.

Suggested classifications:
- Public
- Internal
- Confidential
- Restricted

---

## Public Data

Public data is information safe for unrestricted disclosure.

Production workflow data should rarely be classified as Public.

---

## Internal Data

Internal data is operational platform data not intended for external disclosure.

Examples include:
- service metadata
- non-sensitive configuration
- internal identifiers
- operational health metadata

---

## Confidential Data

Confidential data requires controlled access and limited disclosure.

Examples include:
- workflow summaries
- escalation explanations
- operational annotations
- agent execution summaries
- integration response metadata

---

## Restricted Data

Restricted data requires the highest level of platform protection.

Examples include:
- borrower data
- financial records
- compliance artifacts
- identity attributes
- approval decisions tied to regulated workflows
- prompt inputs containing sensitive operational content
- AI outputs derived from sensitive borrower or financial records

Restricted data must be minimized, access-controlled, encrypted where appropriate, and excluded from logs unless explicitly redacted.

---

# Canonical Identifiers

## Identifier Requirements

Operational records must include identifiers that support traceability across services, events, workflows, logs, traces, and audit records.

---

## workflow_id

`workflow_id` uniquely identifies a Workflow.

It must be present on:
- workflow records
- workflow state transitions
- approval records
- agent execution records
- tool invocation records
- integration exchange records
- audit records
- workflow-related events

---

## correlation_id

`correlation_id` provides end-to-end operational traceability.

It must propagate across:
- API requests
- workflow execution
- agent execution
- tool invocation
- integration calls
- events
- logs
- traces
- audit records

---

## trace_id

`trace_id` links records to distributed tracing telemetry.

It should be captured when data is produced during an instrumented request, workflow activity, agent run, or integration call.

---

## actor_id

`actor_id` identifies the authenticated human or service actor responsible for an action.

It must be captured for:
- approval decisions
- workflow overrides
- replay actions
- policy changes
- prompt changes
- administrative operations

AI agents are not final approval actors for critical workflow decisions.

---

## tenant_id

`tenant_id` is a future-compatible boundary identifier.

It may be included in data contracts to support future tenant isolation, authorization filtering, and operational segmentation.

Presence of `tenant_id` does not imply that full multi-tenancy is implemented.

---

# Core Data Ownership Boundaries

# Workflow Records

## Definition

A Workflow Record is the authoritative persisted representation of a financial operations workflow.

Workflow records represent:
- workflow identity
- workflow type
- current workflow state
- operational priority
- creation metadata
- assigned operational ownership
- completion metadata

---

## Ownership

The workflow-engine owns workflow lifecycle coordination.

The workflow-database stores authoritative workflow metadata.

The gateway-api may expose workflow data through typed response models but must not expose persistence models directly.

---

## Requirements

Workflow records must:
- include `workflow_id`
- include `correlation_id`
- expose current state
- preserve creation and update timestamps
- support operational querying
- remain consistent with the workflow state machine

---

# Workflow State Transitions

## Definition

A Workflow State Transition records a change from one explicit workflow state to another.

State transitions represent:
- operational progress
- orchestration decisions
- escalation conditions
- approval requirements
- terminal outcomes

---

## Requirements

State transition records must capture:
- prior state
- new state
- transition reason
- transition timestamp
- initiating service or actor
- related workflow execution context
- correlation metadata

State transitions must be:
- persisted
- observable
- auditable
- replay-aware

Hidden workflow transitions are prohibited.

---

# Approval Records

## Definition

An Approval Record captures a human decision required for a critical workflow action.

Approval records represent:
- approval request context
- reviewer identity
- decision outcome
- decision rationale
- decision timestamp
- authorization context

---

## Requirements

Approval records must:
- include `workflow_id`
- include `actor_id`
- preserve decision rationale
- distinguish approved, rejected, and escalated outcomes
- support audit retrieval
- remain immutable after decision finalization

Critical workflow decisions must not be represented only as agent output.

---

# Audit Records

## Definition

An Audit Record is an immutable record of a security-relevant, workflow-relevant, or governance-relevant platform action.

Audit records support:
- compliance review
- forensic reconstruction
- replay analysis
- operator accountability
- governance validation

---

## Requirements

Audit records must capture:
- action performed
- actor identity or service identity
- affected resource
- timestamp
- `workflow_id` when applicable
- `correlation_id`
- authorization outcome
- relevant decision metadata

Audit records must be append-only.

Updates to historical audit records are prohibited.

---

# Agent Execution Records

## Definition

An Agent Execution Record captures metadata about a constrained AI agent execution within a workflow.

Agent execution records represent:
- agent identity
- prompt version
- model metadata
- input classification
- structured output status
- confidence signals
- escalation recommendation
- token usage metadata
- execution timing

---

## Requirements

Agent execution records must:
- include `workflow_id`
- include `correlation_id`
- reference prompt and model versions
- capture validation status
- expose confidence or quality signals where applicable
- preserve enough metadata for audit and evaluation

AI outputs must be treated as untrusted until validated by workflow logic, policy checks, or human review.

Agent records must not imply autonomous authority over workflow state.

---

# Tool Invocation Records

## Definition

A Tool Invocation Record captures execution metadata for a governed tool call initiated by an agent or workflow activity.

Tool invocation records represent:
- tool identity
- invoking agent or workflow activity
- permission context
- input validation status
- execution result
- retry metadata
- error metadata
- timing metadata

---

## Requirements

Tool invocation records must:
- include `workflow_id` when workflow-scoped
- include `correlation_id`
- identify the authorized caller
- preserve permission evaluation metadata
- capture success or failure outcome
- support replay-safe analysis

Tool invocation data must not expose secrets, unrestricted credentials, or sensitive payloads in logs.

---

# Integration Exchange Records

## Definition

An Integration Exchange Record captures metadata about interaction with an external or simulated enterprise system.

Integration exchanges represent:
- external system identity
- adapter identity
- request classification
- response classification
- schema validation result
- retry behavior
- failure details
- operational timing

---

## Requirements

Integration exchange records must:
- include `correlation_id`
- include `workflow_id` when associated with a workflow
- identify the integration adapter
- capture schema validation outcomes
- support transient failure diagnosis
- avoid unnecessary PII propagation

External systems must remain behind governed adapters.

Workflow logic must not depend on unmediated external system access.

---

# Evaluation Records

## Definition

An Evaluation Record captures assessment results for AI quality, workflow reliability, or replay behavior.

Evaluation records represent:
- evaluation run identity
- evaluated workflow or agent execution
- prompt version
- model version
- scoring method
- observed quality metrics
- regression result
- evaluator metadata

---

## Requirements

Evaluation records must:
- be reproducible where practical
- preserve evaluated artifact references
- support historical comparison
- identify prompt and model versions
- distinguish production workflow outcomes from evaluation-only results

Evaluation records must not mutate production workflow outcomes.

---

# Prompt Version Metadata

## Definition

Prompt Version Metadata describes governed prompt assets used by AI agents and evaluators.

Prompt metadata represents:
- prompt identifier
- prompt version
- owning agent or evaluator
- approval status
- deployment status
- rollback metadata
- evaluation association

---

## Requirements

Prompt metadata must:
- be versioned
- be auditable
- support rollback
- identify associated agents
- support evaluation traceability

Production agent execution must reference explicit prompt versions.

Untracked prompt changes are prohibited.

---

# Observability Metadata

## Definition

Observability Metadata links data records to operational telemetry.

Observability metadata supports:
- distributed tracing
- structured logging
- metrics correlation
- workflow timelines
- incident response

---

## Requirements

Relevant records should include:
- `correlation_id`
- `trace_id`
- service name
- environment
- execution timestamp
- workflow context

Observability metadata must support debugging without exposing sensitive payloads unnecessarily.

---

# Storage Responsibilities

# PostgreSQL

## Responsibility

PostgreSQL stores authoritative operational records.

It is responsible for:
- durable workflow metadata
- approval history
- audit history
- operational state
- configuration records
- evaluation results
- prompt metadata
- integration exchange metadata

---

## Design Expectations

PostgreSQL schemas should:
- use explicit typed fields
- preserve referential integrity where practical
- support operational queries
- support audit retrieval
- support additive schema evolution
- avoid storing unbounded opaque blobs as primary operational records

---

## Current Local Implementation

The local implementation currently persists:
- workflow records
- workflow state transitions
- workflow timeline entries
- workflow event outbox records
- agent execution records
- tool invocation records
- approval records

Approval records currently preserve:
- approval identity
- workflow identity
- correlation identity
- approval or rejection decision
- decision reason
- operator comment
- reviewing operator identity
- review timestamp
- bounded decision metadata

Approval records are written by workflow-engine-owned decision execution.

gateway-api and operator-console may request approval or rejection actions, but they do not own authoritative approval persistence or workflow state transition logic.

---

# pgvector

## Responsibility

pgvector supports semantic retrieval and contextual lookup.

It may be used for:
- document embedding lookup
- contextual workflow search
- knowledge retrieval
- AI-assisted summarization context

---

## Constraints

Vector search results must not bypass workflow governance.

Embeddings derived from sensitive data must follow the same protection expectations as their source data.

pgvector is an extension of PostgreSQL persistence, not an autonomous AI memory layer.

---

# Redis

## Responsibility

Redis supports ephemeral runtime behavior.

It may be used for:
- caching
- rate limiting
- short-lived coordination
- transient streaming state
- temporary UI session state

---

## Constraints

Redis must be treated as disposable.

The system must tolerate Redis cache loss without losing:
- workflow state
- approval history
- audit history
- compliance evidence
- final AI execution records

---

# Kafka and Redpanda

## Responsibility

Kafka-compatible event streaming supports asynchronous event propagation.

Redpanda is used for local development.

The event stream supports:
- workflow lifecycle events
- agent execution events
- approval events
- integration events
- audit propagation
- observability pipelines

---

## Constraints

Events must be:
- immutable
- schema-governed
- traceable
- replayable

Events should describe facts that happened, not commands or hidden implementation details.

---

# Temporal

## Responsibility

Temporal stores durable workflow execution history.

Temporal supports:
- workflow replay
- retries
- activity scheduling
- timeout handling
- failure recovery
- deterministic orchestration

---

## Constraints

Temporal history must not be the only source for:
- compliance audit records
- approval decisions
- operational query projections
- long-term reporting

Workflow side effects must remain idempotent and replay-safe.

---

# Schema Design Principles

## Strong Typing Required

Data contracts should use strongly typed schemas whenever practical.

Backend services should favor:
- Pydantic models
- explicit DTOs
- validated payloads
- stable response models
- schema validation at trust boundaries

---

## Persistence Models Are Internal

Persistence models must not be exposed directly through APIs.

APIs should expose:
- request DTOs
- response DTOs
- structured error models
- stable operational contracts

This protects internal schema flexibility and supports backward compatibility.

---

## Validate Before Persistence

Data should be validated before durable persistence.

Validation should cover:
- schema correctness
- authorization context
- workflow state compatibility
- required identifiers
- data classification
- payload size limits
- sensitive data handling expectations

AI-generated data must be validated before persistence or workflow use.

---

## Prefer Additive Evolution

Schema evolution should favor additive changes.

Preferred changes include:
- adding nullable fields
- adding optional metadata
- adding new event versions
- adding new projections
- expanding enumerations with compatibility review

Avoid:
- silent field removal
- incompatible enum changes
- ambiguous payload reinterpretation
- destructive migrations without operational planning

---

# Data Lifecycle

# Creation

Data creation must occur through authorized services and governed workflow paths.

Records should capture:
- creation timestamp
- creating actor or service
- correlation metadata
- workflow context when applicable

---

# Mutation

Mutable operational records should preserve history where state changes are meaningful.

Workflow state changes, approval decisions, policy changes, and audit-relevant actions must produce explicit records or events.

---

# Immutability

The following records should be append-only or immutable after finalization:
- audit records
- approval decisions
- finalized workflow state transitions
- emitted events
- prompt version records
- replay execution records

Corrections should be represented as additional records, not silent historical mutation.

---

# Retention

Retention policies must consider:
- regulatory requirements
- audit needs
- incident response
- replay requirements
- privacy obligations
- storage cost

The platform should retain enough data to reconstruct workflow execution and governance decisions.

Retention periods should be explicit before production deployment.

---

# Deletion and Redaction

Deletion and redaction must preserve auditability.

When sensitive content must be removed or masked:
- retain non-sensitive operational metadata where allowed
- preserve audit evidence of the redaction action
- avoid breaking workflow reconstruction
- avoid deleting immutable audit facts without an approved compliance process

---

# Replay and Idempotency

## Replay Safety

Replay must not create duplicate irreversible side effects.

Replay-aware records should distinguish:
- original execution
- retry execution
- replay execution
- evaluation-only replay

---

## Idempotent Writes

Writes performed by workflow activities must be idempotent.

Idempotency should use stable identifiers such as:
- `workflow_id`
- activity identity
- event identity
- external request identity
- tool invocation identity

Duplicate execution must not corrupt workflow state, approval records, audit records, or integration history.

---

# Privacy and Sensitive Data Handling

## Data Minimization

Services should store the minimum sensitive data required for operational correctness, auditability, and regulated workflow execution.

Avoid unnecessary duplication of:
- borrower data
- financial records
- compliance artifacts
- prompt inputs
- integration payloads

---

## Logging Restrictions

Logs must not contain unrestricted sensitive payloads.

Structured logs should prefer:
- identifiers
- classification labels
- validation outcomes
- timing metadata
- error categories
- redacted summaries

---

## AI Data Handling

AI inputs and outputs may contain sensitive workflow context.

AI-related records must capture:
- prompt version
- model version
- execution metadata
- validation status
- confidence signals
- escalation recommendation where applicable

They should avoid storing raw sensitive content unless required for audit, evaluation, or replay.

---

# Query and Projection Model

## Operational Queries

Operational queries should be served from authoritative records or governed projections.

Examples include:
- workflow list views
- workflow detail views
- approval queues
- audit timelines
- agent execution history
- integration status history
- evaluation summaries

---

## Projections

Read projections may be built for performance or UI needs.

Projections must:
- be rebuildable from authoritative data or events
- preserve correlation metadata
- avoid becoming hidden systems of record
- expose freshness expectations where relevant

---

## Reporting

Reporting data should preserve operational meaning.

Reports should distinguish:
- workflow state
- approval outcome
- AI recommendation
- human decision
- integration result
- evaluation score

AI recommendations must not be presented as final business decisions unless a human approval or workflow policy explicitly produced that outcome.

---

# Data Quality Requirements

## Required Quality Signals

Operational records should support data quality review through:
- schema validation status
- required identifier presence
- source service identity
- timestamp consistency
- workflow state compatibility
- authorization context

---

## Failure Handling

Invalid data must:
- fail loudly internally
- emit structured logs
- produce metrics
- preserve diagnostic context
- avoid unsafe workflow progression

External error responses must avoid leaking sensitive implementation details.

---

# Anti-Patterns

The following patterns are prohibited:
- storing authoritative workflow state only in Redis
- allowing agents to directly mutate protected records
- using event payloads as undocumented schemas
- exposing database entities directly through APIs
- storing secrets in prompts, logs, events, or workflow records
- treating AI output as approved business truth without validation
- mutating audit history in place
- bypassing workflow state transitions through direct database updates
- storing sensitive integration payloads without classification or retention review

---

# Final Principle

The AegisFlow data model exists to preserve durable, observable, governed workflow execution in a regulated financial operations environment.

Data design should consistently prioritize:
- workflow integrity
- auditability
- replayability
- least privilege
- sensitive data protection
- human approval traceability
- operational clarity

over storage convenience, autonomous AI assumptions, or hidden system behavior.
