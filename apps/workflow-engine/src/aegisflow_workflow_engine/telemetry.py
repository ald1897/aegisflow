from collections.abc import MutableMapping
from contextlib import contextmanager
from functools import wraps
from time import perf_counter
from typing import Any, Callable

from opentelemetry import propagate, trace
from opentelemetry.context import attach, detach
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

from aegisflow_workflow_engine.config import Settings
from aegisflow_workflow_engine.metrics import record_activity_execution

_configured = False


def configure_telemetry(settings: Settings) -> None:
    global _configured
    if _configured or not settings.enable_telemetry:
        return

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=_traces_endpoint(settings.otel_exporter_otlp_endpoint))
        )
    )
    trace.set_tracer_provider(provider)
    _configured = True


def inject_trace_context(headers: MutableMapping[str, str] | None = None) -> dict[str, str]:
    carrier = dict(headers or {})
    propagate.inject(carrier)
    return carrier


def instrument_activity(activity_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(payload: dict, *args: Any, **kwargs: Any) -> Any:
            start_time = perf_counter()
            status = "completed"
            with activity_span(activity_name, payload) as span:
                try:
                    result = await func(payload, *args, **kwargs)
                    if isinstance(result, dict) and result.get("idempotent"):
                        status = "idempotent"
                        span.set_attribute("idempotent", True)
                    return result
                except Exception as exc:
                    status = "failed"
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    raise
                finally:
                    record_activity_execution(
                        activity_name=activity_name,
                        status=status,
                        duration_seconds=perf_counter() - start_time,
                    )

        return wrapper

    return decorator


@contextmanager
def activity_span(activity_name: str, payload: dict) -> Any:
    token = attach(propagate.extract(payload.get("trace_context", {})))
    tracer = trace.get_tracer(__name__)
    try:
        with tracer.start_as_current_span(
            f"workflow_engine.activity.{activity_name}",
            kind=SpanKind.INTERNAL,
        ) as span:
            _set_payload_attributes(span, payload)
            span.set_attribute("temporal.activity", activity_name)
            yield span
    finally:
        detach(token)


def set_span_attributes(attributes: dict[str, str | int | float | bool | None]) -> None:
    span = trace.get_current_span()
    if not span.is_recording():
        return
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


def _traces_endpoint(base_endpoint: str) -> str:
    return f"{base_endpoint.rstrip('/')}/v1/traces"


def _set_payload_attributes(span: Span, payload: dict) -> None:
    for key in (
        "workflow_id",
        "correlation_id",
        "agent_id",
        "tool_id",
        "approval_id",
        "target_state",
        "decision",
    ):
        value = payload.get(key)
        if value is not None:
            span.set_attribute(key, str(value))
