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

Status: Completed

Tasks:
- implement deterministic agent output evaluator - Complete
- implement deterministic tool usage evaluator - Complete
- implement deterministic escalation evaluator - Complete
- implement hallucination signal evaluator based on structured evidence consistency - Complete
- define evaluator IDs and evaluator versions - Complete
- define score statuses such as `PASS`, `WARN`, and `FAIL` - Complete
- add unit tests for passing, warning, and failing scenarios - Complete

Completion criteria:
- deterministic evaluators score existing local workflow evidence - Met
- evaluators produce bounded rationales and metadata - Met
- hallucination signal checks are evidence-based and reproducible - Met
- tests pass without external model dependencies - Met

---

## Workstream 4 - Judge Model Boundary

Status: Completed

Tasks:
- define LLM-as-judge evaluator interface and result schema - Complete
- add evaluator ID, evaluator version, rubric ID, and rubric version metadata - Complete
- implement deterministic local fallback judge for tests and local validation - Complete
- add configuration switch for external judge model enablement, defaulting to disabled - Complete
- document provider integration as future work unless explicitly enabled - Complete
- add tests proving default local validation does not call external models - Complete

Completion criteria:
- judge-style scoring has a stable internal contract - Met
- external model judging is disabled by default - Met
- local tests can exercise judge result persistence deterministically - Met
- sensitive prompt, document, borrower, and full-output payloads are not persisted by judge results - Met

---

## Workstream 5 - Evaluation Run Orchestration

Status: Completed

Tasks:
- implement evaluation run creation endpoint - Complete
- load workflow, agent execution, tool invocation, timeline, and approval records for a workflow - Complete
- execute deterministic evaluators against the bounded evidence set - Complete
- persist evaluation run and result records - Complete
- handle missing workflows and incomplete workflows with structured errors - Complete
- make evaluation run execution idempotent where practical for repeated local validation - Complete
- add integration tests against seeded workflow evidence - Complete

Completion criteria:
- a local workflow can receive an evaluation run - Met
- results are persisted and retrievable - Met
- missing and incomplete workflow cases are handled clearly - Met
- repeated evaluation does not corrupt workflow state or duplicate unsafe side effects - Met
- tests pass - Met

---

## Workstream 6 - Dataset And Replay-Aware Evaluation

Status: Completed

Tasks:
- define local evaluation dataset case format - Complete
- seed initial Mortgage Exception Review local dataset cases - Complete
- add dataset listing and case retrieval endpoints - Complete
- support evaluating a workflow against an expected dataset case - Complete
- compare expected agents, tools, human review requirement, and decision path against actual records - Complete
- document the boundary between evaluation replay datasets and full workflow replay engine - Complete
- add tests for dataset-case scoring - Complete

Completion criteria:
- local dataset cases are versioned or explicitly identified - Met
- evaluation runs can reference a dataset case - Met
- dataset comparison results are persisted - Met
- replay-aware evaluation is side-effect free - Met
- tests pass - Met

---

## Workstream 7 - Gateway And Postman Validation

Status: Completed

Tasks:
- add gateway-api evaluation retrieval endpoint if needed for operator and Postman ergonomics - Complete
- add Postman requests for evaluation-service health, readiness, metrics, run creation, run retrieval, workflow run listing, dataset listing, and dataset case retrieval - Complete
- extend current manual validation flow to run an evaluation after approval and rejection workflows - Complete
- document expected evaluation results for the local deterministic scenario - Complete
- validate Postman collection JSON - Complete

Completion criteria:
- Postman can create and retrieve evaluation runs - Met
- Postman can validate deterministic scores after workflow execution - Met
- manual validation covers approval and rejection evaluation paths - Met
- collection JSON validates - Met

---

## Workstream 8 - Evaluation Observability And Dashboards

Status: Completed

Tasks:
- emit evaluation-service traces for run creation, evidence loading, evaluator execution, and persistence - Complete
- emit evaluation-service metrics for run counts, durations, result counts, and hallucination signal counts - Complete
- add Grafana dashboard panels or a dedicated dashboard for evaluation runs and quality signals - Complete
- validate Jaeger contains evaluation-service traces - Complete
- validate Prometheus scrapes evaluation-service metrics - Complete
- validate Grafana displays evaluation activity - Complete

Completion criteria:
- evaluation-service appears in Jaeger - Met
- Prometheus target is `up` - Met
- dashboard panels show local evaluation activity - Met
- logs, metrics, and traces avoid sensitive payloads - Met

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

## 2026-05-12 - Workstream 3

Status:
- added bounded workflow evidence dataclasses for workflow, agent execution, tool invocation, and scenario expectations
- added deterministic evaluator protocol and reusable `EvaluationScore` result draft
- defined evaluator version `v1`
- defined score statuses `PASS`, `WARN`, and `FAIL`
- defined severity values `informational`, `moderate`, and `critical`
- implemented `agent-output-contract` evaluator for schema, validation, prompt/model metadata, confidence, and human review consistency checks
- implemented `tool-usage-contract` evaluator for expected tool coverage and governed tool invocation contract checks
- implemented `human-review-escalation` evaluator for review-state, agent review signal, and expected terminal decision consistency
- implemented `evidence-consistency-signals` evaluator for unsupported tool claims and high-confidence validation failure signals
- added deterministic evaluator runner for executing all local evaluators without external model dependencies
- added unit tests covering passing, warning, and failing paths for all deterministic evaluators
- rebuilt evaluation-service image with evaluator modules
- validated evaluation-service automated tests with 20 passing tests

Completed workstream:
- Workstream 3 - Deterministic Local Evaluators

Boundary:
- Workstream 3 is side-effect free and does not read or write database records
- evaluator result drafts are not persisted until later run orchestration workstreams
- hallucination checks are deterministic evidence consistency signals, not external LLM-as-judge results
- no external model provider dependency is introduced

Next step:
- implement Workstream 4: Judge Model Boundary

## 2026-05-12 - Workstream 4

Status:
- added the internal judge-model evaluator protocol and request/result contract
- added explicit evaluator ID, evaluator version, rubric ID, and rubric version metadata for judge-style scores
- added deterministic local judge fallback for reproducible local validation
- added `ENABLE_EXTERNAL_JUDGE_MODEL` and `EXTERNAL_JUDGE_MODEL_PROVIDER` settings, with external judging disabled by default
- added an external judge boundary that fails closed when disabled and keeps provider integration as future work
- converted judge results into existing evaluation result records for deterministic persistence
- added tests for default-disabled external judging, fallback PASS/WARN/FAIL behavior, bounded metadata, and judge result persistence
- rebuilt the evaluation-service image
- validated evaluation-service automated tests with 26 passing tests

Completed workstream:
- Workstream 4 - Judge Model Boundary

Boundary:
- no external model provider is called by default
- judge-style scoring is an evaluation quality signal only and does not mutate workflow state or affect mortgage decisions
- run orchestration endpoints, workflow evidence loading, dataset scoring, gateway/Postman coverage, and dashboards remain assigned to later workstreams
- judge result metadata stores rubric references and bounded scoring context, not prompt content, raw documents, borrower PII, secrets, or full model outputs

Next step:
- implement Workstream 5: Evaluation Run Orchestration

## 2026-05-12 - Workstream 5

Status:
- added evaluation-service read models for workflow, timeline, agent execution, tool invocation, approval, and event evidence tables
- added repository queries for workflow evidence loading and evaluation run retrieval
- added evaluation run request, detail, and summary DTOs
- added `POST /api/v1/evaluations/workflows/{workflow_id}/runs`
- added `GET /api/v1/evaluations/runs/{evaluation_run_id}`
- added `GET /api/v1/evaluations/workflows/{workflow_id}/runs`
- implemented workflow evidence loading from persisted bounded records
- executed deterministic local evaluators against workflow evidence
- supported `judge_model_disabled` mode by adding the deterministic judge-boundary result to persisted scores
- persisted evaluation run and result records without mutating workflow state
- returned structured errors for missing workflows and workflows not ready for evaluation
- preserved practical idempotency for repeated requests with an explicit `evaluation_run_id`
- rebuilt the evaluation-service image
- validated evaluation-service automated tests with 32 passing tests

Completed workstream:
- Workstream 5 - Evaluation Run Orchestration

Boundary:
- evaluation run creation is local evaluation only and does not approve, reject, complete, or mutate workflows
- workflow evidence loading reads existing authoritative records and stores bounded evaluation references and scores
- dataset listing, dataset scoring, gateway evaluation retrieval, Postman validation, evaluation dashboards, and phase closeout documentation remain assigned to later workstreams

Next step:
- implement Workstream 6: Dataset And Replay-Aware Evaluation

## 2026-05-12 - Workstream 6

Status:
- added explicit local dataset case definitions for `mortgage-exception-local-v1`
- seeded approval, rejection, and human-review Mortgage Exception Review dataset cases idempotently through evaluation-service
- added dataset summary DTOs and dataset case request support
- added `GET /api/v1/evaluations/datasets`
- added `GET /api/v1/evaluations/datasets/{dataset_id}/cases`
- added `dataset_case_id` support to evaluation run creation
- added `dataset-replay-contract` evaluator for dataset case alignment
- compared expected agents, tools, human review requirement, and terminal decision against persisted workflow evidence
- persisted dataset comparison results as evaluation results
- stored dataset case identity and replay boundary metadata on evaluation run metadata
- rebuilt the evaluation-service image
- validated evaluation-service automated tests with 36 passing tests

Completed workstream:
- Workstream 6 - Dataset And Replay-Aware Evaluation

Boundary:
- dataset replay is side-effect-free scoring against persisted records only
- Phase 7 dataset replay does not invoke Temporal replay, workflow activities, agent execution, tool execution, approval dispatch, or recovery behavior
- full workflow replay and failure recovery remain assigned to the later replay phase
- gateway/Postman validation, dashboards, and phase closeout documentation remain assigned to later workstreams

Next step:
- implement Workstream 7: Gateway And Postman Validation

## 2026-05-12 - Workstream 7

Status:
- added read-only gateway-api retrieval for persisted workflow evaluation runs and results at `GET /api/v1/workflows/{workflow_id}/evaluations`
- added gateway DTOs and read models for evaluation runs and evaluation results
- added workflow service queries for evaluation run and result retrieval
- added automated gateway coverage for persisted evaluation retrieval
- expanded the Postman collection with evaluation-service health, readiness, metrics, dataset listing, dataset case listing, run creation, run retrieval, workflow run listing, and gateway evaluation retrieval
- extended the manual Postman approval path to create and validate an approval dataset replay evaluation run
- extended the manual Postman rejection path to create and validate a rejection dataset replay evaluation run
- documented expected deterministic `dataset-replay-contract` `PASS` results for local approval and rejection scenarios
- validated the Postman collection JSON and test script syntax
- rebuilt the gateway-api image and validated gateway-api tests with 17 passing tests

Completed workstream:
- Workstream 7 - Gateway And Postman Validation

Boundary:
- gateway evaluation retrieval is read-only and does not create evaluation runs
- evaluation-service remains the evaluation run creation boundary
- evaluation results are quality telemetry only and do not mutate workflow state, approve workflows, reject workflows, or bypass human review

Next step:
- implement Workstream 8: Evaluation Observability And Dashboards

## 2026-05-12 - Workstream 8

Status:
- added evaluation-service spans for evaluation run creation, workflow evidence loading, evaluator execution, and result persistence
- added bounded structured logs for evaluation run start, completion, failure, and result persistence
- added Prometheus metrics for evaluation run counts, run duration, persisted results, evidence-consistency signals, and prompt-attributed result status
- kept metric labels aggregate and avoided workflow IDs, run IDs, trace IDs, borrower values, prompt content, document content, and approval comments
- added `AegisFlow - Evaluation Quality` Grafana dashboard for evaluation runs, durations, evaluator results, evidence-consistency signals, and prompt-attributed result trends
- updated the service health dashboard to include evaluation-service scrape health and HTTP request metrics
- updated Postman dashboard validation to expect the evaluation dashboard
- validated dashboard JSON files, Postman JSON, and Postman test script syntax
- rebuilt the evaluation-service image and validated evaluation-service automated tests

Completed workstream:
- Workstream 8 - Evaluation Observability And Dashboards

Boundary:
- evaluation observability is aggregate operational telemetry only
- metrics, dashboards, traces, and logs do not mutate workflow state or become the system of record for mortgage decisions
- external judge models remain disabled by default

Next step:
- implement Workstream 9: Documentation And Phase Closeout

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
