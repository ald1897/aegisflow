from prometheus_client import Counter, Histogram, start_http_server

_metrics_server_started = False

WORKFLOW_ACTIVITY_EXECUTIONS_TOTAL = Counter(
    "aegisflow_workflow_engine_activity_executions_total",
    "Workflow-engine Temporal activity executions.",
    ("activity", "status"),
)
WORKFLOW_ACTIVITY_DURATION_SECONDS = Histogram(
    "aegisflow_workflow_engine_activity_duration_seconds",
    "Workflow-engine Temporal activity execution duration.",
    ("activity", "status"),
)

WORKFLOW_STATE_TRANSITIONS_TOTAL = Counter(
    "aegisflow_workflow_engine_state_transitions_total",
    "Workflow state transition attempts handled by workflow-engine.",
    ("prior_state", "new_state", "status"),
)

AGENT_EXECUTIONS_TOTAL = Counter(
    "aegisflow_workflow_engine_agent_executions_total",
    "Agent execution records handled by workflow-engine.",
    ("agent_id", "status", "validation_status", "requires_human_review"),
)
AGENT_EXECUTION_DURATION_SECONDS = Histogram(
    "aegisflow_workflow_engine_agent_execution_duration_seconds",
    "Agent execution duration measured by workflow-engine.",
    ("agent_id", "status"),
)

TOOL_INVOCATIONS_TOTAL = Counter(
    "aegisflow_workflow_engine_tool_invocations_total",
    "Tool invocation records handled by workflow-engine.",
    ("tool_id", "status", "permission_status"),
)
TOOL_INVOCATION_DURATION_SECONDS = Histogram(
    "aegisflow_workflow_engine_tool_invocation_duration_seconds",
    "Tool invocation duration measured by workflow-engine.",
    ("tool_id", "status"),
)

APPROVAL_DECISIONS_TOTAL = Counter(
    "aegisflow_workflow_engine_approval_decisions_total",
    "Human approval decisions handled by workflow-engine.",
    ("decision", "status"),
)
APPROVAL_DECISION_DURATION_SECONDS = Histogram(
    "aegisflow_workflow_engine_approval_decision_duration_seconds",
    "Human approval decision handling duration.",
    ("decision", "status"),
)

EVENT_PUBLICATIONS_TOTAL = Counter(
    "aegisflow_workflow_engine_event_publications_total",
    "Workflow event publication attempts handled by workflow-engine.",
    ("event_type", "status"),
)
EVENT_PUBLICATION_DURATION_SECONDS = Histogram(
    "aegisflow_workflow_engine_event_publication_duration_seconds",
    "Workflow event publication duration measured by workflow-engine.",
    ("event_type", "status"),
)

WORKER_STARTS_TOTAL = Counter(
    "aegisflow_workflow_engine_worker_starts_total",
    "Workflow-engine worker startup attempts.",
    ("status",),
)


def start_metrics_endpoint(port: int) -> None:
    global _metrics_server_started
    if _metrics_server_started:
        return
    start_http_server(port)
    _metrics_server_started = True


def record_activity_execution(*, activity_name: str, status: str, duration_seconds: float) -> None:
    labels = {"activity": activity_name, "status": status}
    WORKFLOW_ACTIVITY_EXECUTIONS_TOTAL.labels(**labels).inc()
    WORKFLOW_ACTIVITY_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def record_state_transition(*, prior_state: str, new_state: str, status: str) -> None:
    WORKFLOW_STATE_TRANSITIONS_TOTAL.labels(
        prior_state=prior_state,
        new_state=new_state,
        status=status,
    ).inc()


def record_agent_execution(
    *,
    agent_id: str,
    status: str,
    validation_status: str,
    requires_human_review: bool,
    duration_seconds: float,
) -> None:
    AGENT_EXECUTIONS_TOTAL.labels(
        agent_id=agent_id,
        status=status,
        validation_status=validation_status,
        requires_human_review=str(requires_human_review).lower(),
    ).inc()
    AGENT_EXECUTION_DURATION_SECONDS.labels(agent_id=agent_id, status=status).observe(duration_seconds)


def record_tool_invocation(*, tool_id: str, status: str, permission_status: str, duration_seconds: float) -> None:
    TOOL_INVOCATIONS_TOTAL.labels(
        tool_id=tool_id,
        status=status,
        permission_status=permission_status,
    ).inc()
    TOOL_INVOCATION_DURATION_SECONDS.labels(tool_id=tool_id, status=status).observe(duration_seconds)


def record_approval_decision(*, decision: str, status: str, duration_seconds: float) -> None:
    APPROVAL_DECISIONS_TOTAL.labels(decision=decision, status=status).inc()
    APPROVAL_DECISION_DURATION_SECONDS.labels(decision=decision, status=status).observe(duration_seconds)


def record_event_publication(*, event_type: str, status: str, duration_seconds: float) -> None:
    EVENT_PUBLICATIONS_TOTAL.labels(event_type=event_type, status=status).inc()
    EVENT_PUBLICATION_DURATION_SECONDS.labels(event_type=event_type, status=status).observe(duration_seconds)


def record_worker_start(*, status: str) -> None:
    WORKER_STARTS_TOTAL.labels(status=status).inc()
