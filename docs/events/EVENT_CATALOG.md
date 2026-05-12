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

The current local implementation emits workflow, agent execution, and supported tool invocation events through the `workflow-events` topic.

## Workflow Events

```text
workflow.created
workflow.state_changed
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
- gateway-api does not yet expose workflow tool invocation retrieval
