# Workflow Engine

## Purpose

This document defines the orchestration architecture, execution lifecycle, state management model, retry semantics, replay behavior, and governance boundaries of the AegisFlow workflow engine.

The workflow engine is the operational core of the platform.

It exists to provide:
- deterministic workflow orchestration
- durable state management
- event-driven execution
- replayability
- fault isolation
- escalation coordination
- human-in-the-loop governance
- AI-assisted operational execution

The workflow engine owns workflow coordination across all platform components.

---

# Workflow Philosophy

## Workflows Represent Long-Running Operational Processes

Workflows are not request-response transactions.

They represent:
- durable operational processes
- asynchronous execution chains
- multi-system coordination
- AI-assisted decision flows
- human escalation paths

Workflows may execute for:
- seconds
- minutes
- hours
- days

---

## The Workflow Engine Is the Source of Truth

The workflow engine is authoritative for:
- workflow state
- workflow progression
- orchestration sequencing
- retry coordination
- escalation routing

No external service may mutate workflow state directly.

---

## Event-Driven Coordination Over Direct Invocation

Workflow progression should primarily occur through:
- immutable events

Avoid tightly coupled synchronous orchestration chains.

---

## Replayability Is Mandatory

Every workflow execution must support:
- deterministic replay
- forensic reconstruction
- regression analysis
- historical debugging

Replayability is a first-class architectural requirement.

---

# High-Level Architecture

## Core Workflow Engine Responsibilities

The workflow engine is responsible for:
- workflow lifecycle management
- state persistence
- event publication
- orchestration sequencing
- retry coordination
- timeout handling
- escalation routing
- replay execution
- workflow observability

---

# Workflow Lifecycle

# Workflow Lifecycle States

All workflows transition through explicit lifecycle states.

Implemented local Mortgage Exception Review states:

```text
NEW
INTAKE_IN_PROGRESS
DOCUMENT_ANALYSIS_PENDING
RISK_REVIEW_PENDING
HUMAN_REVIEW_REQUIRED
APPROVED
REJECTED
COMPLETED
FAILED
```

Replay and recovery records are operational records, not workflow lifecycle states. Phase 8 did not add a `REPLAYING` workflow state. A workflow may have replay runs or recovery actions associated with it while its authoritative workflow state remains one of the states listed above.

---

# Implemented Replay Behavior

Phase 8 implements local replay through gateway-api using persisted records in PostgreSQL.

Implemented replay behavior:
- reconstructs workflow evidence from workflow records, state transitions, timeline entries, outbox events, agent executions, tool invocations, approval records, evaluation runs, and evaluation results
- supports `history_reconstruction` and `deterministic_validation` replay modes
- persists replay run records in `workflow_replay_runs`
- persists replay step records in `workflow_replay_steps`
- supports explicit replay run idempotency when a caller supplies a replay run identifier
- exposes read-only replay diagnostics without creating replay records
- emits bounded traces, metrics, structured logs, and dashboard telemetry

Replay is side-effect free. It does not:
- mutate workflow state
- rerun Temporal workflows or activities
- rerun agents or tools
- republish events
- redispatch approval or rejection decisions
- call external mortgage systems
- create mortgage approval, rejection, underwriting, credit, compliance, or servicing decisions

Incomplete workflow evidence is represented as warning or skipped replay steps instead of being repaired by replay.

---

# Implemented Recovery Behavior

Phase 8 implements bounded local recovery for explicit operational remediation.

Gateway-owned local recovery behavior:
- classifies workflow outbox records as informational, retryable, dead-letterable, or terminal
- retries explicitly selected retryable `workflow_event_outbox` records through the existing event publisher boundary
- rejects retry for already-published or dead-lettered events
- marks explicitly selected dead-letterable local outbox records as `DEAD_LETTERED`
- creates `workflow_recovery_actions` records for retry, dead-letter, and workflow recovery requests
- exposes dry-run workflow recovery checks before mutating workflow recovery commands
- requires local actor identity and a recovery reason for recovery action creation

Workflow-engine-owned recovery behavior:
- owns projection reconciliation through the `reconcile_workflow_projection` Temporal activity
- reconciles a workflow record projection to the latest persisted state transition only when an accepted recovery command is executed by workflow-engine logic
- writes a `RECOVERY_ACTION_RECORDED` timeline entry for completed projection recovery
- writes a `recovery.action_completed` outbox event for completed projection recovery

Recovery does not create approval or rejection decisions and does not grant replay authority over mortgage outcomes. Production autonomous recovery, broad activity replay, workflow restart, Temporal history mutation, and downstream mortgage system recovery remain future hardening work.

---

# Replay Safety Rules

Workflow definitions must remain deterministic. Telemetry and recovery side effects belong in activities, API handlers, and publisher boundaries, not inside replay-sensitive workflow code.

All mutating recovery logic must:
- be explicit and auditable
- require actor identity and reason
- preserve workflow history
- route workflow state mutation through workflow-engine-owned logic
- store bounded metadata only
