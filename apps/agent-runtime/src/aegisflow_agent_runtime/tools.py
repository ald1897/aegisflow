from typing import Any
from time import perf_counter

import httpx
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from pydantic import BaseModel, Field

from aegisflow_agent_runtime.metrics import record_tool_client_invocation
from aegisflow_agent_runtime.schemas import AgentExecutionRequest
from aegisflow_agent_runtime.telemetry import inject_trace_context


class ToolRuntimeError(Exception):
    pass


class ToolInvocationContext(BaseModel):
    tool_invocation_id: str
    tool_id: str
    status: str
    permission_status: str
    input_validation_status: str
    output_validation_status: str
    output: dict[str, Any]
    telemetry: dict[str, Any] = Field(default_factory=dict)


class ToolRuntimeClient:
    def __init__(self, base_url: str, *, enabled: bool) -> None:
        self.base_url = base_url
        self.enabled = enabled

    def invoke(
        self,
        *,
        tool_id: str,
        agent_id: str,
        agent_execution_id: str,
        request: AgentExecutionRequest,
        input_payload: dict[str, Any],
    ) -> ToolInvocationContext | None:
        if not self.enabled:
            record_tool_client_invocation(
                agent_id=agent_id,
                tool_id=tool_id,
                status="disabled",
                duration_seconds=0.0,
            )
            return None

        start_time = perf_counter()
        invocation_request = {
            "workflow_id": request.workflow_id,
            "correlation_id": request.correlation_id,
            "agent_id": agent_id,
            "agent_execution_id": agent_execution_id,
            "idempotency_key": f"{request.workflow_id}:{agent_id}:{tool_id}",
            "input": input_payload,
        }
        status = "completed"
        try:
            with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
                with trace.get_tracer(__name__).start_as_current_span(
                    "agent_runtime.http.invoke_tool_runtime",
                    kind=SpanKind.CLIENT,
                ) as span:
                    span.set_attribute("workflow_id", request.workflow_id)
                    span.set_attribute("correlation_id", request.correlation_id)
                    span.set_attribute("agent_id", agent_id)
                    span.set_attribute("agent_execution_id", agent_execution_id)
                    span.set_attribute("tool_id", tool_id)
                    span.set_attribute("http.method", "POST")
                    span.set_attribute("http.route", "/api/v1/tools/{tool_id}/invocations")
                    response = client.post(
                        f"/api/v1/tools/{tool_id}/invocations",
                        headers=inject_trace_context({"X-Correlation-ID": request.correlation_id}),
                        json=invocation_request,
                    )
                    span.set_attribute("http.status_code", response.status_code)
                    if response.status_code >= 400:
                        span.set_status(Status(StatusCode.ERROR))
                    response.raise_for_status()
        except httpx.HTTPError as exc:
            status = "failed"
            span = trace.get_current_span()
            if span.is_recording():
                span.set_status(Status(StatusCode.ERROR))
            raise ToolRuntimeError(f"Tool runtime invocation failed for {tool_id}: {exc}") from exc
        finally:
            record_tool_client_invocation(
                agent_id=agent_id,
                tool_id=tool_id,
                status=status,
                duration_seconds=perf_counter() - start_time,
            )

        return ToolInvocationContext.model_validate(response.json())
