import logging

from fastapi import FastAPI, HTTPException, Response, status

from aegisflow_evaluation_service.config import get_settings
from aegisflow_evaluation_service.database import check_database
from aegisflow_evaluation_service.logging import configure_logging
from aegisflow_evaluation_service.metrics import record_service_startup, render_prometheus_metrics
from aegisflow_evaluation_service.telemetry import (
    EvaluationServiceTelemetryMiddleware,
    configure_telemetry,
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    configure_telemetry(settings)
    record_service_startup(service=settings.service_name, environment=settings.environment)
    logger.info("evaluation service configured", extra={"operation": "service_startup", "status": "configured"})

    app = FastAPI(title="AegisFlow Evaluation Service", version="0.1.0")
    app.add_middleware(EvaluationServiceTelemetryMiddleware)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.service_name,
            "environment": settings.environment,
        }

    @app.get("/ready")
    async def ready() -> dict[str, object]:
        try:
            await check_database()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database_unavailable",
            ) from exc
        return {
            "status": "ok",
            "service": settings.service_name,
            "checks": {
                "database": "ok",
                "evaluation_registry": "ok",
            },
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        content, media_type = render_prometheus_metrics()
        return Response(content=content, media_type=media_type)

    return app


app = create_app()
