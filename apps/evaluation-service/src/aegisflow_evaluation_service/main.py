import logging
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_evaluation_service.config import get_settings
from aegisflow_evaluation_service.database import check_database, get_session
from aegisflow_evaluation_service.logging import configure_logging
from aegisflow_evaluation_service.metrics import record_service_startup, render_prometheus_metrics
from aegisflow_evaluation_service.repository import EvaluationRepository
from aegisflow_evaluation_service.schemas import (
    EvaluationDatasetCaseRead,
    EvaluationDatasetSummary,
    EvaluationRunDetail,
    EvaluationRunRequest,
    EvaluationRunSummary,
)
from aegisflow_evaluation_service.services import (
    DatasetCaseNotFoundError,
    EvaluationOrchestrationError,
    EvaluationRunService,
    WorkflowNotFoundError,
    WorkflowNotReadyForEvaluationError,
)
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

    @app.post(
        "/api/v1/evaluations/workflows/{workflow_id}/runs",
        response_model=EvaluationRunDetail,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_workflow_evaluation_run(
        workflow_id: UUID,
        payload: EvaluationRunRequest,
        session: AsyncSession = Depends(get_session),
        actor_id: str | None = Header(default=None, alias="X-Actor-ID"),
    ) -> EvaluationRunDetail:
        service = EvaluationRunService(EvaluationRepository(session), judge_settings=settings)
        try:
            detail = await service.create_workflow_run(
                workflow_id,
                payload,
                created_by=actor_id or "evaluation-service",
            )
            await session.commit()
            return detail
        except EvaluationOrchestrationError as exc:
            await session.rollback()
            raise _evaluation_http_error(exc) from exc

    @app.get("/api/v1/evaluations/runs/{evaluation_run_id}", response_model=EvaluationRunDetail)
    async def get_evaluation_run(
        evaluation_run_id: UUID,
        session: AsyncSession = Depends(get_session),
    ) -> EvaluationRunDetail:
        service = EvaluationRunService(EvaluationRepository(session), judge_settings=settings)
        detail = await service.get_run_detail(evaluation_run_id)
        if detail is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "evaluation_run_not_found"})
        return detail

    @app.get("/api/v1/evaluations/workflows/{workflow_id}/runs", response_model=list[EvaluationRunSummary])
    async def list_workflow_evaluation_runs(
        workflow_id: UUID,
        session: AsyncSession = Depends(get_session),
    ) -> list[EvaluationRunSummary]:
        service = EvaluationRunService(EvaluationRepository(session), judge_settings=settings)
        try:
            return await service.list_workflow_runs(workflow_id)
        except EvaluationOrchestrationError as exc:
            raise _evaluation_http_error(exc) from exc

    @app.get("/api/v1/evaluations/datasets", response_model=list[EvaluationDatasetSummary])
    async def list_evaluation_datasets(
        session: AsyncSession = Depends(get_session),
    ) -> list[EvaluationDatasetSummary]:
        service = EvaluationRunService(EvaluationRepository(session), judge_settings=settings)
        datasets = await service.list_datasets()
        await session.commit()
        return datasets

    @app.get("/api/v1/evaluations/datasets/{dataset_id}/cases", response_model=list[EvaluationDatasetCaseRead])
    async def list_evaluation_dataset_cases(
        dataset_id: str,
        session: AsyncSession = Depends(get_session),
    ) -> list[EvaluationDatasetCaseRead]:
        service = EvaluationRunService(EvaluationRepository(session), judge_settings=settings)
        cases = await service.list_dataset_cases(dataset_id)
        await session.commit()
        return cases

    return app


def _evaluation_http_error(exc: EvaluationOrchestrationError) -> HTTPException:
    if isinstance(exc, WorkflowNotFoundError | DatasetCaseNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, WorkflowNotReadyForEvaluationError):
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail={"error": exc.error_code, "message": exc.message})


app = create_app()
