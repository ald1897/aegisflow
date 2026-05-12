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
EVALUATION_RUNS_TOTAL = Counter(
    "aegisflow_evaluation_service_evaluation_runs_total",
    "Evaluation runs created or failed by scope, mode, and status.",
    ("evaluation_scope", "evaluation_mode", "status"),
)
EVALUATION_RUN_DURATION_SECONDS = Histogram(
    "aegisflow_evaluation_service_evaluation_run_duration_seconds",
    "Evaluation run orchestration duration.",
    ("evaluation_scope", "evaluation_mode", "status"),
)
EVALUATION_RESULTS_TOTAL = Counter(
    "aegisflow_evaluation_service_evaluation_results_total",
    "Evaluation results persisted by evaluator, score, status, and severity.",
    ("evaluator_id", "score_name", "score_status", "severity"),
)
HALLUCINATION_SIGNALS_TOTAL = Counter(
    "aegisflow_evaluation_service_hallucination_signals_total",
    "Evidence-consistency hallucination-like signals by severity.",
    ("severity",),
)
PROMPT_REGRESSION_RESULTS_TOTAL = Counter(
    "aegisflow_evaluation_service_prompt_regression_results_total",
    "Prompt-attributed evaluation results by prompt identifier, version, and status.",
    ("prompt_id", "prompt_version", "status"),
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


def record_evaluation_run(
    *,
    evaluation_scope: str,
    evaluation_mode: str,
    status: str,
    duration_seconds: float,
) -> None:
    labels = {
        "evaluation_scope": evaluation_scope,
        "evaluation_mode": evaluation_mode,
        "status": status,
    }
    EVALUATION_RUNS_TOTAL.labels(**labels).inc()
    EVALUATION_RUN_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def record_evaluation_result(
    *,
    evaluator_id: str,
    score_name: str,
    score_status: str,
    severity: str,
    prompt_id: str | None = None,
    prompt_version: str | None = None,
) -> None:
    EVALUATION_RESULTS_TOTAL.labels(
        evaluator_id=evaluator_id,
        score_name=score_name,
        score_status=score_status,
        severity=severity,
    ).inc()
    if evaluator_id == "evidence-consistency-signals" and score_status in {"WARN", "FAIL"}:
        HALLUCINATION_SIGNALS_TOTAL.labels(severity=severity).inc()
    if prompt_id and prompt_version:
        PROMPT_REGRESSION_RESULTS_TOTAL.labels(
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            status=score_status,
        ).inc()


def render_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
