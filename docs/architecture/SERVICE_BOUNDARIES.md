# Service Boundaries

## Purpose

This document records the current AegisFlow service boundary inventory for Phase 9 Workstream 1.

It exists to make the implemented runtime explicit before Phase 9 adds local RBAC, policy-engine, audit-service, contract validation, and runtime hardening.

This document distinguishes:
- implemented local runtime services
- placeholder service directories
- target architecture components that are not running yet
- data ownership boundaries
- privileged actions that require authorization in later Phase 9 workstreams

Inventory date:
- 2026-05-14

Evidence used:
- local documentation in `docs/`
- `infrastructure/local-dev/docker-compose.yml`
- service source under `apps/`
- gateway, agent-runtime, tool-runtime, evaluation-service, and workflow-engine route and activity definitions

---

# Current Runtime Summary

The local Docker Compose runtime currently includes these application services:
- gateway-api
- workflow-engine
- agent-runtime
- tool-runtime
- evaluation-service
- operator-console

The local Docker Compose runtime currently includes these platform services:
- Postgres
- Redpanda
- Redis
- Temporal
- Temporal UI
- OpenTelemetry Collector
- Jaeger
- Prometheus
- Grafana

The repository contains these placeholder service directories, but they are empty and not wired into local Docker Compose:
- audit-service
- policy-engine
- notification-service

Current implication:
- Phase 9 should not start by re-separating tool-runtime or evaluation-service.
- Phase 9 should harden the services that already run locally and then implement the missing governance service boundaries where the plan calls for them.

---

# Service Boundary Matrix

| Service | Current status | Owns today | Does not own | Runtime dependencies | Data boundary | Phase 9 implication |
| --- | --- | --- | --- | --- | --- | --- |
| gateway-api | Implemented local service on port `8000` | External API surface, workflow creation requests, operational reads, approval submission API, replay/recovery API, local actor/role parsing for privileged gateway actions, event publication for gateway-owned events, correlation middleware, gateway metrics | AI execution, tool execution, final workflow state authority, production authentication, production RBAC, production audit storage | Postgres, Redpanda, Redis availability, Temporal, OpenTelemetry Collector | Reads and writes local workflow/replay/recovery tables; exposes DTOs instead of persistence models | Add policy checks, audit emission, and contract validation at the main ingress boundary |
| workflow-engine | Implemented Temporal worker with metrics on port `8030` | Workflow orchestration, deterministic state transitions, workflow-owned approval decision execution, projection reconciliation recovery activity, agent invocation activity, tool invocation persistence activity, outbox events for workflow facts | Public API ingress, direct frontend access, AI prompt execution, direct external system access, unrestricted recovery | Postgres, Temporal, Redpanda, agent-runtime, OpenTelemetry Collector | Owns workflow progression and workflow state mutation paths; writes state transitions, timeline, outbox, agent, tool, approval, and recovery completion evidence | Keep as state authority; add policy/audit integrations without allowing policy or audit services to mutate workflow state |
| agent-runtime | Implemented internal service on port `8010` | Registered agent execution, prompt loading, structured output validation, deterministic local agent behavior, governed tool-runtime client calls, agent metrics/traces/logs | Workflow state mutation, approval decisions, unrestricted tool discovery, direct external system access, production model provider selection | Prompts, tool-runtime, OpenTelemetry Collector | Does not persist authoritative workflow records directly; returns structured execution telemetry to workflow-engine | Add service-to-service trust and contract tests; keep as internal execution boundary |
| tool-runtime | Implemented internal service on port `8020` | Registered tool catalog, agent-to-tool permission checks, tool input/output validation, deterministic mock tool handlers, tool metrics/traces/logs | Workflow state mutation, production mortgage system access, arbitrary shell/HTTP/database tools, final business decisions | OpenTelemetry Collector | Does not own workflow persistence; workflow-engine persists tool invocation records from agent telemetry | Add policy decision hook later without making tools autonomous or stateful workflow owners |
| evaluation-service | Implemented internal quality service on port `8040` | Evaluation run creation, deterministic local evaluators, dataset case listing, evaluation persistence, judge boundary with external judge disabled by default, evaluation metrics/traces/logs | Workflow state mutation, approval/rejection authority, production judge provider calls, production mortgage decisions | Postgres, OpenTelemetry Collector | Owns evaluation dataset/run/result records; reads workflow evidence from Postgres | Add authorization for evaluation run creation and contract validation; preserve quality-signal-only boundary |
| operator-console | Implemented local frontend on port `3000` | Human review queue UI, workflow evidence display, approval/rejection form, read-only replay/recovery summaries | Direct workflow mutation, direct calls to workflow-engine/agent-runtime/tool-runtime/Postgres/Temporal, production RBAC enforcement | gateway-api | No direct persistence access | Add local role-aware UI behavior after gateway authorization exists; keep gateway as only API boundary |
| policy-engine | Placeholder directory only | Nothing implemented yet | Runtime policy decisions, production policy administration, workflow state mutation | Not wired | No current persistence or API | Workstream 3 should implement a minimal deterministic policy decision boundary for privileged actions |
| audit-service | Placeholder directory only | Nothing implemented yet | Runtime audit ingestion, audit retrieval, workflow state mutation | Not wired | No current persistence or API | Workstream 4 should implement append-only audit event ingestion and bounded retrieval |
| notification-service | Placeholder directory only | Nothing implemented yet | Operational notifications, escalation delivery, production alerting | Not wired | No current persistence or API | Remains out of Phase 9 unless a later explicit workstream changes scope |

---

# Runtime Dependency Map

## User-Facing Flow

```text
operator-console or Postman
    -> gateway-api
    -> Postgres
    -> Temporal
    -> workflow-engine
    -> agent-runtime
    -> tool-runtime
```

Notes:
- operator-console calls gateway-api only.
- gateway-api is the only implemented external workflow API boundary.
- workflow-engine remains the only implemented workflow state mutation authority after creation.
- agent-runtime and tool-runtime are internal execution participants.
- evaluation-service can be called locally for quality runs, but evaluation output is not workflow authority.

## Synchronous Calls

Current synchronous service calls:
- operator-console to gateway-api
- gateway-api to Temporal for workflow start and human review decision dispatch
- workflow-engine to agent-runtime for agent execution activities
- agent-runtime to tool-runtime for governed tool invocation
- evaluation-service to Postgres for workflow evidence and evaluation records

Current direct local API surfaces:
- gateway-api exposes workflow, review, replay, recovery, and metrics endpoints
- agent-runtime exposes agent registry and execution endpoints
- tool-runtime exposes tool registry and invocation endpoints
- evaluation-service exposes evaluation run and dataset endpoints

Hardening gap:
- internal services are reachable on localhost in local development and do not yet require service-to-service authentication.

## Event Publication

Current event topic:

```text
workflow-events
```

Current event producers:
- gateway-api publishes gateway-owned workflow creation events when enabled
- workflow-engine writes and publishes workflow, agent, tool, approval, and recovery events through the outbox boundary

Current event families:
- `workflow.created`
- `workflow.state_changed`
- `workflow.approved`
- `workflow.rejected`
- `workflow.completed`
- `workflow.failed`
- `agent.execution_completed`
- `tool.invocation_completed`
- `tool.invocation_failed`
- `approval.decision_recorded`
- `recovery.action_completed`

Hardening gap:
- event schemas are documented but not mechanically validated by a dedicated contract gate yet.

## Observability Flow

```text
application services
    -> OpenTelemetry Collector
    -> Jaeger

Prometheus
    -> service /metrics endpoints
    -> Grafana
```

Current metric endpoints:
- gateway-api: `http://localhost:8000/metrics`
- workflow-engine: `http://localhost:8030/metrics`
- agent-runtime: `http://localhost:8010/metrics`
- tool-runtime: `http://localhost:8020/metrics`
- evaluation-service: `http://localhost:8040/metrics`

Current dashboard coverage:
- workflow operations
- service health and latency
- agent and tool execution
- approval decisions
- evaluation quality
- replay and recovery

Hardening gap:
- policy and audit telemetry cannot exist until policy-engine and audit-service are implemented.

---

# Data Ownership Inventory

Postgres is the current local system of record. Multiple services access the same local database, but ownership is still defined by domain responsibility.

| Data set | Current tables or records | Current writer | Current readers | Ownership notes |
| --- | --- | --- | --- | --- |
| Workflow records | `workflow_records` | gateway-api creates initial workflow records; workflow-engine owns lifecycle projection updates and recovery reconciliation | gateway-api, workflow-engine, evaluation-service | workflow-engine remains lifecycle authority even though gateway owns external creation ingress |
| Workflow state history | `workflow_state_transitions` | workflow-engine | gateway-api, workflow-engine, evaluation-service | state transitions must remain explicit and append-oriented |
| Workflow timeline | `workflow_timeline_entries` | workflow-engine and gateway-owned creation paths where applicable | gateway-api, workflow-engine, evaluation-service | timeline supports review and replay but does not replace state authority |
| Workflow event outbox | `workflow_event_outbox` | gateway-api and workflow-engine through existing event publisher boundaries | gateway-api, workflow-engine | outbox retry/dead-letter recovery is explicit and auditable |
| Agent execution records | `agent_execution_records` | workflow-engine | gateway-api, workflow-engine, evaluation-service | agent-runtime returns execution data; workflow-engine persists workflow evidence |
| Tool invocation records | `tool_invocation_records` | workflow-engine | gateway-api, workflow-engine, evaluation-service | tool-runtime executes tools; workflow-engine persists workflow-scoped tool evidence |
| Approval records | `approval_records` | workflow-engine decision logic | gateway-api, workflow-engine, evaluation-service | human decisions are workflow-owned and immutable after finalization |
| Evaluation records | `evaluation_dataset_cases`, `evaluation_runs`, `evaluation_results` | evaluation-service | evaluation-service, gateway-api | quality telemetry only; not workflow authority |
| Replay records | `workflow_replay_runs`, `workflow_replay_steps` | gateway-api replay orchestration | gateway-api | side-effect-free diagnostic records only |
| Recovery records | `workflow_recovery_actions` | gateway-api for request records; workflow-engine for projection recovery completion behavior | gateway-api, workflow-engine | workflow state mutation remains workflow-engine owned |
| Audit records | Future audit-service persistence | Not implemented | Not implemented | Phase 9 Workstream 4 must define append-only audit records |
| Policy records | Future policy-engine configuration if needed | Not implemented | Not implemented | Phase 9 Workstream 3 starts with deterministic local policy decisions |

Hardening gap:
- current services share a local database for development speed.
- Phase 9 should document and test ownership rules before introducing more service separation.
- A later production architecture may split physical databases or access paths, but that is not required for Workstream 1.

---

# Privileged Action Inventory

The following actions should be treated as privileged or authorization-relevant in Phase 9.

| Action | Current boundary | Current local control | Target permission name | Notes for later workstreams |
| --- | --- | --- | --- | --- |
| Create workflow | `POST /api/v1/workflows` on gateway-api | Optional actor header defaults to `system` | `workflow:create` | Should require an authenticated local actor once RBAC foundation exists |
| Submit approval decision | `POST /api/v1/workflows/{workflow_id}/approvals` on gateway-api | Requires `X-Actor-ID`, `X-Actor-Roles`, and `workflow:review_decide`; workflow must be reviewable | `workflow:review_decide` | Should call policy-engine and emit audit event before/after decision dispatch |
| Create replay run | `POST /api/v1/workflows/{workflow_id}/replay-runs` on gateway-api | Requires `X-Actor-ID`, `X-Actor-Roles`, and `workflow:replay_create`; replay is side-effect free | `workflow:replay_create` | Replay remains privileged because it inspects operational history |
| View replay run | replay retrieval/listing endpoints on gateway-api | Read-only, no role enforcement yet | `workflow:replay_read` | Should distinguish ordinary workflow readers from replay/admin users |
| Read replay diagnostics | `GET /api/v1/workflows/{workflow_id}/replay-diagnostics` on gateway-api | Read-only, no role enforcement yet | `workflow:replay_read` | Diagnostics may expose operational consistency details |
| Create recovery action | `POST /api/v1/workflows/{workflow_id}/recovery-actions` on gateway-api | Requires `X-Actor-ID`, `X-Actor-Roles`, `workflow:recovery_execute`, reason, and supported action | `workflow:recovery_execute` | Should emit audit record after audit-service exists |
| Retry outbox event | Recovery action `retry_outbox_event` | Requires explicit `workflow_event_outbox` target and `events:outbox_retry` | `events:outbox_retry` | Must continue to use existing event publisher boundary |
| Dead-letter outbox event | Recovery action `mark_outbox_event_dead_lettered` | Requires explicit `workflow_event_outbox` target and `events:outbox_dead_letter` | `events:outbox_dead_letter` | Must be audit-visible because it suppresses future publishing attempts |
| Reconcile workflow projection | Recovery action `reconcile_workflow_projection` | Requires `workflow:projection_reconcile`; gateway request record; workflow-engine owns mutation | `workflow:projection_reconcile` | Policy must preserve workflow-engine state ownership |
| Create evaluation run | `POST /api/v1/evaluations/workflows/{workflow_id}/runs` on evaluation-service | Optional `X-Actor-ID`; defaults to `evaluation-service` | `evaluation:run_create` | Should require local actor/role for direct local calls |
| Read evaluation results | evaluation-service and gateway workflow evaluation endpoints | Read-only, no role enforcement yet | `evaluation:read` | Evaluation results are quality signals but still workflow evidence |
| Execute agent directly | `POST /api/v1/agents/{agent_id}/executions` on agent-runtime | Registered agent and workflow-state validation only | `agent:execute` | Should become service-to-service only for workflow-engine in hardened local runtime |
| Invoke tool directly | `POST /api/v1/tools/{tool_id}/invocations` on tool-runtime | Registered tool, schema validation, agent-to-tool permissions | `tool:invoke` | Should become service-to-service only for agent-runtime in hardened local runtime |
| Read metrics and dashboards | `/metrics`, Prometheus, Grafana, Jaeger | Local network access only | `observability:read` | Future hardening should avoid exposing sensitive operational telemetry broadly |
| Administer policies | Future policy-engine API | Not implemented | `policy:admin` | Must require platform admin role and audit event |
| Inspect audit records | Future audit-service API | Not implemented | `audit:read` | Must be bounded and role-scoped |

Current gap:
- `X-Actor-ID` and `X-Actor-Roles` are local development headers, not production authentication credentials.
- policy decision boundary, audit emission boundary, production identity provider integration, and service-to-service authentication are not implemented yet.

---

# Architecture Gaps Found

## Implemented Versus Planned Services

The architecture documents describe policy-engine, audit-service, notification-service, and integration adapters as platform components.

Current implementation state:
- policy-engine is a placeholder only
- audit-service is a placeholder only
- notification-service is a placeholder only
- integration adapters are represented by deterministic mock tools inside tool-runtime, not separate adapter services

Phase 9 response:
- Workstream 2 should add local identity/RBAC scaffolding.
- Workstream 3 should implement policy-engine as a minimal deterministic policy decision service.
- Workstream 4 should implement audit-service as an append-only audit event service.
- notification-service should remain out of scope unless explicitly added later.

## Internal Trust

Current implementation state:
- internal service endpoints are exposed on localhost for local development
- service-to-service calls propagate correlation and trace context
- service-to-service authentication is not implemented

Phase 9 response:
- Workstream 5 should define service identity and actor propagation headers.
- Policy checks should be made at gateway privileged boundaries first.
- Internal services should not trust arbitrary privileged headers from unvalidated external callers once local RBAC exists.

## Shared Database Access

Current implementation state:
- gateway-api, workflow-engine, and evaluation-service all access Postgres directly
- ownership rules are documented but not mechanically enforced by database boundaries

Phase 9 response:
- Workstream 1 records ownership rules.
- Workstream 6 should add contract validation.
- Later phases can consider database-per-service or narrower access paths if operational pressure justifies it.

## Contract Validation

Current implementation state:
- services expose FastAPI/OpenAPI schemas
- events and DTOs are documented
- automated tests cover many behaviors
- there is no dedicated contract snapshot or event schema validation gate

Phase 9 response:
- Workstream 6 should add mechanical contract validation for implemented APIs and event families.

---

# Workstream 1 Completion Checklist

Completed:
- current implemented services and placeholder directories are distinguished
- gateway-api, workflow-engine, agent-runtime, tool-runtime, evaluation-service, operator-console, policy-engine, and audit-service are included in the service boundary matrix
- notification-service is called out as a placeholder and out-of-scope unless explicitly added later
- synchronous calls, event publication, database ownership, and observability dependencies are mapped
- privileged actions have owning boundaries and target permission names
- architecture gaps between planned and implemented services are documented

No runtime behavior changed in this workstream.
