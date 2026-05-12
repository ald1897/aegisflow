import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from aegisflow_evaluation_service.config import Settings

_log_context: ContextVar[dict[str, str]] = ContextVar("evaluation_service_log_context", default={})

EXTRA_FIELDS = {
    "correlation_id",
    "dataset_id",
    "evaluation_mode",
    "evaluation_run_id",
    "evaluation_scope",
    "evaluator_id",
    "operation",
    "result_count",
    "route",
    "score_name",
    "score_status",
    "severity",
    "status",
    "workflow_id",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service_name: str, environment: str) -> None:
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "environment": self.environment,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_log_context.get())
        trace_id = _current_trace_id()
        if trace_id:
            payload["trace_id"] = trace_id
        for field in EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service_name=settings.service_name, environment=settings.environment))
    root_logger.addHandler(handler)


@contextmanager
def bind_log_context(**context: str | None):
    current = _log_context.get()
    filtered = {key: str(value) for key, value in context.items() if value is not None}
    token = _log_context.set(current | filtered)
    try:
        yield
    finally:
        _log_context.reset(token)


def _current_trace_id() -> str | None:
    from aegisflow_evaluation_service.telemetry import current_trace_id

    return current_trace_id()
