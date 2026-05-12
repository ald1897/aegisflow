from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from aegisflow_gateway.api.routes import router
from aegisflow_gateway.api.schemas import ErrorResponse
from aegisflow_gateway.config import get_settings
from aegisflow_gateway.services.workflows import WorkflowNotFoundError, WorkflowReviewActionError
from aegisflow_gateway.telemetry.correlation import CorrelationIdMiddleware
from aegisflow_gateway.telemetry.logging import configure_logging
from aegisflow_gateway.telemetry.tracing import configure_telemetry


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    configure_telemetry(settings)

    app = FastAPI(title=settings.api_title, version=settings.api_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Actor-ID", "X-Correlation-ID"],
    )
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

    @app.exception_handler(WorkflowReviewActionError)
    async def workflow_review_action_handler(request: Request, exc: WorkflowReviewActionError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=exc.error,
                message=exc.message,
                correlation_id=getattr(request.state, "correlation_id", None),
            ).model_dump(),
        )

    return app


app = create_app()
