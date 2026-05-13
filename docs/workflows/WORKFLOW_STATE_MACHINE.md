# Workflow State Machine

## Purpose

This document defines the workflow lifecycle model for AegisFlow.

The workflow state machine establishes:
- valid workflow states
- state transition rules
- escalation semantics
- retry behavior
- terminal state handling
- orchestration expectations

The workflow lifecycle is intentionally explicit, observable, deterministic, replayable, and auditable.

---

# Workflow Philosophy

A workflow represents a durable operational business process.

AI agents participate within workflows but do not control workflow state independently. The workflow-engine remains the authoritative orchestration layer for workflow state transitions.

---

# Implemented Mortgage Exception Review States

The current local implementation supports the following workflow states:

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

The standard workflow path reaches `HUMAN_REVIEW_REQUIRED` after governed agent and tool activity. A human approval or rejection then advances the workflow through `APPROVED` or `REJECTED` and finally to `COMPLETED`.

---

# Implemented Transition Graph

```text
NEW
  -> INTAKE_IN_PROGRESS
  -> DOCUMENT_ANALYSIS_PENDING
  -> RISK_REVIEW_PENDING
  -> HUMAN_REVIEW_REQUIRED
  -> APPROVED
  -> COMPLETED

HUMAN_REVIEW_REQUIRED
  -> REJECTED
  -> COMPLETED

Any non-terminal active state
  -> FAILED
```

Terminal states:
- `COMPLETED`
- `FAILED`

No transition is allowed out of a terminal state in the current local implementation.

---

# Human Review Boundary

Human review is required before the local workflow can complete through an approval or rejection path.

Implemented controls:
- approval and rejection requests require `X-Actor-ID`
- approval and rejection requests require decision context from the operator
- gateway-api routes decisions through workflow-engine-owned Temporal decision execution
- approval records, timeline entries, state transitions, and outbox events preserve the decision history

AI agents, tools, evaluation results, replay runs, and recovery actions do not approve or reject workflows.

---

# Replay And Recovery State Boundary

Phase 8 did not add recovery-specific workflow lifecycle states.

Replay and recovery records are operational records associated with a workflow:
- `workflow_replay_runs`
- `workflow_replay_steps`
- `workflow_recovery_actions`

Replay never changes workflow state. Replay reconstructs and validates persisted evidence and stores replay diagnostics only.

Outbox recovery can change a selected outbox record's publication status, including setting a failed local event to `DEAD_LETTERED`, but this is not a workflow state transition.

Workflow projection reconciliation is the only Phase 8 recovery path that can mutate a workflow record's current state, and that mutation is owned by workflow-engine recovery activity logic. It reconciles the workflow record projection to the latest persisted state transition and records recovery history with a timeline entry and `recovery.action_completed` outbox event.

Recovery does not create new approval, rejection, completion, underwriting, credit, compliance, servicing, or downstream mortgage system decisions.

---

# Replay Safety Rules

Workflow state transitions must remain deterministic and explicit.

Replay and recovery tooling must:
- preserve existing state transition history
- avoid hidden direct database state rewrites from gateway-api
- avoid rerunning agents, tools, approvals, workflow activities, event publication, or external integrations during replay
- represent recovery as explicit, auditable operational remediation
- keep unsupported or unsafe recovery actions rejected with structured errors

---

# Final Principle

The workflow state machine exists to keep operational progress clear and auditable. Replay and recovery can explain or remediate local operational failures, but they must not become alternate business decision paths.
