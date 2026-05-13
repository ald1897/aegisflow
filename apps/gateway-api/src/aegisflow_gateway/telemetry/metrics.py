from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "aegisflow_gateway_http_requests_total",
    "Gateway API HTTP requests.",
    ("method", "route", "status_class"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "aegisflow_gateway_http_request_duration_seconds",
    "Gateway API HTTP request duration.",
    ("method", "route", "status_class"),
)
HTTP_ERRORS_TOTAL = Counter(
    "aegisflow_gateway_http_errors_total",
    "Gateway API HTTP error responses.",
    ("method", "route", "status_class"),
)

WORKFLOW_CREATIONS_TOTAL = Counter(
    "aegisflow_gateway_workflow_creations_total",
    "Gateway API workflow creation attempts.",
    ("workflow_type", "status"),
)

TEMPORAL_WORKFLOW_STARTS_TOTAL = Counter(
    "aegisflow_gateway_temporal_workflow_starts_total",
    "Temporal workflow start attempts initiated by the gateway.",
    ("operation", "workflow_type", "status"),
)
TEMPORAL_WORKFLOW_START_DURATION_SECONDS = Histogram(
    "aegisflow_gateway_temporal_workflow_start_duration_seconds",
    "Temporal workflow start duration for gateway-initiated workflows.",
    ("operation", "workflow_type", "status"),
)

APPROVAL_DECISION_DISPATCHES_TOTAL = Counter(
    "aegisflow_gateway_approval_decision_dispatches_total",
    "Human approval decision dispatch attempts initiated by the gateway.",
    ("decision", "status"),
)
APPROVAL_DECISION_DISPATCH_DURATION_SECONDS = Histogram(
    "aegisflow_gateway_approval_decision_dispatch_duration_seconds",
    "Human approval decision dispatch duration.",
    ("decision", "status"),
)

EVENT_PUBLICATIONS_TOTAL = Counter(
    "aegisflow_gateway_event_publications_total",
    "Workflow event publication attempts initiated by the gateway.",
    ("event_type", "status"),
)
EVENT_PUBLICATION_DURATION_SECONDS = Histogram(
    "aegisflow_gateway_event_publication_duration_seconds",
    "Workflow event publication duration.",
    ("event_type", "status"),
)

REPLAY_RUNS_TOTAL = Counter(
    "aegisflow_gateway_replay_runs_total",
    "Gateway replay run orchestration attempts.",
    ("replay_mode", "status"),
)
REPLAY_RUN_DURATION_SECONDS = Histogram(
    "aegisflow_gateway_replay_run_duration_seconds",
    "Gateway replay run orchestration duration.",
    ("replay_mode", "status"),
)
REPLAY_STEPS_TOTAL = Counter(
    "aegisflow_gateway_replay_steps_total",
    "Gateway replay step validation results.",
    ("artifact_type", "status"),
)

RECOVERY_ACTIONS_TOTAL = Counter(
    "aegisflow_gateway_recovery_actions_total",
    "Gateway recovery action attempts.",
    ("action_type", "status"),
)
RECOVERY_ACTION_DURATION_SECONDS = Histogram(
    "aegisflow_gateway_recovery_action_duration_seconds",
    "Gateway recovery action duration.",
    ("action_type", "status"),
)
OUTBOX_EVENTS_BY_PUBLISH_STATUS = Gauge(
    "aegisflow_gateway_outbox_events_by_publish_status",
    "Current workflow outbox event count by publication status observed by gateway recovery operations.",
    ("publish_status",),
)
OUTBOX_RETRIES_TOTAL = Counter(
    "aegisflow_gateway_outbox_retries_total",
    "Gateway outbox retry attempts.",
    ("event_type", "status"),
)
STUCK_WORKFLOW_DIAGNOSTICS_TOTAL = Counter(
    "aegisflow_gateway_stuck_workflow_diagnostics_total",
    "Gateway stuck workflow recovery diagnostic checks.",
    ("workflow_type", "diagnostic_status"),
)

_OUTBOX_PUBLISH_STATUSES = ("PENDING", "PUBLISHED", "FAILED", "DEAD_LETTERED")


def record_http_request(*, method: str, route: str, status_code: int, duration_seconds: float) -> None:
    status_class = f"{status_code // 100}xx"
    labels = {
        "method": method,
        "route": route,
        "status_class": status_class,
    }
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_seconds)
    if status_code >= 400:
        HTTP_ERRORS_TOTAL.labels(**labels).inc()


def record_workflow_creation(*, workflow_type: str, status: str) -> None:
    WORKFLOW_CREATIONS_TOTAL.labels(workflow_type=workflow_type, status=status).inc()


def record_temporal_workflow_start(
    *,
    operation: str,
    workflow_type: str,
    status: str,
    duration_seconds: float,
) -> None:
    labels = {
        "operation": operation,
        "workflow_type": workflow_type,
        "status": status,
    }
    TEMPORAL_WORKFLOW_STARTS_TOTAL.labels(**labels).inc()
    TEMPORAL_WORKFLOW_START_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def record_approval_decision_dispatch(*, decision: str, status: str, duration_seconds: float) -> None:
    labels = {
        "decision": decision,
        "status": status,
    }
    APPROVAL_DECISION_DISPATCHES_TOTAL.labels(**labels).inc()
    APPROVAL_DECISION_DISPATCH_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def record_event_publication(*, event_type: str, status: str, duration_seconds: float) -> None:
    labels = {
        "event_type": event_type,
        "status": status,
    }
    EVENT_PUBLICATIONS_TOTAL.labels(**labels).inc()
    EVENT_PUBLICATION_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def record_replay_run(*, replay_mode: str, status: str, duration_seconds: float) -> None:
    labels = {
        "replay_mode": replay_mode,
        "status": status,
    }
    REPLAY_RUNS_TOTAL.labels(**labels).inc()
    REPLAY_RUN_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def record_replay_step(*, artifact_type: str, status: str) -> None:
    REPLAY_STEPS_TOTAL.labels(artifact_type=artifact_type, status=status).inc()


def record_recovery_action(*, action_type: str, status: str, duration_seconds: float) -> None:
    labels = {
        "action_type": action_type,
        "status": status,
    }
    RECOVERY_ACTIONS_TOTAL.labels(**labels).inc()
    RECOVERY_ACTION_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def record_outbox_event_status_counts(counts_by_publish_status: dict[str, int]) -> None:
    for publish_status in _OUTBOX_PUBLISH_STATUSES:
        OUTBOX_EVENTS_BY_PUBLISH_STATUS.labels(publish_status=publish_status).set(
            counts_by_publish_status.get(publish_status, 0)
        )


def record_outbox_retry(*, event_type: str, status: str) -> None:
    OUTBOX_RETRIES_TOTAL.labels(event_type=event_type, status=status).inc()


def record_stuck_workflow_diagnostic(*, workflow_type: str, diagnostic_status: str) -> None:
    STUCK_WORKFLOW_DIAGNOSTICS_TOTAL.labels(
        workflow_type=workflow_type,
        diagnostic_status=diagnostic_status,
    ).inc()


def render_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
