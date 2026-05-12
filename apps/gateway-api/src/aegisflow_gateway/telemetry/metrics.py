from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

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


def render_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
