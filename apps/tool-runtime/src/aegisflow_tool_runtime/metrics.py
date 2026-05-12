from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "aegisflow_tool_runtime_http_requests_total",
    "Tool runtime HTTP requests.",
    ("method", "route", "status_class"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "aegisflow_tool_runtime_http_request_duration_seconds",
    "Tool runtime HTTP request duration.",
    ("method", "route", "status_class"),
)
HTTP_ERRORS_TOTAL = Counter(
    "aegisflow_tool_runtime_http_errors_total",
    "Tool runtime HTTP error responses.",
    ("method", "route", "status_class"),
)

TOOL_INVOCATIONS_TOTAL = Counter(
    "aegisflow_tool_runtime_tool_invocations_total",
    "Tool invocation attempts.",
    ("tool_id", "status", "permission_status", "input_validation_status", "output_validation_status"),
)
TOOL_INVOCATION_DURATION_SECONDS = Histogram(
    "aegisflow_tool_runtime_tool_invocation_duration_seconds",
    "Tool invocation duration.",
    ("tool_id", "status"),
)
TOOL_HANDLER_DURATION_SECONDS = Histogram(
    "aegisflow_tool_runtime_handler_duration_seconds",
    "Deterministic tool handler duration.",
    ("tool_id", "status"),
)


def record_http_request(*, method: str, route: str, status_code: int, duration_seconds: float) -> None:
    status_class = f"{status_code // 100}xx"
    labels = {"method": method, "route": route, "status_class": status_class}
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_seconds)
    if status_code >= 400:
        HTTP_ERRORS_TOTAL.labels(**labels).inc()


def record_tool_invocation(
    *,
    tool_id: str,
    status: str,
    permission_status: str,
    input_validation_status: str,
    output_validation_status: str,
    duration_seconds: float,
) -> None:
    TOOL_INVOCATIONS_TOTAL.labels(
        tool_id=tool_id,
        status=status,
        permission_status=permission_status,
        input_validation_status=input_validation_status,
        output_validation_status=output_validation_status,
    ).inc()
    TOOL_INVOCATION_DURATION_SECONDS.labels(tool_id=tool_id, status=status).observe(duration_seconds)


def record_tool_handler_duration(*, tool_id: str, status: str, duration_seconds: float) -> None:
    TOOL_HANDLER_DURATION_SECONDS.labels(tool_id=tool_id, status=status).observe(duration_seconds)


def render_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
