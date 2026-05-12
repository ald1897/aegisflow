from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from aegisflow_tool_runtime.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


async def test_health_returns_service_status(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "tool-runtime"


async def test_list_tools_returns_registered_tools(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tools")

    assert response.status_code == 200
    tool_ids = {tool["tool_id"] for tool in response.json()["tools"]}
    assert tool_ids == {
        "borrower_profile_lookup",
        "document_fetch",
        "fraud_signal_lookup",
    }


async def test_borrower_profile_lookup_returns_validated_output(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/tools/borrower_profile_lookup/invocations",
        json={
            "workflow_id": "workflow-1",
            "correlation_id": "correlation-1",
            "agent_id": "intake_agent",
            "agent_execution_id": "agent-execution-1",
            "idempotency_key": "workflow-1:intake:borrower",
            "input": {
                "workflow_id": "workflow-1",
                "correlation_id": "correlation-1",
                "case_reference": "MORT-123",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["permission_status"] == "AUTHORIZED"
    assert body["input_validation_status"] == "VALIDATED"
    assert body["output_validation_status"] == "VALIDATED"
    assert body["output"]["masked_borrower_reference"].startswith("BRW-***-")


async def test_document_fetch_does_not_return_raw_document_content(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/tools/document_fetch/invocations",
        json={
            "workflow_id": "workflow-1",
            "correlation_id": "correlation-1",
            "agent_id": "document_analysis_agent",
            "input": {
                "workflow_id": "workflow-1",
                "correlation_id": "correlation-1",
                "case_reference": "MORT-123",
                "requested_document_types": ["income_verification", "credit_report"],
            },
        },
    )

    assert response.status_code == 201
    output = response.json()["output"]
    assert "income_verification" in output["available_document_types"]
    assert "credit_report" in output["missing_document_types"]
    assert "raw" not in output


async def test_unauthorized_agent_cannot_invoke_tool(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/tools/borrower_profile_lookup/invocations",
        json={
            "workflow_id": "workflow-1",
            "correlation_id": "correlation-1",
            "agent_id": "document_analysis_agent",
            "input": {
                "workflow_id": "workflow-1",
                "correlation_id": "correlation-1",
                "case_reference": "MORT-123",
            },
        },
    )

    assert response.status_code == 403


async def test_invalid_tool_input_returns_structured_error(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/tools/document_fetch/invocations",
        json={
            "workflow_id": "workflow-1",
            "correlation_id": "correlation-1",
            "agent_id": "document_analysis_agent",
            "input": {
                "workflow_id": "workflow-1",
                "correlation_id": "correlation-1",
                "case_reference": "MORT-123",
                "requested_document_types": [],
            },
        },
    )

    assert response.status_code == 422


async def test_unregistered_tool_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/tools/unrestricted_shell/invocations",
        json={
            "workflow_id": "workflow-1",
            "correlation_id": "correlation-1",
            "agent_id": "intake_agent",
            "input": {},
        },
    )

    assert response.status_code == 404
