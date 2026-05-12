from time import perf_counter

from opentelemetry import propagate, trace
from opentelemetry.context import attach, detach
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aegisflow_evaluation_service.config import Settings
from aegisflow_evaluation_service.logging import bind_log_context
from aegisflow_evaluation_service.metrics import record_http_request

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


def current_trace_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return f"{span_context.trace_id:032x}"


def _traces_endpoint(base_endpoint: str) -> str:
    return f"{base_endpoint.rstrip('/')}/v1/traces"


class EvaluationServiceTelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        context = propagate.extract(dict(request.headers))
        token = attach(context)
        route = "unmatched"
        status_code = 500
        start_time = perf_counter()
        try:
            tracer = trace.get_tracer(__name__)
            with bind_log_context(
                correlation_id=request.headers.get("X-Correlation-ID"),
                route=request.url.path,
            ):
                with tracer.start_as_current_span(
                    f"{request.method} {request.url.path}",
                    kind=SpanKind.SERVER,
                ) as span:
                    _set_request_span_attributes(span, request)
                    response = await call_next(request)
                    status_code = response.status_code
                    route = _route_path(request)
                    span.update_name(f"{request.method} {route}")
                    span.set_attribute("http.route", route)
                    span.set_attribute("http.status_code", status_code)
                    if status_code >= 500:
                        span.set_status(Status(StatusCode.ERROR))
                    return response
        except Exception as exc:
            span = trace.get_current_span()
            if span.is_recording():
                route = _route_path(request)
                span.set_attribute("http.route", route)
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            record_http_request(
                method=request.method,
                route=route,
                status_code=status_code,
                duration_seconds=perf_counter() - start_time,
            )
            detach(token)


def _set_request_span_attributes(span: Span, request: Request) -> None:
    span.set_attribute("http.method", request.method)
    span.set_attribute("url.path", request.url.path)
    span.set_attribute("http.scheme", request.url.scheme)
    span.set_attribute("network.protocol.version", request.scope.get("http_version", "unknown"))


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path or "unmatched"
