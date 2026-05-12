# Phase 7 Implementation Plan

## Purpose

This document defines the continuous implementation plan for Phase 7 of AegisFlow.

Phase 7 introduces the first measurable AI evaluation layer for the completed and observable Mortgage Exception Review local simulation.

The plan exists to:
- guide implementation work across multiple development sessions
- preserve workflow-engine ownership of workflow state
- make agent and workflow quality measurable without changing production workflow outcomes
- introduce replay-aware evaluation records without unsafe side effects
- provide clear validation checkpoints before Phase 7 is considered complete

This document must be updated as implementation progresses.

---

# Phase 7 Objective

Phase 7 will implement AI evaluation and replay support for the local Mortgage Exception Review workflow.

The platform must support operational quality measurement for:
- governed agent outputs
- prompt versions
- model metadata
- structured output quality
- escalation and human review recommendations
- tool usage consistency
- approval and rejection outcome comparison
- replayable evaluation scenarios

Evaluation must:
- remain separate from authoritative workflow state
- preserve prompt and model version traceability
- persist reproducible evaluation results
- support deterministic local scoring before external judge models are introduced
- avoid storing raw document contents, borrower PII, secrets, prompt content, or full model outputs unnecessarily
- remain observable through the Phase 6 tracing, metrics, dashboard, and log foundation

Evaluation data may support regression analysis, quality review, and governance decisions.

Evaluation data must not:
- approve or reject workflows
- mutate workflow state
- bypass human review
- replace approval records, workflow timelines, or audit records
- become the system of record for mortgage decisions
- call production mortgage systems
- introduce unsafe side effects during replay

---

# Business Context

## Current Business Capability

AegisFlow can currently demonstrate a governed and observable Mortgage Exception Review workflow from creation through AI-assisted preparation, human review, approval or rejection, and local workflow completion.

Current Phase 6 capability proves:
- workflows can be created, persisted, traced, measured, and completed locally
- governed agents can produce validated structured outputs
- approved tools can provide synthetic supporting context
- human approval or rejection remains authoritative
- workflow activity is visible through Postgres, Temporal, events, traces, metrics, dashboards, and structured logs
- Postman can validate approval, rejection, metrics, traces, dashboards, and correlated logs

## Phase 7 Business Goal

Phase 7 will demonstrate how mortgage operations and platform teams can measure the quality of AI-assisted workflow preparation.

For mortgage stakeholders, this means AegisFlow will begin to show whether AI assistance is useful, consistent, and safe enough to keep improving.

Examples of business value:
- identify whether agent outputs are complete enough for human review
- detect hallucination-like unsupported claims in structured agent summaries
- compare prompt versions against stable local scenarios
- evaluate whether human review escalation recommendations align with expected outcomes
- preserve quality signals for governance discussions without treating AI as a decision maker
- establish a regression foundation before adding less deterministic model providers

## Business Boundary

Phase 7 will not implement autonomous mortgage decisions.

Phase 7 will not replace human approval, compliance review, underwriting judgment, servicing policy, or downstream mortgage system controls.

Phase 7 will not connect to production evaluation platforms or external judge models by default.

Phase 7 will not implement full workflow replay and failure recovery tooling. It will implement evaluation replay datasets and replay-safe scoring paths that prepare for the later replay phase.

---

# Current Implementation Baseline

Phase 7 starts from the completed Phase 6 baseline.

Implemented runtime services:
- `gateway-api`
- `workflow-engine`
- `agent-runtime`
- `tool-runtime`
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

Existing evaluation-related foundation:
- `apps/evaluation-service` placeholder exists
- agent executions persist prompt ID, prompt version, model name, confidence score, validation status, human review requirement, structured output, and metadata
- tool invocations persist permission status, validation status, output metadata, and correlation ID
- approval records persist operator decision, reason, comment, reviewer identity, and metadata
- workflow timelines provide ordered workflow context
- observability provides trace, metric, and log context for evaluation runs

Phase 7 must extend this baseline without weakening workflow-engine ownership of workflow state or treating evaluation scores as mortgage decisions.

---

# Target Phase 7 Scope

## In Scope

Phase 7 should implement:
- evaluation-service FastAPI service
- evaluation result persistence
- evaluation dataset definitions for local scenarios
- deterministic local scoring for current agent outputs
- LLM-as-judge adapter boundary with external judging disabled by default
- hallucination signal checks based on available structured evidence
- prompt and model version regression summaries
- replay-aware evaluation run records
- gateway-api read access to evaluation summaries where appropriate
- Postman validation requests for evaluation runs and evaluation retrieval
- Prometheus metrics and OpenTelemetry tracing for evaluation-service
- structured logs with correlation ID and trace ID support
- documentation updates for current functionality, roadmap, data model, and developer workflow

## Out Of Scope

Phase 7 must not implement:
- production LLM-as-judge integration enabled by default
- production evaluation vendor integration
- full workflow replay engine
- workflow recovery tooling
- automatic blocking of workflow approvals based on evaluation scores
- autonomous underwriting, credit, compliance, or servicing decisions
- production identity provider integration
- production RBAC enforcement
- production mortgage system integration
- storage of raw document content, borrower PII, secrets, prompt content, or full model outputs beyond existing local simulation records

---

# Proposed Runtime Architecture

## Local Evaluation Service

Phase 7 should turn `apps/evaluation-service` into a local FastAPI service.

Initial responsibilities:
- expose health and readiness endpoints
- run deterministic evaluation against persisted workflow evidence
- persist evaluation run and result records
- expose evaluation result retrieval endpoints
- emit traces, metrics, and structured logs

Preferred local service flow:

```text
Postman or gateway-api
    ->
evaluation-service
    ->
Postgres workflow, agent, tool, approval, and evaluation records
```

The evaluation-service reads workflow evidence but does not own or mutate workflow state.

## Evaluation Data Flow

```text
Workflow execution completes or reaches HUMAN_REVIEW_REQUIRED
    ->
Agent, tool, timeline, and approval records are available
    ->
Evaluation run is requested
    ->
Evaluation-service loads bounded workflow evidence
    ->
Deterministic evaluators score quality dimensions
    ->
Evaluation records are persisted
    ->
Gateway/Postman/operator tooling can retrieve evaluation summaries
```

## Persistence Model

Recommended initial tables:
- `evaluation_runs`
- `evaluation_results`
- `evaluation_dataset_cases`

Recommended `evaluation_runs` fields:
- `evaluation_run_id`
- `workflow_id`
- `correlation_id`
- `evaluation_scope`
- `evaluation_mode`
- `dataset_id`
- `status`
- `started_at`
- `completed_at`
- `created_by`
- `run_metadata`

Recommended `evaluation_results` fields:
- `evaluation_result_id`
- `evaluation_run_id`
- `workflow_id`
- `agent_execution_id`
- `prompt_id`
- `prompt_version`
- `model_name`
- `evaluator_id`
- `evaluator_version`
- `score_name`
- `score_value`
- `score_status`
- `severity`
- `rationale`
- `result_metadata`
- `created_at`

Recommended `evaluation_dataset_cases` fields:
- `dataset_case_id`
- `dataset_id`
- `case_name`
- `workflow_type`
- `expected_agents`
- `expected_tools`
- `expected_human_review`
- `expected_decision`
- `expected_signals`
- `case_metadata`
- `created_at`

Evaluation records must store bounded summaries and references, not raw sensitive artifacts.

## Evaluation Modes

Recommended initial modes:
- `deterministic_local`
- `dataset_replay`
- `judge_model_disabled`

Future modes may include:
- `llm_as_judge`
- `historical_replay`
- `human_review_sample`

The initial implementation should keep external model judging disabled by default.

## Judge Model Boundary

Phase 7 should define the LLM-as-judge contract without requiring an external model provider during local validation.

Initial boundary:
- evaluator interface for qualitative judge scoring
- explicit evaluator ID and evaluator version
- explicit rubric ID and rubric version
- deterministic local fallback for tests
- configuration switch that keeps external judge calls disabled by default
- structured judge result shape for future provider integration

The judge boundary must not store prompt content, raw document content, borrower PII, secrets, or full model output.

---

# Evaluation Dimensions

## Agent Output Evaluation

Initial deterministic checks:
- output schema validation status is `VALIDATED`
- required output fields are present
- confidence score is within expected range
- `requires_human_review` is present and boolean
- agent output includes bounded rationale or summary fields expected by the agent contract
- agent execution references the expected prompt ID and prompt version

## Tool Usage Evaluation

Initial deterministic checks:
- expected tools were invoked for the workflow path
- tool permission status is `AUTHORIZED`
- tool input validation status is `VALIDATED`
- tool output validation status is `VALIDATED`
- tool invocation records are associated with the correct workflow and agent

## Escalation Evaluation

Initial deterministic checks:
- workflow reaches `HUMAN_REVIEW_REQUIRED`
- agent outputs support human review requirement where expected
- approval or rejection decision path completes only after human decision dispatch
- duplicate terminal decisions remain rejected by existing backend logic

## Hallucination Signal Evaluation

Initial deterministic signals:
- agent output references unsupported tool IDs
- agent output omits expected evidence references
- agent output claims tool context when no matching tool invocation record exists
- confidence is high while validation or evidence checks fail

Severity levels:
- `informational`
- `moderate`
- `critical`

## Prompt Regression Evaluation

Initial deterministic comparison:
- current prompt version appears in agent execution records
- expected local dataset cases still produce validated outputs
- expected tool usage remains stable
- human review escalation remains stable
- quality scores do not fall below configured local thresholds

---

# API Scope

## evaluation-service Endpoints

Recommended endpoints:

```text
GET /health
GET /ready
GET /metrics
POST /api/v1/evaluations/workflows/{workflow_id}/runs
GET /api/v1/evaluations/runs/{evaluation_run_id}
GET /api/v1/evaluations/workflows/{workflow_id}/runs
GET /api/v1/evaluations/datasets
GET /api/v1/evaluations/datasets/{dataset_id}/cases
```

## gateway-api Endpoints

Recommended gateway read surface:

```text
GET /api/v1/workflows/{workflow_id}/evaluations
```

Gateway write-through to evaluation-service can be deferred unless needed for Postman ergonomics.

---

# Observability Requirements

Phase 7 must extend Phase 6 observability.

Required traces:
- evaluation run request
- workflow evidence loading
- evaluator execution
- evaluation result persistence

Required metrics:
- evaluation runs total by scope, mode, and status
- evaluation run duration
- evaluation results total by evaluator, score name, status, and severity
- hallucination signals total by severity
- prompt regression results total by prompt ID, prompt version, and status

Metric labels must remain low-cardinality.

Metrics must not label by:
- workflow ID
- evaluation run ID
- trace ID
- approval ID
- borrower values
- prompt content
- document content
- comments

Required logs:
- evaluation run started
- evaluation run completed
- evaluation run failed
- evaluation result persisted

Logs must include correlation ID and trace ID where available and avoid sensitive payloads.

---

# Workstreams

## Workstream 1 - Evaluation Service Skeleton

Status: Completed

Tasks:
- scaffold `apps/evaluation-service` FastAPI application - Complete
- add `pyproject.toml`, Dockerfile, package structure, and tests - Complete
- add settings for service name, environment, log level, database URL, telemetry, and metrics port - Complete
- add `GET /health`, `GET /ready`, and `GET /metrics` - Complete
- add local Docker Compose service on a stable port - Complete
- add Prometheus scrape target - Complete
- add structured logging, trace setup, and metrics helpers consistent with Phase 6 services - Complete

Completion criteria:
- evaluation-service starts locally - Met
- health and readiness endpoints pass - Met
- metrics endpoint is scrapeable - Met
- Prometheus target is `up` - Met
- basic service tests pass - Met

---

## Workstream 2 - Evaluation Persistence Model

Status: Completed

Tasks:
- add Alembic migration for evaluation persistence tables - Complete
- add SQLAlchemy models for evaluation runs, results, and dataset cases - Complete
- add repository/service layer for creating and retrieving evaluation records - Complete
- add DTOs and schema validation for evaluation records - Complete
- ensure records use bounded metadata and references rather than raw sensitive payloads - Complete
- add tests for persistence, idempotency expectations, and retrieval ordering - Complete

Completion criteria:
- evaluation tables are created locally - Met
- evaluation records can be persisted and retrieved - Met
- model constraints preserve workflow association and reproducibility metadata - Met
- tests pass - Met

---

## Workstream 3 - Deterministic Local Evaluators

Status: Not Started

Tasks:
- implement deterministic agent output evaluator
- implement deterministic tool usage evaluator
- implement deterministic escalation evaluator
- implement hallucination signal evaluator based on structured evidence consistency
- define evaluator IDs and evaluator versions
- define score statuses such as `PASS`, `WARN`, and `FAIL`
- add unit tests for passing, warning, and failing scenarios

Completion criteria:
- deterministic evaluators score existing local workflow evidence
- evaluators produce bounded rationales and metadata
- hallucination signal checks are evidence-based and reproducible
- tests pass without external model dependencies

---

## Workstream 4 - Judge Model Boundary

Status: Not Started

Tasks:
- define LLM-as-judge evaluator interface and result schema
- add evaluator ID, evaluator version, rubric ID, and rubric version metadata
- implement deterministic local fallback judge for tests and local validation
- add configuration switch for external judge model enablement, defaulting to disabled
- document provider integration as future work unless explicitly enabled
- add tests proving default local validation does not call external models

Completion criteria:
- judge-style scoring has a stable internal contract
- external model judging is disabled by default
- local tests can exercise judge result persistence deterministically
- sensitive prompt, document, borrower, and full-output payloads are not persisted by judge results

---

## Workstream 5 - Evaluation Run Orchestration

Status: Not Started

Tasks:
- implement evaluation run creation endpoint
- load workflow, agent execution, tool invocation, timeline, and approval records for a workflow
- execute deterministic evaluators against the bounded evidence set
- persist evaluation run and result records
- handle missing workflows and incomplete workflows with structured errors
- make evaluation run execution idempotent where practical for repeated local validation
- add integration tests against seeded workflow evidence

Completion criteria:
- a local workflow can receive an evaluation run
- results are persisted and retrievable
- missing and incomplete workflow cases are handled clearly
- repeated evaluation does not corrupt workflow state or duplicate unsafe side effects
- tests pass

---

## Workstream 6 - Dataset And Replay-Aware Evaluation

Status: Not Started

Tasks:
- define local evaluation dataset case format
- seed initial Mortgage Exception Review local dataset cases
- add dataset listing and case retrieval endpoints
- support evaluating a workflow against an expected dataset case
- compare expected agents, tools, human review requirement, and decision path against actual records
- document the boundary between evaluation replay datasets and full workflow replay engine
- add tests for dataset-case scoring

Completion criteria:
- local dataset cases are versioned or explicitly identified
- evaluation runs can reference a dataset case
- dataset comparison results are persisted
- replay-aware evaluation is side-effect free
- tests pass

---

## Workstream 7 - Gateway And Postman Validation

Status: Not Started

Tasks:
- add gateway-api evaluation retrieval endpoint if needed for operator and Postman ergonomics
- add Postman requests for evaluation-service health, readiness, metrics, run creation, run retrieval, workflow run listing, dataset listing, and dataset case retrieval
- extend current manual validation flow to run an evaluation after approval and rejection workflows
- document expected evaluation results for the local deterministic scenario
- validate Postman collection JSON

Completion criteria:
- Postman can create and retrieve evaluation runs
- Postman can validate deterministic scores after workflow execution
- manual validation covers approval and rejection evaluation paths
- collection JSON validates

---

## Workstream 8 - Evaluation Observability And Dashboards

Status: Not Started

Tasks:
- emit evaluation-service traces for run creation, evidence loading, evaluator execution, and persistence
- emit evaluation-service metrics for run counts, durations, result counts, and hallucination signal counts
- add Grafana dashboard panels or a dedicated dashboard for evaluation runs and quality signals
- validate Jaeger contains evaluation-service traces
- validate Prometheus scrapes evaluation-service metrics
- validate Grafana displays evaluation activity

Completion criteria:
- evaluation-service appears in Jaeger
- Prometheus target is `up`
- dashboard panels show local evaluation activity
- logs, metrics, and traces avoid sensitive payloads

---

## Workstream 9 - Documentation And Phase Closeout

Status: Not Started

Tasks:
- update `CURRENT_FUNCTIONALITY.md`
- update `IMPLEMENTATION_ROADMAP.md`
- update `AI_EVALUATION_STRATEGY.md` with implementation decisions
- update `DATA_MODEL.md` for implemented evaluation records
- update `API_CONTRACTS.md` for evaluation endpoints
- update `DEVELOPER_WORKFLOW.md` with evaluation validation commands
- add Phase 7 completion log after validation

Completion criteria:
- documentation describes implemented behavior, not aspirational behavior
- business-facing boundary remains clear
- manual tester can run workflow evaluation locally
- automated tests and manual validation are recorded

---

# Validation Plan

## Automated Tests

Expected test suites:
- evaluation-service tests
- gateway-api tests where gateway evaluation endpoints are added
- workflow-engine tests if workflow evidence contracts change
- agent-runtime tests if agent output contracts change
- tool-runtime tests if tool telemetry contracts change
- Postman collection JSON validation

Minimum validation:
- evaluation-service starts without external model providers
- evaluation persistence works against local Postgres
- deterministic evaluators score seeded evidence correctly
- evaluation run creation does not mutate workflow state
- evaluation retrieval returns bounded result data
- metrics endpoints do not expose sensitive payloads
- telemetry configuration does not break tests when disabled

---

## Manual Validation

Expected manual flow:
- start local Docker Compose stack
- create a Mortgage Exception Review workflow through Postman
- poll to `HUMAN_REVIEW_REQUIRED`
- approve one workflow to `COMPLETED`
- create and reject a separate workflow to `COMPLETED`
- create evaluation runs for both workflows
- inspect evaluation run results
- inspect Prometheus metrics for evaluation-service
- inspect Jaeger traces for evaluation-service
- inspect Grafana evaluation panels
- inspect structured logs by correlation ID

Expected manual result:
- approval and rejection workflows remain unchanged by evaluation
- evaluation runs complete successfully
- agent, tool, escalation, hallucination signal, and dataset comparison results are persisted
- evaluation scores are visible through API/Postman
- traces, metrics, dashboards, and logs reflect evaluation activity

---

# Risk Register

## Risk 1 - Evaluation Is Mistaken For Decision Authority

Mitigation:
- document evaluation as quality telemetry and governance support
- keep workflow-engine and human review authoritative
- prevent evaluation-service from mutating workflow state

---

## Risk 2 - Sensitive Data Leaks Into Evaluation Records

Mitigation:
- persist bounded summaries, references, score values, statuses, and rationales
- avoid raw document contents, borrower PII, prompt content, full model output, and approval comments where not required
- review evaluator metadata before adding persistence

---

## Risk 3 - Replay Evaluation Causes Side Effects

Mitigation:
- keep Phase 7 replay support dataset-based and side-effect free
- avoid invoking workflow activities that mutate state during evaluation
- defer full replay engine behavior to the later replay phase

---

## Risk 4 - LLM-as-Judge Adds Nondeterminism Too Early

Mitigation:
- implement deterministic local evaluators first
- keep external judge models disabled by default
- require explicit evaluator IDs, versions, thresholds, and reproducibility metadata

---

## Risk 5 - Evaluation Metrics Become High Cardinality

Mitigation:
- do not label metrics with workflow IDs, run IDs, approval IDs, trace IDs, borrower values, prompt content, or document content
- use IDs in persisted records and traces, not metric labels
- keep dashboards aggregate-first

---

# Phase 7 Completion Criteria

Phase 7 is complete when:
- evaluation-service starts in local Docker Compose
- evaluation persistence tables exist and are tested
- deterministic local evaluators score workflow evidence
- evaluation runs can be created and retrieved
- approval and rejection workflows can both be evaluated
- evaluation records preserve prompt and model version traceability
- replay-aware dataset cases can be listed and used for scoring
- evaluation-service emits traces, metrics, and structured logs
- Grafana or dashboard panels expose evaluation activity
- Postman validates local evaluation workflows
- evaluation avoids sensitive payload exposure
- documentation and roadmap are updated

---

# Running Status Log

## 2026-05-12

Status:
- Phase 7 planning started after Phase 6 completion
- continuous implementation plan created

Next step:
- implement Workstream 1: Evaluation Service Skeleton

## 2026-05-12 - Workstream 1

Status:
- scaffolded `apps/evaluation-service` as a FastAPI application
- added evaluation-service package metadata, Dockerfile, and test structure
- added settings for service identity, database URL, metrics port, logging, telemetry enablement, and OTLP endpoint
- added lazy async database readiness check
- added `GET /health`, `GET /ready`, and `GET /metrics`
- added Prometheus HTTP request, error, latency, and startup metrics
- added OpenTelemetry request middleware and OTLP trace export configuration
- added structured JSON logging with bounded evaluation context fields
- added Docker Compose service on port `8040`
- added Prometheus scrape target for `evaluation-service`
- validated Docker Compose configuration
- validated evaluation-service automated tests with 3 passing tests
- built and started evaluation-service locally
- validated local health endpoint
- validated local readiness endpoint against Postgres
- validated local metrics endpoint
- reloaded Prometheus and validated `evaluation-service` scrape target as `up`
- validated Jaeger lists `evaluation-service` after local requests

Completed workstream:
- Workstream 1 - Evaluation Service Skeleton

Boundary:
- Workstream 1 provides the service shell only
- evaluation persistence, evaluator logic, run orchestration, datasets, gateway endpoints, Postman requests, and dashboards remain assigned to later Phase 7 workstreams
- evaluation-service does not mutate workflow state or perform mortgage decisions

Next step:
- implement Workstream 2: Evaluation Persistence Model

## 2026-05-12 - Workstream 2

Status:
- added Alembic migration `20260512_0006_add_evaluation_records`
- added `evaluation_dataset_cases`, `evaluation_runs`, and `evaluation_results` tables
- added indexes for workflow, correlation, dataset, status, evaluator, score, and severity lookup paths
- added foreign key constraints to preserve workflow, agent execution, and evaluation run associations
- added evaluation-service SQLAlchemy models for workflow references, agent execution references, evaluation runs, evaluation results, and dataset cases
- added async session factory support for evaluation-service database access
- added Pydantic DTOs for evaluation run, evaluation result, and dataset case create/read shapes
- added evaluation repository and persistence service for create, retrieve, list, and idempotent explicit-ID operations
- added tests for run/result persistence, explicit run ID idempotency, workflow run ordering, and dataset case filtering
- rebuilt evaluation-service image with persistence modules
- validated evaluation-service automated tests with 7 passing tests
- rebuilt gateway-api image with the new Alembic migration
- applied Alembic upgrade to local Postgres
- validated local Postgres contains all three evaluation tables
- restarted evaluation-service and validated readiness against the migrated database

Completed workstream:
- Workstream 2 - Evaluation Persistence Model

Boundary:
- Workstream 2 stores evaluation records and dataset definitions only
- deterministic evaluator logic, run orchestration endpoints, dataset scoring behavior, gateway/Postman requests, and dashboards remain assigned to later Phase 7 workstreams
- evaluation records preserve references and bounded metadata, not raw document contents, borrower PII, secrets, prompt content, or full model output

Next step:
- implement Workstream 3: Deterministic Local Evaluators

---

# Decision Log

## Decision 1 - Evaluation Is Quality Governance, Not Workflow Authority

Decision:
- Phase 7 evaluation records will support quality measurement, regression analysis, and governance review, but they will not approve, reject, complete, or mutate workflows.

Reason:
- workflow-engine ownership of state is an AegisFlow architectural constraint
- human review remains authoritative for critical mortgage actions
- evaluation results may be incomplete, probabilistic, or later recomputed

---

## Decision 2 - Deterministic Local Evaluators First

Decision:
- Phase 7 will implement deterministic local evaluators before enabling LLM-as-judge behavior.

Reason:
- deterministic checks provide stable regression protection
- local validation must not depend on external model providers
- reproducibility is required before qualitative judging is introduced

---

## Decision 3 - Replay-Aware Datasets Before Full Replay Engine

Decision:
- Phase 7 will support evaluation datasets and side-effect-free replay-aware scoring, but full workflow replay and recovery tooling remain outside the phase.

Reason:
- dataset scoring establishes evaluation contracts without invoking unsafe side effects
- full replay tooling is broader than AI quality measurement
- this preserves a clean boundary for the later replay and recovery phase
