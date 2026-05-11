from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from aegisflow_gateway.api.routes import router
from aegisflow_gateway.api.schemas import ErrorResponse
from aegisflow_gateway.config import get_settings
from aegisflow_gateway.services.workflows import WorkflowNotFoundError
from aegisflow_gateway.telemetry.correlation import CorrelationIdMiddleware
from aegisflow_gateway.telemetry.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title=settings.api_title, version=settings.api_version)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(router)

    @app.exception_handler(WorkflowNotFoundError)
    async def workflow_not_found_handler(request: Request, exc: WorkflowNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="workflow_not_found",
                message=str(exc),
                correlation_id=getattr(request.state, "correlation_id", None),
            ).model_dump(),
        )

    return app


app = create_app()
