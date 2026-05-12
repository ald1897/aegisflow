from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from aegisflow_evaluation_service.config import get_settings
from aegisflow_evaluation_service.database import dispose_engine
from aegisflow_evaluation_service.main import create_app


@pytest.fixture(autouse=True)
async def configure_test_settings(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite://")
    monkeypatch.setenv("ENABLE_TELEMETRY", "false")
    get_settings.cache_clear()
    await dispose_engine()
    yield
    get_settings.cache_clear()
    await dispose_engine()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


async def test_health_returns_service_status(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "evaluation-service",
        "environment": "local",
    }


async def test_ready_checks_database(client: AsyncClient) -> None:
    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"
    assert response.json()["checks"]["evaluation_registry"] == "ok"


async def test_metrics_endpoint_exposes_evaluation_service_metrics(client: AsyncClient) -> None:
    await client.get("/health")

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "aegisflow_evaluation_service_http_requests_total" in response.text
    assert "aegisflow_evaluation_service_startups_total" in response.text
    assert "aegisflow_evaluation_service_evaluation_runs_total" in response.text
    assert "aegisflow_evaluation_service_evaluation_results_total" in response.text
    assert "aegisflow_evaluation_service_hallucination_signals_total" in response.text
    assert "aegisflow_evaluation_service_prompt_regression_results_total" in response.text
