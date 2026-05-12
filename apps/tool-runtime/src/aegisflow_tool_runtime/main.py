import logging

from fastapi import Depends, FastAPI, HTTPException, status

from aegisflow_tool_runtime.config import Settings, get_settings
from aegisflow_tool_runtime.schemas import (
    ToolInvocationRequest,
    ToolInvocationResponse,
    ToolRegistryResponse,
)
from aegisflow_tool_runtime.tools import (
    ToolInputValidationError,
    ToolNotFoundError,
    ToolPermissionDeniedError,
    ToolRuntime,
)


def get_tool_runtime() -> ToolRuntime:
    return ToolRuntime()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    app = FastAPI(title="AegisFlow Tool Runtime", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.service_name,
            "environment": settings.environment,
        }

    @app.get("/ready")
    async def ready(runtime: ToolRuntime = Depends(get_tool_runtime)) -> dict[str, object]:
        tools = runtime.list_tools()
        return {
            "status": "ok",
            "service": settings.service_name,
            "checks": {
                "tool_registry": "ok",
                "schema_validation": "ok",
            },
            "registered_tools": len(tools),
        }

    @app.get("/api/v1/tools", response_model=ToolRegistryResponse)
    async def list_tools(runtime: ToolRuntime = Depends(get_tool_runtime)) -> ToolRegistryResponse:
        return ToolRegistryResponse(tools=runtime.list_tools())

    @app.post(
        "/api/v1/tools/{tool_id}/invocations",
        response_model=ToolInvocationResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def invoke_tool(
        tool_id: str,
        payload: ToolInvocationRequest,
        runtime: ToolRuntime = Depends(get_tool_runtime),
    ) -> ToolInvocationResponse:
        try:
            return runtime.invoke(tool_id, payload)
        except ToolNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool_not_found") from exc
        except ToolPermissionDeniedError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except ToolInputValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


app = create_app()
