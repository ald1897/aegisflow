from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "aegisflow_evaluation_service_http_requests_total",
    "Evaluation service HTTP requests.",
    ("method", "route", "status_class"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "aegisflow_evaluation_service_http_request_duration_seconds",
    "Evaluation service HTTP request duration.",
    ("method", "route", "status_class"),
)
HTTP_ERRORS_TOTAL = Counter(
    "aegisflow_evaluation_service_http_errors_total",
    "Evaluation service HTTP error responses.",
    ("method", "route", "status_class"),
)
SERVICE_STARTUPS_TOTAL = Counter(
    "aegisflow_evaluation_service_startups_total",
    "Evaluation service application startup count.",
    ("service", "environment"),
)


def record_http_request(*, method: str, route: str, status_code: int, duration_seconds: float) -> None:
    status_class = f"{status_code // 100}xx"
    labels = {"method": method, "route": route, "status_class": status_class}
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_seconds)
    if status_code >= 400:
        HTTP_ERRORS_TOTAL.labels(**labels).inc()


def record_service_startup(*, service: str, environment: str) -> None:
    SERVICE_STARTUPS_TOTAL.labels(service=service, environment=environment).inc()


def render_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
