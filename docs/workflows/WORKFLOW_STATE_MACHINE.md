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

The workflow lifecycle is intentionally:
- explicit
- observable
- deterministic
- replayable
- auditable

All workflow implementations should conform to the rules defined in this document.

---

# Workflow Philosophy

A workflow represents a durable operational business process.

Workflows are:
- long-running
- stateful
- replayable
- event-driven
- observable

AI agents participate within workflows but do not control workflow state independently.

The workflow engine remains the authoritative orchestration layer.

---

# Workflow Lifecycle Overview

Every workflow progresses through a series of explicit states.

States represent:
- operational progress
- orchestration status
- escalation conditions
- approval requirements
- terminal outcomes

Workflow states must always be:
- persisted
- traceable
- auditable

---

# High-Level State Diagram

```text
NEW
 ↓
INTAKE_IN_PROGRESS
 ↓
DOCUMENT_ANALYSIS_PENDING
 ↓
DOCUMENT_ANALYSIS_COMPLETED
 ↓
RISK_REVIEW_PENDING
 ↓
DECISION_PENDING
 ↓
┌───────────────────────┐
│ Human Review Needed?  │
└───────────┬───────────┘
            │
      YES   ▼   NO
   HUMAN_REVIEW_REQUIRED
            ↓
      HUMAN_REVIEW_IN_PROGRESS
            ↓
         APPROVED
            │
            ▼
        COMPLETED

OR

         REJECTED
            │
            ▼
         COMPLETED