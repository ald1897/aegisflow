from collections.abc import MutableMapping

from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from aegisflow_tool_runtime.config import Settings

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


def _traces_endpoint(base_endpoint: str) -> str:
    return f"{base_endpoint.rstrip('/')}/v1/traces"
