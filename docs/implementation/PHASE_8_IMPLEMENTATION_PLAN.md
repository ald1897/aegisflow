# Phase 8 Implementation Plan

## Purpose

This document defines the continuous implementation plan for Phase 8 of AegisFlow.

Phase 8 introduces local replay and failure recovery capabilities for the completed Mortgage Exception Review workflow foundation.

The plan exists to:
- guide implementation work across multiple development sessions
- preserve workflow-engine ownership of workflow state
- make workflow history reconstructable from durable records
- validate replay safety before recovery actions are allowed
- provide bounded failure recovery tooling for local workflow, event, and operator diagnostics
- keep replay and recovery observable, auditable, and side-effect controlled

This document must be updated as implementation progresses.

---

# Phase 8 Objective

Phase 8 will implement replay and failure recovery tooling for the local AegisFlow runtime.

The platform must support:
- reconstruction of completed or in-progress workflow history from persisted records
- deterministic validation of expected workflow state transitions
- replay-run records that preserve what was checked and what differed
- side-effect-safe replay modes that do not re-run agents, tools, approvals, or external integrations by default
- failure classification for workflow, event outbox, agent, tool, approval, and evaluation evidence
- local recovery actions for retryable operational failures
- administrator-facing API and Postman validation paths
- replay and recovery observability through traces, metrics, logs, and dashboards

Replay and recovery may support debugging, incident analysis, regression review, and controlled local remediation.

Replay and recovery must not:
- bypass workflow-engine ownership of workflow state
- silently mutate workflow records
- duplicate irreversible side effects
- re-dispatch human approvals without explicit recovery action
- re-run governed tools or agents during dry-run replay
- call production mortgage systems
- treat replay output as a mortgage approval, rejection, or completion decision
- store raw document contents, borrower PII, secrets, prompt content, approval comments as diagnostic metadata, or full model outputs

---

# Business Context

## Current Business Capability

AegisFlow can currently demonstrate a governed and observable local Mortgage Exception Review workflow from creation through AI-assisted preparation, human review, local approval or rejection, completion, and deterministic evaluation.

Current capability proves:
- workflow state is durable and queryable
- AI and tool participation is governed and recorded
- human approval or rejection remains authoritative
- local workflow operations are observable through traces, metrics, logs, dashboards, and Postman checks
- local evaluation can score persisted workflow evidence without mutating workflow state

## Phase 8 Business Goal

Phase 8 will demonstrate that AegisFlow can explain and recover from operational failures without losing governance.

For mortgage stakeholders, this means the platform begins to answer:
- what happened to a case
- where a case became stuck
- whether the recorded history is internally consistent
- whether a failed event or activity can be safely retried
- what recovery action was requested, who requested it, and what happened next

Business value:
- strengthen operational trust in workflow automation
- make failed or stuck workflow cases easier to diagnose
- reduce ambiguity during incident review
- preserve audit readiness during recovery
- establish the foundation for future production recovery controls

## Business Boundary

Phase 8 will not implement autonomous recovery for production mortgage operations.

Phase 8 will not replace human approval, compliance review, underwriting judgment, servicing policy, or downstream mortgage system controls.

Phase 8 will not enable production identity provider or RBAC enforcement. Local recovery actions may use development actor headers until the later security hardening phase.

Phase 8 will not connect to production mortgage systems.

Phase 8 will not perform unrestricted Temporal history manipulation. Temporal history remains the durable execution record; Phase 8 tooling reads and validates workflow evidence before any controlled recovery action is allowed.

---

# Current Implementation Baseline

Phase 8 starts from the completed Phase 7 baseline.

Implemented runtime services:
- `gateway-api`
- `workflow-engine`
- `agent-runtime`
- `tool-runtime`
- `evaluation-service`
- `operator-console`
- Postgres
- Redpanda
- Redis
- Temporal
- Temporal UI
- OpenTelemetry Collector
- Jaeger
- Prometheus
- Grafana

Implemented workflow behavior:
- `NEW`
- `INTAKE_IN_PROGRESS`
- `DOCUMENT_ANALYSIS_PENDING`
- `RISK_REVIEW_PENDING`
- `HUMAN_REVIEW_REQUIRED`
- `APPROVED`
- `REJECTED`
- `COMPLETED`

Implemented persisted records:
- `workflow_records`
- `workflow_state_transitions`
- `workflow_timeline_entries`
- `workflow_event_outbox`
- `agent_execution_records`
- `tool_invocation_records`
- `approval_records`
- `evaluation_dataset_cases`
- `evaluation_runs`
- `evaluation_results`

Existing recovery-related foundation:
- workflow records include Temporal workflow ID and run ID metadata
- workflow state transitions preserve prior state, new state, reason, actor, correlation ID, and timestamp
- timeline records preserve ordered operational history
- event outbox records include publish status, retry count, last error, and published timestamp
- agent execution records preserve validation status and error metadata
- tool invocation records preserve permission, validation, status, and error metadata
- approval records preserve operator decision context
- evaluation records preserve quality signals for persisted workflow evidence
- observability provides trace, metric, and log context across services

Phase 8 must extend this baseline without weakening workflow-engine ownership of workflow state or treating replay output as an operational decision.

---

# Target Phase 8 Scope

## In Scope

Phase 8 should implement:
- replay and recovery persistence tables
- replay domain contracts and status enums
- workflow evidence reconstruction from persisted records
- deterministic replay validation for current Mortgage Exception Review state paths
- replay run creation and retrieval
- dry-run replay mode as the default
- side-effect policy for replay and recovery actions
- failed/stuck workflow diagnosis from persisted state, timelines, outbox events, agent records, tool records, approval records, and evaluation records
- outbox retry and dead-letter handling for local event publication failures
- controlled workflow recovery commands for local retryable conditions
- gateway-api administrative replay and recovery endpoints
- optional operator-console visibility for replay runs and recovery actions
- Postman validation requests for replay, diagnosis, and recovery paths
- Prometheus metrics and OpenTelemetry tracing for replay and recovery operations
- Grafana panels or dashboard updates for replay and recovery activity
- documentation updates for current functionality, roadmap, data model, API contracts, workflow engine, security, and developer workflow

## Out Of Scope

Phase 8 must not implement:
- production autonomous recovery
- production identity provider integration
- production RBAC enforcement
- production incident paging
- production log aggregation
- production mortgage system integration
- mutation of Temporal history
- unrestricted re-execution of workflow activities
- automatic approval, rejection, completion, cancellation, or override based on replay output
- replay modes that call external systems by default
- storage of raw document content, borrower PII, secrets, prompt content, approval comments as replay metadata, or full model outputs

---

# Proposed Runtime Architecture

## Initial Local Architecture

Phase 8 should avoid introducing a new physical service unless implementation pressure proves it necessary.

Initial ownership:
- gateway-api exposes administrative replay and recovery request/retrieval endpoints
- workflow-engine owns any workflow state mutation or recovery activity
- Postgres stores replay and recovery records
- existing services continue to own their current records
- operator-console may display replay/recovery summaries after gateway endpoints exist

Preferred local flow for replay:

```text
Postman or operator-console
    ->
gateway-api replay endpoint
    ->
Postgres workflow, timeline, transition, event, agent, tool, approval, and evaluation records
    ->
replay run and replay step records
```

Preferred local flow for recovery:

```text
Postman or operator-console
    ->
gateway-api recovery endpoint
    ->
workflow-engine-owned recovery workflow or activity
    ->
Postgres recovery action, workflow, timeline, and outbox records
```

Gateway may orchestrate read-only replay analysis directly.

Gateway must not directly mutate workflow state for recovery outcomes. Mutating recovery actions must route through workflow-engine-owned logic.

## Replay Modes

Initial replay modes:
- `history_reconstruction`
- `deterministic_validation`
- `dry_run_recovery_check`

Future replay modes may include:
- `temporal_history_replay`
- `activity_replay`
- `integration_replay`
- `production_incident_replay`

Default mode must be side-effect free.

## Recovery Action Types

Initial recovery action types:
- `retry_outbox_event`
- `mark_outbox_event_dead_lettered`
- `clear_retryable_outbox_error`
- `reconcile_workflow_projection`
- `resume_stuck_workflow_check`

Future recovery actions may include:
- controlled workflow cancellation
- controlled workflow restart
- activity retry orchestration
- operator reassignment
- external integration compensation

Initial actions must be local, explicit, audited, and bounded.

---

# Persistence Model

Recommended initial tables:
- `workflow_replay_runs`
- `workflow_replay_steps`
- `workflow_recovery_actions`

Recommended `workflow_replay_runs` fields:
- `replay_run_id`
- `workflow_id`
- `correlation_id`
- `replay_mode`
- `status`
- `source_temporal_workflow_id`
- `source_temporal_run_id`
- `started_at`
- `completed_at`
- `requested_by`
- `replay_metadata`
- `created_at`

Recommended `workflow_replay_steps` fields:
- `replay_step_id`
- `replay_run_id`
- `workflow_id`
- `sequence_number`
- `artifact_type`
- `artifact_id`
- `expected_state`
- `observed_state`
- `status`
- `message`
- `step_metadata`
- `created_at`

Recommended `workflow_recovery_actions` fields:
- `recovery_action_id`
- `workflow_id`
- `correlation_id`
- `action_type`
- `target_resource_type`
- `target_resource_id`
- `status`
- `requested_by`
- `reason`
- `started_at`
- `completed_at`
- `result_metadata`
- `created_at`

Replay and recovery records must store bounded references and diagnostic summaries.

Replay and recovery records must not store:
- raw document contents
- unrestricted borrower PII
- secrets
- prompt content
- approval comments as diagnostic metadata
- full model outputs
- unrestricted integration payloads

---

# Replay Validation Dimensions

## Workflow State Reconstruction

Initial checks:
- workflow record exists
- state transition sequence is ordered and valid
- first transition is compatible with workflow creation
- final persisted workflow state matches the last state transition
- terminal timestamp fields are compatible with terminal state
- timeline entries align with expected major workflow milestones

## Agent Evidence Reconstruction

Initial checks:
- required agent execution records exist for current local workflow path
- agent execution records are associated with the workflow and correlation ID
- validation status is present
- prompt ID, prompt version, and model name are present
- agent execution timing is compatible with workflow timeline ordering

## Tool Evidence Reconstruction

Initial checks:
- tool invocation records are associated with expected agents
- permission status is present
- input and output validation statuses are present
- tool invocation timing is compatible with agent execution evidence
- tool failure metadata is bounded when present

## Human Review Reconstruction

Initial checks:
- approval records exist only for workflows that reached human review
- approval decision is compatible with terminal approval or rejection path
- approval record actor and reviewed timestamp are present
- duplicate final decisions are not represented as multiple authoritative outcomes

## Event Outbox Reconstruction

Initial checks:
- workflow event outbox records exist for expected major workflow facts
- publish status is one of the accepted local statuses
- retry count and last error are internally consistent
- failed or pending events can be classified for retry or dead-letter handling

## Evaluation Evidence Reconstruction

Initial checks:
- evaluation runs remain quality telemetry only
- evaluation results reference existing workflow records
- evaluation records do not conflict with authoritative workflow outcome records
- evaluation replay dataset results are not mistaken for workflow replay execution

---

# API Scope

## gateway-api Replay Endpoints

Recommended endpoints:

```text
POST /api/v1/workflows/{workflow_id}/replay-runs
GET /api/v1/workflows/{workflow_id}/replay-runs
GET /api/v1/replay-runs/{replay_run_id}
GET /api/v1/workflows/{workflow_id}/replay-diagnostics
```

Replay run creation must:
- require a local actor identity such as `X-Actor-ID`
- default to side-effect-free replay
- create a replay run record
- create replay step records
- return bounded diagnostics
- never mutate workflow state

## gateway-api Recovery Endpoints

Recommended endpoints:

```text
POST /api/v1/workflows/{workflow_id}/recovery-actions
GET /api/v1/workflows/{workflow_id}/recovery-actions
GET /api/v1/recovery-actions/{recovery_action_id}
```

Recovery action creation must:
- require a local actor identity such as `X-Actor-ID`
- require an action type
- require a reason
- validate that the action is allowed for the target resource
- route workflow state mutations through workflow-engine-owned recovery logic
- persist the requested action and final result

---

# Observability Requirements

Phase 8 must extend the existing Phase 6 and Phase 7 observability foundation.

Required traces:
- replay run request
- workflow evidence loading
- replay step validation
- replay run persistence
- recovery action request
- recovery action execution
- outbox retry or dead-letter update

Required metrics:
- replay runs total by mode and status
- replay steps total by artifact type and status
- replay run duration
- recovery actions total by action type and status
- recovery action duration
- outbox events by publish status
- outbox retries total by event type and status
- stuck workflow diagnostics total by workflow type and diagnostic status

Metric labels must remain low-cardinality.

Metrics must not label by:
- workflow ID
- replay run ID
- recovery action ID
- event ID
- trace ID
- borrower values
- prompt content
- document content
- approval comments

Required logs:
- replay run started
- replay run completed
- replay run failed
- replay mismatch detected
- recovery action requested
- recovery action completed
- recovery action failed
- outbox event retried
- outbox event dead-lettered

Logs must include correlation ID and trace ID where available and avoid sensitive payloads.

---

# Workstreams

## Workstream 1 - Replay And Recovery Domain Model

Status: Completed

Tasks:
- define replay run, replay step, and recovery action statuses - Complete
- add Alembic migration for `workflow_replay_runs`, `workflow_replay_steps`, and `workflow_recovery_actions` - Complete
- add SQLAlchemy models to gateway-api and workflow-engine as needed - Complete
- add DTOs for replay run, replay step, diagnostic, and recovery action responses - Complete
- add repository methods for create, retrieve, and list behavior - Complete
- document bounded metadata and sensitive data restrictions - Complete
- add persistence tests - Complete

Completion criteria:
- replay and recovery tables are created locally - Met
- records can be persisted and retrieved - Met
- records preserve workflow and correlation identity - Met
- persistence tests pass - Met

---

## Workstream 2 - Workflow Evidence Reconstruction

Status: Completed

Tasks:
- implement workflow evidence loader for workflow record, transitions, timeline, outbox events, agent executions, tool invocations, approval records, and evaluation records - Complete
- normalize evidence into bounded internal dataclasses or DTOs - Complete
- sort evidence deterministically by timestamp and stable identifiers - Complete
- classify evidence artifacts by type and ownership - Complete
- add missing evidence diagnostics for incomplete workflows - Complete
- add tests for completed approval, completed rejection, and human-review-in-progress workflows - Complete

Completion criteria:
- workflow evidence can be reconstructed from persisted records - Met
- reconstruction does not mutate workflow state - Met
- completed approval and rejection workflows produce stable evidence snapshots - Met
- tests pass - Met

---

## Workstream 3 - Deterministic Replay Validator

Status: Completed

Tasks:
- implement state transition sequence validator for the local Mortgage Exception Review path - Complete
- implement timeline milestone validator - Complete
- implement agent evidence validator - Complete
- implement tool evidence validator - Complete
- implement human review evidence validator - Complete
- implement event outbox evidence validator - Complete
- implement evaluation evidence boundary validator - Complete
- map validation results into replay step records - Complete
- add unit tests for pass, warn, and fail scenarios - Complete

Completion criteria:
- replay validation creates deterministic step results - Met
- replay mismatches are bounded and explainable - Met
- validator does not re-run agents, tools, approvals, events, or workflows - Met
- tests pass - Met

---

## Workstream 4 - Replay Run Orchestration

Status: Completed

Tasks:
- add replay run creation service - Complete
- support `history_reconstruction` mode - Complete
- support `deterministic_validation` mode - Complete
- support explicit `replay_run_id` idempotency where practical - Complete
- persist replay run and replay step records - Complete
- handle missing workflows with structured errors - Complete
- handle workflows with incomplete evidence using warning diagnostics instead of unsafe mutation - Complete
- add retrieval and workflow listing services - Complete
- add integration tests against seeded workflow evidence - Complete

Completion criteria:
- a local workflow can receive a replay run - Met
- replay runs and steps are persisted and retrievable - Met
- missing workflow and incomplete evidence cases are handled clearly - Met
- replay run creation is side-effect free - Met
- tests pass - Met

---

## Workstream 5 - Failure Classification And Outbox Recovery

Status: Completed

Tasks:
- define retryable, terminal, dead-letterable, and informational failure categories - Complete
- classify workflow event outbox records by publish status, retry count, and last error - Complete
- add safe outbox retry command for retryable local events - Complete
- add dead-letter marking behavior for explicitly selected local outbox events - Complete
- add recovery action records for outbox retry and dead-letter outcomes - Complete
- ensure event retry uses existing event publication boundaries - Complete
- add tests for pending, published, failed, retryable, and dead-lettered event cases - Complete

Completion criteria:
- failed outbox events can be diagnosed - Met
- retryable outbox events can be retried explicitly - Met
- dead-letter action is explicit and auditable - Met
- event retry does not duplicate successful published events - Met
- tests pass - Met

---

## Workstream 6 - Workflow Recovery Commands

Status: Completed

Tasks:
- define allowed local recovery commands for stuck or inconsistent workflows - Complete
- require actor identity and recovery reason for every recovery command - Complete
- route any workflow state mutation through workflow-engine-owned recovery activities or workflows - Complete
- add dry-run recovery check before mutating commands - Complete
- add timeline entries for accepted recovery actions - Complete
- add outbox events for completed recovery actions where appropriate - Complete
- reject unsafe recovery actions with structured errors - Complete
- add workflow-engine and gateway-api tests - Complete

Completion criteria:
- recovery commands are explicit and auditable - Met
- gateway-api does not directly mutate workflow state for recovery outcomes - Met
- unsafe or unsupported recovery actions are rejected - Met
- recovery actions preserve workflow history - Met
- tests pass - Met

---

## Workstream 7 - Gateway API And Operator Visibility

Status: Completed

Tasks:
- add gateway replay run creation endpoint - Complete
- add gateway replay run retrieval endpoint - Complete
- add gateway workflow replay run listing endpoint - Complete
- add gateway workflow replay diagnostics endpoint - Complete
- add gateway recovery action creation and retrieval endpoints - Complete
- add operator-console read-only replay/recovery summaries if time allows - Complete
- keep recovery mutation controls behind explicit operator action, not passive page load - Complete
- add API and UI tests where surfaces are changed - Complete

Completion criteria:
- replay and recovery records are accessible through gateway-api - Met
- operator-facing data is bounded and understandable - Met
- no read endpoint creates replay or recovery side effects - Met
- tests pass - Met

---

## Workstream 8 - Postman Validation And Local Failure Scenarios

Status: Completed

Tasks:
- add Postman requests for replay run creation and retrieval - Complete
- add Postman requests for replay diagnostics - Complete
- add Postman requests for recovery action creation and retrieval - Complete
- add local validation for approval workflow replay - Complete
- add local validation for rejection workflow replay - Complete
- add local validation for a retryable outbox failure scenario - Complete
- add local validation for rejection of unsupported recovery actions - Complete
- validate Postman collection JSON and script syntax - Complete

Completion criteria:
- Postman can create and retrieve replay runs - Met
- Postman can validate replay diagnostics for approval and rejection workflows - Met
- Postman can exercise at least one safe recovery action - Met
- unsupported recovery actions are rejected with structured errors - Met
- collection JSON and scripts validate - Met

---

## Workstream 9 - Replay Observability And Dashboards

Status: Completed

Tasks:
- emit replay and recovery traces - Complete
- emit replay and recovery metrics - Complete
- add structured logs for replay and recovery operations - Complete
- add Grafana panels or a dedicated dashboard for replay and recovery activity - Complete
- validate Jaeger contains replay and recovery traces - Complete
- validate Prometheus scrapes replay and recovery metrics - Complete
- validate Grafana displays replay and recovery activity - Complete
- keep metric labels low-cardinality - Complete

Completion criteria:
- replay and recovery activity appears in Jaeger - Met
- Prometheus exposes replay and recovery metrics - Met
- Grafana displays replay and recovery panels - Met
- logs include bounded correlation and trace context - Met
- telemetry avoids sensitive payload exposure - Met

---

## Workstream 10 - Documentation And Phase Closeout

Status: Completed

Tasks:
- update `CURRENT_FUNCTIONALITY.md` - Complete
- update `IMPLEMENTATION_ROADMAP.md` - Complete
- update `WORKFLOW_ENGINE.md` with implemented replay and recovery behavior - Complete
- update `WORKFLOW_STATE_MACHINE.md` if recovery states or transitions are added - Complete
- update `DATA_MODEL.md` for implemented replay and recovery records - Complete
- update `API_CONTRACTS.md` for replay and recovery endpoints - Complete
- update `SECURITY_MODEL.md` for local recovery authorization boundaries - Complete
- update `OBSERVABILITY_STRATEGY.md` for replay and recovery telemetry - Complete
- update `DEVELOPER_WORKFLOW.md` with replay and recovery validation commands - Complete
- add Phase 8 completion log after validation - Complete

Completion criteria:
- documentation describes implemented behavior, not aspirational behavior - Met
- business-facing recovery boundary remains clear - Met
- manual tester can run local replay and safe recovery validation - Met
- automated tests and manual validation are recorded - Met

---

# Validation Plan

## Automated Tests

Expected test suites:
- gateway-api tests for replay and recovery endpoints
- workflow-engine tests for recovery command execution where workflow state mutation is involved
- service/domain tests for replay evidence reconstruction and validation
- Postman collection JSON validation
- Postman script syntax validation
- Docker Compose configuration validation

Minimum validation:
- replay persistence works against local Postgres
- replay evidence reconstruction works for approval and rejection workflows
- deterministic replay validation produces stable results
- replay run creation does not mutate workflow state
- recovery commands require actor identity and reason
- unsupported recovery commands are rejected
- outbox retry does not duplicate already-published events
- metrics endpoints do not expose sensitive payloads
- telemetry configuration does not break tests when disabled

## Manual Validation

Expected manual flow:
- start local Docker Compose stack
- create and approve a Mortgage Exception Review workflow
- create and reject a separate Mortgage Exception Review workflow
- create replay runs for both workflows
- inspect replay diagnostics and replay step records
- create or seed a retryable local outbox failure scenario
- execute an explicit safe recovery action
- inspect recovery action records
- inspect workflow timeline and outbox records after recovery
- inspect Prometheus metrics for replay and recovery activity
- inspect Jaeger traces for replay and recovery activity
- inspect Grafana replay and recovery panels
- inspect structured logs by correlation ID

Expected manual result:
- approval and rejection workflows remain reconstructable
- replay runs complete without mutating workflow state
- replay diagnostics are bounded and understandable
- safe recovery action is explicit, recorded, and observable
- unsupported or unsafe recovery action is rejected
- traces, metrics, dashboards, and logs reflect replay and recovery activity

---

# Risk Register

## Risk 1 - Replay Accidentally Creates Side Effects

Mitigation:
- make dry-run replay the default
- prohibit agent, tool, approval, event publication, and workflow mutation during replay validation
- require explicit recovery action endpoints for any mutation
- add tests proving replay run creation does not mutate workflow state

---

## Risk 2 - Recovery Bypasses Workflow Engine Ownership

Mitigation:
- route workflow state mutation through workflow-engine-owned recovery logic
- keep gateway-api responsible for validation and request intake, not direct workflow state updates
- add tests for ownership boundaries

---

## Risk 3 - Duplicate Event Publication

Mitigation:
- retry only events classified as retryable
- reject retries for already-published events
- preserve retry count, status, and recovery action history
- add idempotency checks around event publication

---

## Risk 4 - Recovery Is Mistaken For Business Approval

Mitigation:
- document recovery as operational remediation only
- keep approval/rejection decisions tied to approval records and human review paths
- prevent recovery actions from creating mortgage approval or rejection decisions

---

## Risk 5 - Replay Records Leak Sensitive Data

Mitigation:
- persist references, statuses, counts, and bounded diagnostics only
- exclude raw documents, borrower PII, secrets, prompt content, approval comments as metadata, and full model outputs
- test representative response payloads for bounded shape

---

## Risk 6 - Replay Metrics Become High Cardinality

Mitigation:
- do not label metrics with workflow IDs, replay run IDs, recovery action IDs, event IDs, trace IDs, borrower values, prompt content, document content, or approval comments
- use IDs in persisted records and traces, not metric labels
- keep dashboards aggregate-first

---

# Phase 8 Completion Criteria

Phase 8 is complete when:
- replay and recovery persistence tables exist and are tested - Met
- workflow evidence reconstruction works for local approval and rejection workflows - Met
- deterministic replay validation produces persisted replay runs and steps - Met
- replay run creation is side-effect free - Met
- replay and recovery retrieval endpoints are available through gateway-api - Met
- safe outbox recovery behavior is implemented and tested - Met
- unsupported recovery actions are rejected with structured errors - Met
- recovery actions require local actor identity and reason - Met
- any workflow state mutation routes through workflow-engine-owned logic - Met
- Postman validates replay and safe recovery workflows - Met
- replay and recovery emit traces, metrics, and structured logs - Met
- Grafana or dashboard panels expose replay and recovery activity - Met
- replay and recovery avoid sensitive payload exposure - Met
- documentation and roadmap are updated - Met

---

# Running Status Log

## 2026-05-12 - Planning

Status:
- Phase 8 planning started after Phase 7 completion
- continuous implementation plan created

Next step:
- implement Workstream 1: Replay And Recovery Domain Model

## 2026-05-12 - Workstream 1

Status:
- added Alembic migration `20260512_0007_add_replay_recovery_records`
- added `workflow_replay_runs`, `workflow_replay_steps`, and `workflow_recovery_actions` tables
- added replay mode, replay run status, replay step status, recovery action type, and recovery action status enums to gateway-api and workflow-engine domain models
- added gateway-api and workflow-engine SQLAlchemy models for replay and recovery records
- added gateway-api DTOs for replay runs, replay steps, replay diagnostics, and recovery actions
- added gateway-api service methods for replay run create/retrieve/list, replay step create/list, and recovery action create/retrieve/list
- added persistence tests for replay runs, replay steps, and recovery actions
- made gateway-api tests override compose runtime flags so persistence tests remain isolated from local event publishing settings

Validation:
- gateway-api pytest suite passed with 19 tests
- workflow-engine pytest suite passed with 12 tests
- Docker Compose configuration validated
- Python source compilation succeeded for gateway-api and workflow-engine

Completed workstream:
- Workstream 1 - Replay And Recovery Domain Model

Boundary:
- Workstream 1 only adds persistence, typed contracts, and service-layer create/retrieve/list behavior
- no public replay or recovery endpoints are introduced yet
- no workflow state mutation, event retry, Temporal replay, agent execution, tool execution, or approval dispatch is introduced
- replay and recovery metadata remains bounded to references, statuses, and diagnostic context only

Next step:
- implement Workstream 2: Workflow Evidence Reconstruction

## 2026-05-12 - Workstream 2

Status:
- added gateway-api workflow evidence reconstruction dataclasses for normalized artifacts, diagnostics, and snapshots
- added read-only workflow evidence reconstruction for workflow records, state transitions, timeline entries, event outbox records, agent executions, tool invocations, approval records, evaluation runs, and evaluation results
- added deterministic artifact sorting by occurrence timestamp, artifact type, and artifact identifier
- classified artifacts by type and owning runtime boundary
- bounded artifact metadata to references, statuses, keys, flags, and diagnostic summaries
- added diagnostics for missing state transitions, missing timeline entries, missing agent evidence, missing tool evidence, pending human review, missing terminal approval evidence, and missing completed-workflow evaluation runs
- added gateway service method `reconstruct_workflow_evidence`
- added tests for completed approval workflow evidence, completed rejection workflow evidence, and human-review-in-progress diagnostics
- verified reconstruction does not create approval or replay records and does not mutate workflow counts

Validation:
- gateway-api pytest suite passed with 22 tests
- Docker Compose configuration validated
- gateway-api source compilation succeeded

Completed workstream:
- Workstream 2 - Workflow Evidence Reconstruction

Boundary:
- Workstream 2 is read-only evidence reconstruction only
- no replay runs, replay steps, recovery actions, workflow state transitions, outbox retries, Temporal replay, agent execution, tool execution, or approval dispatch are created
- approval comments, raw documents, borrower PII, prompt content, full model outputs, and unrestricted payloads are not copied into evidence artifacts

Next step:
- implement Workstream 3: Deterministic Replay Validator

## 2026-05-12 - Workstream 3

Status:
- added gateway-api deterministic replay validation dataclasses for validation results and replay-step-shaped validation steps
- added deterministic validation for local Mortgage Exception Review state transition sequences
- added timeline milestone validation for workflow, state transition, agent, tool, and approval milestones
- added agent execution and tool invocation evidence validation
- added human review validation for completed approval or rejection workflows and pending human-review workflows
- added event outbox validation for expected event families and pending or failed publication evidence
- added evaluation boundary validation for completed and in-progress workflows
- added gateway service method `validate_deterministic_replay`
- updated workflow evidence test fixtures to seed a complete deterministic mortgage-review path
- added tests for pass, warn, and fail replay validation scenarios

Validation:
- gateway-api pytest suite passed with 25 tests
- Docker Compose configuration validated
- gateway-api source compilation succeeded

Completed workstream:
- Workstream 3 - Deterministic Replay Validator

Boundary:
- Workstream 3 builds side-effect-free validation results from reconstructed evidence
- no replay runs, replay steps, recovery actions, workflow state transitions, outbox retries, Temporal replay, agent execution, tool execution, or approval dispatch are created
- validation metadata remains bounded to expected and observed identifiers, statuses, artifact families, and diagnostic counts

Next step:
- implement Workstream 4: Replay Run Orchestration

## 2026-05-13 - Workstream 4

Status:
- added gateway-api replay run orchestration service method `create_orchestrated_replay_run`
- supported `history_reconstruction` mode by converting reconstructed evidence artifacts and diagnostics into persisted replay steps
- supported `deterministic_validation` mode by persisting deterministic replay validator steps
- added explicit replay run id idempotency for same workflow and replay mode
- added conflict handling for reused replay run ids with different workflow or mode
- persisted completed or failed replay run status from generated step outcomes
- persisted replay step records with bounded metadata only
- preserved retrieval and workflow listing through existing replay run and replay step service methods
- added tests for history reconstruction, deterministic validation, explicit idempotency, and incomplete evidence warning orchestration

Validation:
- gateway-api pytest suite passed with 29 tests
- Docker Compose configuration validated
- gateway-api source compilation succeeded

Completed workstream:
- Workstream 4 - Replay Run Orchestration

Boundary:
- Workstream 4 persists replay run and replay step records only
- no recovery actions, workflow state transitions, outbox retries, Temporal replay, agent execution, tool execution, approval dispatch, or event publication are created
- incomplete workflow evidence is preserved as warning or skipped replay steps rather than repaired or mutated
- replay metadata remains bounded to summaries, counts, statuses, artifact families, diagnostic codes, and expected or observed identifiers

Next step:
- implement Workstream 5: Failure Classification And Outbox Recovery

## 2026-05-13 - Workstream 5

Status:
- added gateway-api outbox failure categories for informational, retryable, dead-letterable, and terminal events
- added `DEAD_LETTERED` outbox publish status to gateway-api and workflow-engine domain models
- added outbox classification for publish status, retry count, last error presence, retry threshold, and terminal-looking errors
- added gateway service methods for outbox event retrieval, classification, workflow-level classification listing, retry, and dead-letter marking
- added retry command that resets retryable failed events to pending and optionally invokes the existing event publisher boundary
- added dead-letter command that marks explicitly selected failed local events as `DEAD_LETTERED`
- added recovery action audit records for retry and dead-letter outcomes with bounded metadata
- updated gateway and workflow-engine publishers to skip dead-lettered events
- added tests for pending, published, retryable failed, retry-exhausted failed, and dead-lettered event classification
- added tests for retry via publisher boundary, published-event retry rejection, and dead-letter audit behavior

Validation:
- gateway-api pytest suite passed with 33 tests
- workflow-engine pytest suite passed with 12 tests
- Docker Compose configuration validated
- gateway-api and workflow-engine source compilation succeeded

Completed workstream:
- Workstream 5 - Failure Classification And Outbox Recovery

Boundary:
- Workstream 5 only classifies and recovers workflow event outbox records
- retry uses the existing event publisher boundary and does not publish already published or dead-lettered events
- no workflow state transitions, Temporal replay, agent execution, tool execution, approval dispatch, replay runs, or replay steps are created
- recovery action metadata remains bounded to statuses, counts, classifications, and presence flags only

Next step:
- implement Workstream 6: Workflow Recovery Commands

## 2026-05-13 - Workstream 6

Status:
- added gateway-api workflow recovery planner for dry-run recovery checks
- added allowed local workflow recovery actions for projection reconciliation and stuck-workflow dry-run checks
- added gateway service method `check_workflow_recovery`
- added gateway service method `request_workflow_recovery`
- required local actor identity and recovery reason before recovery requests are accepted
- made gateway recovery requests create auditable `REQUESTED` recovery actions without mutating workflow state
- added workflow-engine recovery activity `reconcile_workflow_projection`
- registered workflow-engine recovery activity with the Temporal worker
- routed projection reconciliation state mutation through workflow-engine-owned logic
- added workflow-engine recovery timeline entry and recovery completion outbox event
- added rejection behavior for unsafe, unsupported, or incomplete recovery commands
- added gateway-api tests for dry-run checks, auditable requests, required actor/reason, and unsafe command rejection
- added workflow-engine tests for projection reconciliation mutation, dry-run non-mutation, and unsupported command rejection

Validation:
- gateway-api pytest suite passed with 37 tests
- workflow-engine pytest suite passed with 15 tests
- Docker Compose configuration validated
- gateway-api and workflow-engine source compilation succeeded

Completed workstream:
- Workstream 6 - Workflow Recovery Commands

Boundary:
- gateway-api only performs dry-run checks and creates recovery request records
- workflow state mutation is performed only by workflow-engine-owned recovery activity logic
- workflow-engine writes recovery timeline and recovery completion outbox records for accepted recovery actions
- unsafe workflow recovery actions are rejected with structured errors
- recovery metadata remains bounded to statuses, states, transition identifiers, reason presence, and safety flags only

## 2026-05-13 - Workstream 7

Status:
- added gateway-api replay run creation endpoint
- added gateway-api replay run retrieval endpoint
- added gateway-api workflow replay run listing endpoint
- added gateway-api read-only replay diagnostics endpoint
- added gateway-api workflow recovery dry-run check endpoint
- added gateway-api explicit recovery action creation endpoint
- added gateway-api recovery action retrieval and workflow recovery action listing endpoints
- required `X-Actor-ID` for replay run creation and recovery action creation
- required explicit outbox target resource fields for outbox retry and dead-letter recovery
- kept replay diagnostics, replay retrieval, recovery checks, and recovery retrieval endpoints read-only
- added gateway-api tests for replay API creation/retrieval/listing, read-only diagnostics, actor enforcement, workflow recovery checks/actions, and explicit outbox recovery targets
- added operator-console read-only replay and recovery summaries to the workflow review workspace

Validation:
- gateway-api pytest suite passed with 41 tests
- workflow-engine pytest suite passed with 15 tests
- operator-console production build passed
- Docker Compose configuration validated
- gateway-api and workflow-engine source compilation succeeded

Completed workstream:
- Workstream 7 - Gateway API And Operator Visibility

Boundary:
- replay run creation persists replay run and replay step records only
- replay diagnostics and all retrieval endpoints do not create replay or recovery records
- gateway recovery action creation requires explicit operator action, actor identity, and reason
- gateway workflow recovery requests remain auditable records; workflow-engine remains responsible for actual workflow state mutation
- no Temporal replay, agent execution, tool execution, approval dispatch, passive recovery mutation, or external integration calls are introduced
- operator-console replay/recovery visibility is read-only and does not expose recovery mutation controls

Next step:
- implement Workstream 8: Postman Validation And Local Failure Scenarios

## 2026-05-13 - Workstream 8

Status:
- added Postman replay diagnostics requests for approval and rejection workflows
- added Postman deterministic replay run creation, retrieval, and workflow replay listing requests for approval and rejection workflows
- added Postman recovery action creation, retrieval, and workflow recovery action listing requests
- added Postman validation for structured rejection of unsupported recovery actions
- added local helper script `scripts/seed_retryable_outbox_failure.ps1` to seed a retryable workflow outbox failure for safe local recovery validation
- added collection variables for replay run ids, retryable outbox event id, recovery action id, and explicit recovery-scenario enablement
- kept the default collection runnable without requiring database seeding while allowing strict recovery validation when `enableRecoveryScenario` is set to `true`
- validated Postman collection JSON parsing and script syntax

Validation:
- Postman collection JSON parsed successfully
- Postman test and pre-request scripts parsed successfully
- PowerShell seed helper syntax parsed successfully
- Docker Compose configuration validated
- local live approval workflow replay smoke validation completed through gateway-api
- local live seeded outbox retry recovery action completed through gateway-api
- unsupported recovery action returned structured `workflow_recovery_not_allowed` error

Completed workstream:
- Workstream 8 - Postman Validation And Local Failure Scenarios

Boundary:
- Workstream 8 adds manual validation coverage and a local failure seed helper only
- no gateway-api, workflow-engine, workflow state, Temporal replay, agent execution, tool execution, approval dispatch, event publication, or recovery business behavior is changed
- local outbox seeding is explicit, operator-run, and limited to a selected outbox event in the local Docker Postgres container

Next step:
- implement Workstream 9: Replay Observability And Dashboards

## 2026-05-13 - Workstream 9

Status:
- added gateway-api replay run metrics for run count, run duration, and replay step results by replay mode, artifact type, and status
- added gateway-api recovery metrics for recovery action count and duration by action type and status
- added gateway-api outbox status gauge and outbox retry counter by publish status, event type, and outcome status
- added gateway-api stuck workflow diagnostic counter by workflow type and diagnostic status
- added OpenTelemetry spans for replay run creation, workflow evidence loading, replay step validation, replay run persistence, replay diagnostics, workflow recovery checks, workflow recovery requests, outbox retry, and outbox dead-letter updates
- added bounded structured logs for replay run start/completion/failure, replay mismatches, replay diagnostics, recovery requests, recovery completion/failure, outbox retries, and outbox dead-letter updates
- added Grafana dashboard `AegisFlow - Replay And Recovery`
- preserved low-cardinality metric labels and kept workflow identifiers, replay run identifiers, recovery action identifiers, event identifiers, trace identifiers, borrower values, prompt content, document content, and approval comments out of metric labels

Validation:
- gateway-api Python source compilation succeeded
- Postman collection JSON parsed successfully
- Grafana replay/recovery dashboard JSON parsed successfully
- Docker Compose configuration validated
- gateway-api pytest suite passed
- Prometheus exposed replay and recovery metric families through gateway-api `/metrics`
- local live replay and recovery smoke path produced replay/recovery metrics
- Prometheus returned replay, recovery, outbox retry, and stuck-workflow diagnostic samples
- Jaeger returned gateway replay and recovery traces
- Grafana listed `AegisFlow - Replay And Recovery`
- Docker logs contained bounded replay and recovery entries with correlation ID and trace ID

Completed workstream:
- Workstream 9 - Replay Observability And Dashboards

Boundary:
- Workstream 9 adds telemetry and dashboard visibility only
- replay remains side-effect free and persists replay records only
- recovery actions remain explicit and bounded; workflow state mutation ownership remains with workflow-engine recovery logic
- metric labels remain aggregate-first and avoid sensitive or high-cardinality identifiers

Next step:
- implement Workstream 10: Documentation And Phase Closeout

## 2026-05-13 - Workstream 10

Status:
- updated current functionality documentation to describe completed Phase 8 local replay and recovery capability
- updated the implementation roadmap with Phase 8 completion status, delivered replay/recovery capability, validation results, and remaining future boundaries
- updated workflow engine and workflow state machine documentation for side-effect-free replay, outbox recovery, workflow-engine-owned recovery, and the lack of new workflow lifecycle states
- updated data model documentation for replay/recovery records, outbox `DEAD_LETTERED` status, and recovery action outcomes
- updated API, event, security, observability, and developer workflow documentation for implemented replay and recovery contracts
- preserved the business boundary that replay and recovery do not approve, reject, complete, underwrite, or mutate mortgage decisions

Validation:
- gateway-api pytest suite passed with 41 tests
- workflow-engine pytest suite passed with 15 tests
- operator-console production build passed
- Postman collection JSON and script syntax parsed successfully
- Grafana replay/recovery dashboard JSON parsed successfully
- Docker Compose configuration validated
- local live replay and seeded outbox recovery smoke validations completed during Workstreams 8 and 9

Completed workstream:
- Workstream 10 - Documentation And Phase Closeout

Completed phase:
- Phase 8 - Replay and Failure Recovery

Next step:
- begin Phase 9 planning when ready

---

# Decision Log

## Decision 1 - Replay Is Side-Effect Free By Default

Decision:
- Phase 8 replay runs will reconstruct and validate persisted workflow evidence by default. They will not re-run agents, tools, approvals, events, workflow activities, or external integrations.

Reason:
- replay must be safe for local debugging and future production incident analysis
- duplicate tool calls, event publication, or human decisions would corrupt operational history
- recovery actions need a separate explicit control boundary

---

## Decision 2 - Workflow Engine Owns Mutating Recovery

Decision:
- Gateway may expose recovery request APIs, but any workflow state mutation must route through workflow-engine-owned recovery logic.

Reason:
- workflow-engine ownership of state is an AegisFlow architectural constraint
- recovery must preserve the same governance model as normal workflow progression
- direct gateway state mutation would create hidden operational paths

---

## Decision 3 - Outbox Recovery Before Broad Workflow Recovery

Decision:
- Phase 8 will implement bounded event outbox recovery before broader workflow restart or activity replay commands.

Reason:
- outbox records already contain retry and error metadata
- event retry/dead-letter handling is valuable and contained
- broader workflow restart and activity replay require stricter authorization and production controls

---

## Decision 4 - No New Replay Service Initially

Decision:
- Phase 8 will start with gateway-api and workflow-engine changes rather than a new replay-service.

Reason:
- current replay scope is local and workflow-specific
- existing services already own the relevant API, persistence, and workflow mutation boundaries
- a separate replay-service can be introduced later if operational complexity justifies it
