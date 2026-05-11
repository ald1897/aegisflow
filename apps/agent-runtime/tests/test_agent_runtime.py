from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from aegisflow_agent_runtime.config import get_settings
from aegisflow_agent_runtime.main import create_app


@pytest.fixture(autouse=True)
def configure_prompt_path(monkeypatch: pytest.MonkeyPatch) -> None:
    app_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PROMPTS_PATH", str(app_root / "prompts"))
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


def test_prompt_assets_exist() -> None:
    app_root = Path(__file__).resolve().parents[1]
    assert (app_root / "prompts/intake-agent.v1.md").exists()
    assert (app_root / "prompts/document-analysis-agent.v1.md").exists()


async def test_list_agents_returns_registered_agents(client: AsyncClient) -> None:
    response = await client.get("/api/v1/agents")

    assert response.status_code == 200
    agent_ids = {agent["agent_id"] for agent in response.json()["agents"]}
    assert agent_ids == {"intake_agent", "document_analysis_agent"}


async def test_intake_agent_returns_validated_output(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/agents/intake_agent/executions",
        json={
            "workflow_id": "workflow-1",
            "correlation_id": "correlation-1",
            "workflow_type": "MORTGAGE_EXCEPTION_REVIEW",
            "workflow_state": "INTAKE_IN_PROGRESS",
            "priority": "HIGH",
            "metadata": {"case_reference": "MORT-123", "channel": "api"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["validation_status"] == "VALIDATED"
    assert body["prompt_id"] == "intake-agent"
    assert body["output"]["recommended_next_state"] == "DOCUMENT_ANALYSIS_PENDING"


async def test_document_analysis_agent_preserves_human_review(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/agents/document_analysis_agent/executions",
        json={
            "workflow_id": "workflow-1",
            "correlation_id": "correlation-1",
            "workflow_type": "MORTGAGE_EXCEPTION_REVIEW",
            "workflow_state": "DOCUMENT_ANALYSIS_PENDING",
            "priority": "HIGH",
            "metadata": {"case_reference": "MORT-123"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["requires_human_review"] is True
    assert body["output"]["document_status"] == "INCOMPLETE"
    assert body["output"]["recommended_next_state"] == "RISK_REVIEW_PENDING"


async def test_agent_rejects_unsupported_workflow_state(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/agents/intake_agent/executions",
        json={
            "workflow_id": "workflow-1",
            "correlation_id": "correlation-1",
            "workflow_type": "MORTGAGE_EXCEPTION_REVIEW",
            "workflow_state": "RISK_REVIEW_PENDING",
            "priority": "HIGH",
            "metadata": {},
        },
    )

    assert response.status_code == 409
