from typing import Any

import httpx
from pydantic import BaseModel, Field

from aegisflow_agent_runtime.schemas import AgentExecutionRequest


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
            return None

        invocation_request = {
            "workflow_id": request.workflow_id,
            "correlation_id": request.correlation_id,
            "agent_id": agent_id,
            "agent_execution_id": agent_execution_id,
            "idempotency_key": f"{request.workflow_id}:{agent_id}:{tool_id}",
            "input": input_payload,
        }
        try:
            with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
                response = client.post(f"/api/v1/tools/{tool_id}/invocations", json=invocation_request)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ToolRuntimeError(f"Tool runtime invocation failed for {tool_id}: {exc}") from exc

        return ToolInvocationContext.model_validate(response.json())
