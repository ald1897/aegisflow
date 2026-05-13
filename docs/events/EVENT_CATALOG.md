# Event Catalog

## Purpose

This document defines the event-driven communication model used throughout AegisFlow.

The event catalog establishes:
- event naming conventions
- event ownership boundaries
- event payload standards
- event lifecycle expectations
- audit propagation rules
- observability metadata requirements

Events are foundational to:
- workflow orchestration
- distributed coordination
- auditability
- replayability
- operational observability

All services must conform to the event standards defined in this document.

---

# Event Philosophy

## Events Represent Meaningful Operational Facts

Events represent immutable facts describing:
- workflow lifecycle changes
- agent execution activity
- integration outcomes
- approval decisions
- escalation actions
- operational telemetry

Events should describe:
- something that happened

not:
- commands
- requests
- implementation details

---

## Events Are Immutable

Published events must never be mutated after emission.

If operational state changes:
- emit a new event

Do not modify historical event payloads.

---

## Events Enable Replayability

Events should support:
- workflow replay
- audit reconstruction
- debugging
- observability
- evaluation pipelines

Event streams are considered operational history.

---

## Events Are Operational Contracts

Events should be treated as durable contracts between services.

Avoid:
- implicit payload structures
- undocumented schemas
- breaking schema evolution

---

# Messaging Infrastructure

## Core Technologies

- Kafka-compatible event streaming
- Redpanda for local development

---

## Messaging Goals

The messaging layer exists to support:
- asynchronous orchestration
- decoupled services
- resilient coordination
- replayability
- audit propagation

---

# Event Naming Conventions

## Naming Format

All events should follow:

```text
<domain>.<entity>.<action>
```

---

# Implemented Local Events

The current local implementation emits workflow, agent execution, supported tool invocation, and approval decision events through the `workflow-events` topic.

## Workflow Events

```text
workflow.created
workflow.state_changed
workflow.approved
workflow.rejected
workflow.completed
workflow.failed
```

Workflow events represent durable workflow lifecycle facts.

---

## Agent Execution Events

Currently emitted on successful governed agent execution:

```text
agent.execution_completed
```

Reserved for future failure handling:

```text
agent.execution_failed
```

Agent execution events represent governed AI execution facts.

They must include:
- `event_id`
- `event_type`
- `event_version`
- `workflow_id`
- `correlation_id`
- agent identifier
- agent execution identifier
- prompt identifier
- prompt version
- validation status
- confidence score
- human review requirement

Agent execution events must not be interpreted as final business decisions.

They describe validated agent output produced inside a workflow. Workflow state progression remains owned by the workflow engine, and critical mortgage actions still require human review.

---

## Tool Invocation Events

Produced by the workflow-engine when governed agent tool invocation telemetry is recorded:

```text
tool.invocation_completed
tool.invocation_failed
```

Tool invocation events represent governed tool execution facts.

They must include:
- `event_id`
- `event_type`
- `event_version`
- `workflow_id`
- `correlation_id`
- tool invocation identifier
- agent identifier
- agent execution identifier when available
- tool identifier
- execution status
- permission status
- input validation status
- output validation status

Tool invocation events must not be interpreted as business decisions.

They describe whether an approved tool invocation completed or failed inside a governed workflow context. Tool results provide supporting operational context only. Workflow state progression remains owned by the workflow engine, and critical mortgage actions still require human review.

Current implementation boundary:
- tool invocation event records are written through the outbox model
- standard Mortgage Exception Review execution produces tool invocation events for approved agent tool use
- gateway-api exposes workflow tool invocation retrieval for persisted tool invocation records

---

## Approval Events

Produced by the workflow-engine when a human approval decision is recorded:

```text
approval.decision_recorded
```

Produced by workflow decision integration when human review decisions are applied:

```text
workflow.approved
workflow.rejected
workflow.completed
```

Approval events represent human review facts.

They must include:
- `event_id`
- `event_type`
- `event_version`
- `workflow_id`
- `correlation_id`
- approval identifier
- decision
- decision reason
- reviewing operator
- review timestamp

Approval events must not be interpreted as AI decisions.

They describe a human operator decision recorded inside a governed workflow context. Workflow state progression remains owned by the workflow engine.

Current implementation boundary:
- approval decision event records are written through the outbox model
- approval decision integration can advance workflow state through `APPROVED` or `REJECTED` to `COMPLETED`
- gateway-api exposes approval decision submission and routes decisions through workflow-engine-owned Temporal decision execution
- operator-console and Postman validation submit approval decisions through gateway-api; they do not emit approval events directly

---

## Recovery Events

Produced by workflow-engine-owned recovery activity when workflow projection reconciliation completes:

```text
recovery.action_completed
```

Recovery events represent operational remediation facts, not mortgage business decisions.

They must include:
- `event_id`
- `event_type`
- `event_version`
- `workflow_id`
- `correlation_id`
- recovery action identifier
- action type
- prior state
- reconciled state

Current implementation boundary:
- recovery completion events are written through the outbox model by workflow-engine recovery activity logic
- gateway-api recovery requests create auditable recovery records but do not directly emit workflow recovery completion events
- recovery events do not approve, reject, complete, underwrite, service, or update downstream mortgage systems
- replay never emits recovery events

---

## Event Outbox Publication Status

The current local outbox publication statuses are:

```text
PENDING
PUBLISHED
FAILED
DEAD_LETTERED
```

`DEAD_LETTERED` is a local recovery status for explicitly selected failed outbox records that should not continue publishing attempts. Publishers skip dead-lettered events.
