# Phase 5 Implementation Plan

## Purpose

This document defines the continuous implementation plan for Phase 5 of AegisFlow.

Phase 5 introduces Human Review and Operator Console capabilities.

The plan exists to:
- guide implementation work across multiple development sessions
- preserve architectural alignment with existing platform documentation
- keep human approval explicit, auditable, and workflow-owned
- prevent AI outputs or tool results from becoming final mortgage decisions
- provide clear validation checkpoints before Phase 5 is considered complete

This document must be updated as implementation progresses.

---

# Phase 5 Objective

Phase 5 will introduce operational human-in-the-loop review.

The platform must support authenticated operator review of workflows that have reached:

```text
HUMAN_REVIEW_REQUIRED
```

Human review must:
- expose workflow context needed for review
- show workflow timeline, agent execution records, and tool invocation records
- capture operator decisions and comments
- persist approval records
- emit approval events
- advance workflow state only through workflow-engine-owned transitions
- preserve auditability for regulated mortgage operations

AI agents may provide supporting context.

AI agents must not:
- approve a workflow
- reject a workflow
- complete a workflow
- mutate approval records
- impersonate a human operator
- bypass human review for critical mortgage actions

---

# Business Context

## Current Business Capability

AegisFlow can currently demonstrate a governed Mortgage Exception Review workflow from creation through required human review.

Current Phase 4 capability proves:
- a mortgage exception review case can be created
- the workflow can run durably through Temporal
- governed agents can produce validated structured outputs
- approved tools can retrieve synthetic supporting context through tool-runtime
- workflow timeline, agent execution, and tool invocation history can be queried
- the workflow stops at `HUMAN_REVIEW_REQUIRED`

## Phase 5 Business Goal

Phase 5 will demonstrate how a mortgage operations user can review a prepared exception case and record a controlled business decision.

For mortgage stakeholders, this means AegisFlow will begin to show the operational handoff from AI-assisted preparation to accountable human decisioning.

Examples of business value:
- review cases from an operator queue
- inspect case preparation history
- compare workflow state, agent outputs, and tool results before decisioning
- record approval or rejection with comments
- preserve a durable audit trail for review actions

## Business Boundary

Phase 5 will not connect to production mortgage systems.

Phase 5 will not perform final underwriting, credit, compliance, or servicing actions in external systems.

Approval and rejection actions will be local workflow decisions for the simulated Mortgage Exception Review process.

Human review remains the authority boundary for critical workflow outcomes.

---

# Current Implementation Baseline

Phase 5 starts from the completed Phase 4 baseline.

Implemented runtime services:
- `gateway-api`
- `workflow-engine`
- `agent-runtime`
- `tool-runtime`
- Postgres
- Redpanda
- Redis
- Temporal
- Temporal UI

Implemented persisted records:
- `workflow_records`
- `workflow_state_transitions`
- `workflow_timeline_entries`
- `workflow_event_outbox`
- `agent_execution_records`
- `tool_invocation_records`

Implemented workflow behavior:
- `NEW`
- `INTAKE_IN_PROGRESS`
- `DOCUMENT_ANALYSIS_PENDING`
- `RISK_REVIEW_PENDING`
- `HUMAN_REVIEW_REQUIRED`

Implemented query APIs:
- workflow retrieval
- workflow timeline retrieval
- workflow agent execution retrieval
- workflow tool invocation retrieval

Phase 5 must extend this baseline without weakening workflow-engine ownership of state transitions.

---

# Target Phase 5 Scope

## In Scope

Phase 5 should implement:
- operator-console application foundation
- human review queue
- workflow detail view for operator review
- approval record persistence
- approval decision API
- approval comments
- approval timeline entries
- approval events through the existing outbox pattern
- workflow-engine handling for approved and rejected decisions
- workflow transition to `APPROVED` or `REJECTED`
- workflow completion after human decision where state machine rules permit
- Postman requests for manual approval validation
- automated tests for approval persistence, API behavior, and workflow transitions
- documentation updates

---

## Out Of Scope

Phase 5 must not implement:
- production identity provider integration
- production RBAC policy engine
- real mortgage system update actions
- final underwriting automation
- autonomous approval by AI agents
- document upload or document content management
- notification delivery outside local simulation
- full audit-service separation
- distributed tracing stack
- AI evaluation scoring

---

# Proposed Runtime Architecture

## Frontend Application

Use the existing application boundary:

```text
apps/operator-console
```

The operator-console should be a local frontend application for:
- review queue visibility
- workflow detail inspection
- approval and rejection actions
- timeline and audit review

The operator-console must not:
- mutate workflow state directly outside gateway-api contracts
- call agent-runtime directly
- call tool-runtime directly
- hide approval audit metadata
- present AI output as final business truth

---

## Service Communication Flow

```text
Operator Console
    ->
Gateway API
    ->
Workflow Engine
    ->
PostgreSQL
    ->
Workflow Event Outbox
```

The gateway-api remains responsible for:
- API request validation
- approval DTO boundaries
- operator actor propagation
- operational query access

The workflow-engine remains responsible for:
- workflow state transitions
- durable workflow progression
- replay-safe transition behavior
- approval-driven completion behavior

PostgreSQL remains responsible for:
- authoritative workflow records
- approval records
- state transition records
- timeline entries
- event outbox records

---

# Data Model Additions

## Approval Records

Phase 5 should add a durable record aligned with `DATA_MODEL.md`.

Suggested table:

```text
approval_records
```

Required conceptual fields:
- `approval_id`
- `workflow_id`
- `correlation_id`
- `decision`
- `decision_reason`
- `comment`
- `reviewed_by`
- `reviewed_at`
- `created_at`
- `approval_metadata`

The table should store operator decision metadata and review comments.

It must not store:
- secrets
- raw document contents
- unrestricted borrower PII
- unvalidated external payloads

---

# Event Additions

Phase 5 should add events through the existing outbox model.

Expected event types:

```text
approval.decision_recorded
workflow.approved
workflow.rejected
workflow.completed
```

Approval events must include:
- `event_id`
- `event_type`
- `event_version`
- `workflow_id`
- `correlation_id`
- `approval_id`
- `decision`
- `reviewed_by`
- decision timestamp

Approval events must describe operational facts.

They must not be commands or hidden implementation signals.

---

# API Additions

## gateway-api Operational Review API

Expected endpoints:

```text
GET /api/v1/reviews/human-review-queue
GET /api/v1/workflows/{workflow_id}/review-context
GET /api/v1/workflows/{workflow_id}/approvals
POST /api/v1/workflows/{workflow_id}/approvals
```

The review context endpoint should aggregate existing workflow-owned data:
- workflow record
- workflow timeline
- agent execution records
- tool invocation records
- approval records

The approval creation endpoint must:
- require an actor identifier
- accept explicit approval or rejection
- require a decision reason or comment
- reject duplicate terminal decisions
- reject decisions for workflows not in a reviewable state
- return DTOs, not persistence models

---

# Workflow Engine Changes

Phase 5 should extend workflow handling for human decisions.

Expected workflow behavior:
- workflow reaches `HUMAN_REVIEW_REQUIRED`
- operator records approval or rejection
- workflow-engine validates the current state
- workflow-engine records the transition to `APPROVED` or `REJECTED`
- workflow-engine records completion when permitted by the state machine
- timeline and outbox records are emitted

The workflow-engine must remain the only component that advances workflow state.

Approval API handlers must not directly rewrite workflow state without workflow-engine transition logic.

---

# Operator Console Changes

## Initial Views

Phase 5 should implement:
- review queue view
- workflow detail view
- timeline panel
- agent execution panel
- tool invocation panel
- approval decision panel

## Operator Actions

Phase 5 should support:
- approve workflow
- reject workflow
- submit comments
- refresh workflow state
- inspect prior approval records

## UX Constraints

The operator-console should be functional and operationally focused.

It should not use marketing-style layouts.

The first screen should be the review queue, not a landing page.

The UI must clearly distinguish:
- workflow facts
- agent outputs
- tool outputs
- operator decisions

---

# Implementation Workstreams

## Workstream 1 - Approval Persistence And Events

Status: Completed

Tasks:
- add Alembic migration for `approval_records` - Complete
- add persistence models to gateway-api and workflow-engine as needed - Complete
- add approval event types - Complete
- add approval timeline entry types - Complete
- add approval record service logic - Complete
- add idempotency and duplicate decision protections - Complete

Completion criteria:
- approval records are persisted by workflow - Met
- approval timeline entries are created - Met
- approval events are written through the outbox model - Met
- duplicate approval decisions fail safely or are idempotent by design - Met

---

## Workstream 2 - Workflow Decision Integration

Status: Completed

Tasks:
- add workflow-engine activity for human approval decisions - Complete
- validate current workflow state before decisioning - Complete
- transition approved workflows through valid state machine states - Complete
- transition rejected workflows through valid state machine states - Complete
- preserve Temporal replay safety - Complete
- add workflow-engine tests - Complete

Completion criteria:
- only `HUMAN_REVIEW_REQUIRED` workflows can be decisioned - Met
- approved workflows reach the expected approved or completed state - Met
- rejected workflows reach the expected rejected or completed state - Met
- invalid transitions are rejected and auditable - Met

---

## Workstream 3 - Gateway Review APIs

Status: Completed

Tasks:
- add human review queue endpoint - Complete
- add workflow review context endpoint - Complete
- add workflow approvals retrieval endpoint - Complete
- add workflow approval decision endpoint - Complete
- add DTOs for review queue, review context, and approval records - Complete
- add gateway-api tests - Complete

Completion criteria:
- gateway can list workflows awaiting human review - Met
- gateway can return full review context for a workflow - Met
- gateway can record approval and rejection decisions - Met
- gateway returns structured errors for invalid review actions - Met

---

## Workstream 4 - Operator Console Foundation

Status: Completed

Tasks:
- inspect existing `apps/operator-console` structure - Complete
- choose implementation approach aligned with repository patterns - Complete
- create local frontend app if needed - Complete
- add Docker Compose support if needed - Complete
- add review queue screen - Complete
- add API client configuration - Complete

Completion criteria:
- operator-console starts locally - Met
- first screen shows human review queue - Met
- queue fetches data from gateway-api - Met
- UI uses operational layout suitable for repeated review work - Met

---

## Workstream 5 - Workflow Review Experience

Status: Completed

Tasks:
- add workflow detail view - Complete
- display workflow metadata and current state - Complete
- display timeline entries - Complete
- display agent execution summaries - Complete
- display tool invocation summaries - Complete
- add approval and rejection form - Complete
- capture required operator comments - Complete
- show submitted decision result - Complete

Completion criteria:
- operator can inspect workflow context before decisioning - Met
- operator can approve a workflow - Met
- operator can reject a workflow - Met
- UI distinguishes AI assistance from human decision authority - Met

---

## Workstream 6 - Postman And Manual Validation

Status: Completed

Tasks:
- update Postman collection with human review queue request - Complete
- update Postman collection with review context request - Complete
- update Postman collection with approval retrieval request - Complete
- update Postman collection with approve workflow request - Complete
- update Postman collection with reject workflow request - Complete
- update manual validation documentation - Complete

Completion criteria:
- Postman can create a workflow and poll to `HUMAN_REVIEW_REQUIRED` - Met
- Postman can retrieve review context - Met
- Postman can approve a reviewable workflow - Met
- Postman can reject a separate reviewable workflow - Met
- Postman can validate persisted approval records - Met

---

## Workstream 7 - Documentation And Roadmap Updates

Status: Completed

Tasks:
- update `CURRENT_FUNCTIONALITY.md` - Complete
- update `IMPLEMENTATION_ROADMAP.md` - Complete
- update `API_CONTRACTS.md` - Complete
- update `EVENT_CATALOG.md` - Complete
- update `DATA_MODEL.md` if approval implementation details refine the model - Complete
- update `SECURITY_MODEL.md` if new operator enforcement decisions are added - Complete

Completion criteria:
- documentation describes implemented behavior, not aspirational behavior - Met
- Phase 5 completion log is added after validation - Met
- business-facing boundary remains clear for mortgage stakeholders - Met

---

# Validation Plan

## Automated Tests

Expected test suites:
- gateway-api tests
- workflow-engine tests
- operator-console tests where practical

Minimum validation:
- approval records are persisted
- approval records are queryable by workflow
- review queue returns workflows in `HUMAN_REVIEW_REQUIRED`
- review context includes workflow, timeline, agents, tools, and approvals
- approve action requires an operator actor
- reject action requires an operator actor
- approval actions reject non-reviewable workflows
- duplicate decisions are handled safely
- workflow state transitions remain workflow-engine-owned
- timeline and outbox records are created

---

## Manual Postman Validation

Expected Postman requests:
- Create Mortgage Exception Review Workflow
- Poll Until Human Review Required
- Get Human Review Queue
- Get Workflow Review Context
- Get Workflow Approvals
- Approve Workflow
- Get Workflow Timeline
- Create Mortgage Exception Review Workflow For Rejection
- Poll Rejection Workflow Until Human Review Required
- Reject Workflow
- Get Rejection Workflow Approvals

Expected manual result:
- workflow reaches `HUMAN_REVIEW_REQUIRED`
- review queue includes the workflow
- review context includes prepared workflow history
- approval decision is persisted for one workflow
- rejection decision is persisted for a separate workflow
- approval and rejection decisions produce timeline and event records
- workflow state changes according to state machine rules

---

# Risk Register

## Risk 1 - Approval API Bypasses Workflow Engine

Mitigation:
- all workflow state changes must use workflow-engine transition logic
- approval persistence must be coordinated with timeline and outbox records
- direct state mutation from operator-console is prohibited

---

## Risk 2 - AI Output Is Presented As Final Decision

Mitigation:
- UI labels must distinguish agent outputs from operator decisions
- approval records must identify a human operator
- agents must not create approval records

---

## Risk 3 - Duplicate Operator Decisions Corrupt Workflow State

Mitigation:
- enforce one active terminal decision per workflow
- use idempotency where practical
- validate current workflow state before accepting approval decisions

---

## Risk 4 - Sensitive Review Context Is Overexposed

Mitigation:
- use existing DTOs
- avoid raw document content
- avoid unrestricted borrower PII
- preserve masked and synthetic data in local development

---

## Risk 5 - Operator Console Becomes A Hidden Business Logic Layer

Mitigation:
- keep business decisions in explicit API calls
- keep workflow transitions in workflow-engine
- keep UI as an inspection and action surface

---

# Phase 5 Completion Criteria

Status: Completed

Phase 5 is complete when:
- approval records are persisted in PostgreSQL
- human review queue is available through gateway-api
- workflow review context is available through gateway-api
- operator decisions are captured through gateway-api
- workflow-engine transitions approved and rejected workflows through valid states
- approval timeline entries are created
- approval events are written through the outbox model
- operator-console can review and decision workflows locally
- Postman validates approval and rejection paths
- automated tests pass for impacted services
- documentation and roadmap are updated

---

# Running Status Log

## 2026-05-12

Status:
- Phase 5 planning started
- Continuous implementation plan created

Next step:
- implement Workstream 1: Approval Persistence And Events

## 2026-05-12 - Workstream 1

Status:
- added Alembic migration `20260512_0005` for `approval_records`
- added approval persistence models to gateway-api and workflow-engine
- added approval event vocabulary, including `approval.decision_recorded`
- added approval timeline entry type `APPROVAL_DECISION_RECORDED`
- added workflow-engine `record_approval_decision` activity
- implemented idempotent retry behavior by `approval_id`
- implemented duplicate terminal decision protection for workflows
- registered the approval activity with the Temporal worker
- applied the migration successfully against local Postgres
- validated the local table shape in Postgres
- validated workflow-engine automated tests with 8 passing tests
- validated gateway-api automated tests with 9 passing tests

Completed workstream:
- Workstream 1 - Approval Persistence And Events

Boundary:
- approval decision state advancement was deferred to Workstream 2 at this checkpoint
- gateway-api does not yet expose review queue, review context, or approval decision endpoints
- operator-console does not yet display or submit approval decisions

Next step:
- implement Workstream 2: Workflow Decision Integration

## 2026-05-12 - Workstream 2

Status:
- added explicit workflow states `APPROVED` and `REJECTED`
- updated allowed workflow transitions for human review decisions
- added workflow-engine `apply_human_review_decision` activity
- validated workflows must be in `HUMAN_REVIEW_REQUIRED` before a new human decision is applied
- wired approved decisions through `HUMAN_REVIEW_REQUIRED` to `APPROVED` to `COMPLETED`
- wired rejected decisions through `HUMAN_REVIEW_REQUIRED` to `REJECTED` to `COMPLETED`
- emitted `workflow.approved`, `workflow.rejected`, and `workflow.completed` events through the existing state transition outbox pattern
- preserved idempotent retries after decision completion
- registered the decision activity with the Temporal worker
- rebuilt the local workflow-engine container with the new activity
- validated workflow-engine automated tests with 12 passing tests
- validated gateway-api automated tests with 9 passing tests

Completed workstream:
- Workstream 2 - Workflow Decision Integration

Boundary:
- operator-console does not yet display or submit approval decisions
- standard Mortgage Exception Review workflow still pauses at `HUMAN_REVIEW_REQUIRED` until a human decision activity is invoked

Next step:
- implement Workstream 3: Gateway Review APIs

## 2026-05-12 - Workstream 3

Status:
- added gateway-api `GET /api/v1/reviews/human-review-queue`
- added gateway-api `GET /api/v1/workflows/{workflow_id}/review-context`
- added gateway-api `GET /api/v1/workflows/{workflow_id}/approvals`
- added gateway-api `POST /api/v1/workflows/{workflow_id}/approvals`
- added DTOs for review queue entries, review context, approval records, and decision responses
- added required `X-Actor-ID` enforcement for approval decisions
- added structured `workflow_not_reviewable` and `actor_required` error handling
- added a workflow-engine-owned `HumanReviewDecisionWorkflow` that executes the existing `apply_human_review_decision` activity
- routed gateway approval decisions through Temporal instead of direct gateway state mutation
- rebuilt gateway-api and workflow-engine containers
- validated gateway-api automated tests with 15 passing tests
- validated workflow-engine automated tests with 12 passing tests
- validated local live API smoke path from workflow creation to `HUMAN_REVIEW_REQUIRED` to gateway approval and `COMPLETED`

Completed workstream:
- Workstream 3 - Gateway Review APIs

Boundary:
- operator-console does not yet display or submit approval decisions
- Postman approval decision coverage remains assigned to Workstream 6
- standard Mortgage Exception Review workflow still pauses at `HUMAN_REVIEW_REQUIRED` until a human decision is submitted through the gateway approval API

Next step:
- implement Workstream 4: Operator Console Foundation

## 2026-05-12 - Workstream 4

Status:
- scaffolded `apps/operator-console` as a React, TypeScript, Vite, and Tailwind application
- implemented the first screen as an operational human review queue
- added queue summary counts for awaiting review, urgent, and high-priority workflows
- added gateway-api client configuration through `VITE_GATEWAY_API_URL`
- added Dockerfile for local operator-console execution
- added Docker Compose service on port `3000`
- added gateway-api CORS support for `http://localhost:3000`
- added operator-console README with local startup and validation commands
- validated operator-console production build with `npm run build`
- validated gateway-api automated tests with 15 passing tests after CORS update
- built and started local operator-console container
- validated gateway-api review queue API from the running local stack
- validated gateway-api CORS preflight for operator-console origin

Completed workstream:
- Workstream 4 - Operator Console Foundation

Boundary:
- operator-console displays the review queue only
- workflow detail, timeline panels, agent/tool panels, and approval form remain assigned to Workstream 5
- operator-console does not call agent-runtime, tool-runtime, or workflow-engine directly

Next step:
- implement Workstream 5: Workflow Review Experience

## 2026-05-12 - Workstream 5

Status:
- added selected workflow review workspace to operator-console
- added workflow detail panel with workflow state, priority, metadata, Temporal identifiers, and correlation metadata
- added timeline panel populated from gateway review context
- added agent execution panel with validation status, prompt version, confidence score, and structured output summary
- added tool invocation panel with permission status, validation status, and validated output summary
- added approval history panel
- added human decision form with operator identity, approval or rejection decision, and required comment
- wired approval and rejection submissions to gateway-api `POST /api/v1/workflows/{workflow_id}/approvals`
- preserved gateway-api as the only frontend API boundary
- refreshed the review queue after decision submission
- validated operator-console production build with `npm run build`
- rebuilt and restarted local operator-console container
- validated operator-console HTTP serving on port `3000`
- validated live gateway review context retrieval for a queued workflow

Completed workstream:
- Workstream 5 - Workflow Review Experience

Boundary:
- Postman approval validation remains assigned to Workstream 6
- production authentication and RBAC remain out of scope
- operator-console still does not call agent-runtime, tool-runtime, workflow-engine, Postgres, or Temporal directly

Next step:
- implement Workstream 6: Postman And Manual Validation

## 2026-05-12 - Workstream 6

Status:
- expanded the Postman collection with human review queue retrieval
- expanded the Postman collection with workflow review context retrieval
- expanded the Postman collection with workflow approval record retrieval
- added Postman approval submission for a reviewable workflow
- added Postman rejection submission for a separate reviewable workflow
- added dedicated rejection workflow polling and approval retrieval requests for Collection Runner execution
- added collection variables for last decision, approval ID, and rejection approval ID
- updated current functionality manual validation steps to use Postman for approval and rejection testing
- validated Postman collection JSON structure
- validated live local API smoke path for review queue retrieval, review context retrieval, approval submission, approval retrieval, rejection submission, and rejection approval retrieval

Completed workstream:
- Workstream 6 - Postman And Manual Validation

Boundary:
- Postman validation covers local gateway-api review APIs and workflow-engine-owned decision execution
- production authentication and RBAC remain out of scope
- production mortgage system update actions remain out of scope

Next step:
- implement Workstream 7: Documentation And Roadmap Updates

## 2026-05-12 - Workstream 7

Status:
- updated current functionality documentation to describe completed Phase 5 human review behavior
- updated implementation roadmap business language for current local operator review and decision capability
- added Phase 5 completion log to the implementation roadmap
- updated API contracts with implemented approval decision response and transition behavior
- updated event catalog with approval event production boundaries for operator-console and Postman validation
- updated data model with current local persistence records and approval record ownership boundaries
- updated security model to reflect operator-console approval submission and local `X-Actor-ID` boundary
- preserved explicit non-scope for production identity, RBAC, downstream mortgage system updates, and final underwriting or compliance decisions

Completed workstream:
- Workstream 7 - Documentation And Roadmap Updates

Completed phase:
- Phase 5 - Human Review UI

Next step:
- begin Phase 6 planning: Observability Integration

---

# Decision Log

## Decision 1 - Human Operators Own Approval Decisions

Decision:
- Phase 5 approval and rejection actions must identify a human operator actor.

Reason:
- critical mortgage actions require human accountability
- AI agents are supporting participants, not approval authorities
- approval audit history must be attributable

---

## Decision 2 - Preserve Workflow Engine State Ownership

Decision:
- approval APIs will not directly mutate workflow state outside workflow-engine transition logic.

Reason:
- workflow state must remain durable, replayable, and observable
- state transitions must produce timeline and event records
- direct API mutation would weaken orchestration guarantees

---

## Decision 3 - Use Local Simulated Approval Scope

Decision:
- Phase 5 approval and rejection actions will remain local workflow decisions.

Reason:
- production mortgage system updates are out of scope
- local decisions allow validation of governance, auditability, and review ergonomics
- external integration actions can be added later through governed adapters
