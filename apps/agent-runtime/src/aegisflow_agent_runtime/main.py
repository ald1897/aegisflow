import logging

from fastapi import Depends, FastAPI, HTTPException, status

from aegisflow_agent_runtime.agents import (
    AgentNotFoundError,
    AgentRuntime,
    UnsupportedWorkflowStateError,
)
from aegisflow_agent_runtime.config import Settings, get_settings
from aegisflow_agent_runtime.prompts import PromptRegistry
from aegisflow_agent_runtime.schemas import (
    AgentExecutionRequest,
    AgentExecutionResponse,
    AgentRegistryResponse,
)
from aegisflow_agent_runtime.tools import ToolRuntimeClient


def get_agent_runtime(settings: Settings = Depends(get_settings)) -> AgentRuntime:
    return AgentRuntime(
        PromptRegistry(settings.prompts_path),
        ToolRuntimeClient(settings.tool_runtime_url, enabled=settings.enable_tool_runtime),
    )


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    app = FastAPI(title="AegisFlow Agent Runtime", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.service_name,
            "environment": settings.environment,
        }

    @app.get("/ready")
    async def ready(runtime: AgentRuntime = Depends(get_agent_runtime)) -> dict[str, object]:
        agents = runtime.list_agents()
        return {
            "status": "ok",
            "service": settings.service_name,
            "checks": {
                "agent_registry": "ok",
                "prompt_registry": "ok",
            },
            "registered_agents": len(agents),
        }

    @app.get("/api/v1/agents", response_model=AgentRegistryResponse)
    async def list_agents(runtime: AgentRuntime = Depends(get_agent_runtime)) -> AgentRegistryResponse:
        return AgentRegistryResponse(agents=runtime.list_agents())

    @app.post(
        "/api/v1/agents/{agent_id}/executions",
        response_model=AgentExecutionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def execute_agent(
        agent_id: str,
        payload: AgentExecutionRequest,
        runtime: AgentRuntime = Depends(get_agent_runtime),
    ) -> AgentExecutionResponse:
        try:
            return runtime.execute(agent_id, payload)
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_not_found") from exc
        except UnsupportedWorkflowStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return app


app = create_app()
