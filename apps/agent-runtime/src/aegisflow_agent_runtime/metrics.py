from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "aegisflow_agent_runtime_http_requests_total",
    "Agent runtime HTTP requests.",
    ("method", "route", "status_class"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "aegisflow_agent_runtime_http_request_duration_seconds",
    "Agent runtime HTTP request duration.",
    ("method", "route", "status_class"),
)
HTTP_ERRORS_TOTAL = Counter(
    "aegisflow_agent_runtime_http_errors_total",
    "Agent runtime HTTP error responses.",
    ("method", "route", "status_class"),
)

AGENT_EXECUTIONS_TOTAL = Counter(
    "aegisflow_agent_runtime_agent_executions_total",
    "Agent execution attempts.",
    ("agent_id", "status", "validation_status", "requires_human_review"),
)
AGENT_EXECUTION_DURATION_SECONDS = Histogram(
    "aegisflow_agent_runtime_agent_execution_duration_seconds",
    "Agent execution duration.",
    ("agent_id", "status"),
)

AGENT_GRAPH_STEPS_TOTAL = Counter(
    "aegisflow_agent_runtime_graph_steps_total",
    "Agent graph step executions.",
    ("agent_id", "step", "status"),
)
AGENT_GRAPH_STEP_DURATION_SECONDS = Histogram(
    "aegisflow_agent_runtime_graph_step_duration_seconds",
    "Agent graph step duration.",
    ("agent_id", "step", "status"),
)

TOOL_CLIENT_INVOCATIONS_TOTAL = Counter(
    "aegisflow_agent_runtime_tool_client_invocations_total",
    "Tool runtime client invocation attempts from agent-runtime.",
    ("agent_id", "tool_id", "status"),
)
TOOL_CLIENT_INVOCATION_DURATION_SECONDS = Histogram(
    "aegisflow_agent_runtime_tool_client_invocation_duration_seconds",
    "Tool runtime client invocation duration from agent-runtime.",
    ("agent_id", "tool_id", "status"),
)


def record_http_request(*, method: str, route: str, status_code: int, duration_seconds: float) -> None:
    status_class = f"{status_code // 100}xx"
    labels = {"method": method, "route": route, "status_class": status_class}
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_seconds)
    if status_code >= 400:
        HTTP_ERRORS_TOTAL.labels(**labels).inc()


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


def record_graph_step(*, agent_id: str, step: str, status: str, duration_seconds: float) -> None:
    labels = {"agent_id": agent_id, "step": step, "status": status}
    AGENT_GRAPH_STEPS_TOTAL.labels(**labels).inc()
    AGENT_GRAPH_STEP_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def record_tool_client_invocation(
    *,
    agent_id: str,
    tool_id: str,
    status: str,
    duration_seconds: float,
) -> None:
    labels = {"agent_id": agent_id, "tool_id": tool_id, "status": status}
    TOOL_CLIENT_INVOCATIONS_TOTAL.labels(**labels).inc()
    TOOL_CLIENT_INVOCATION_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def render_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
