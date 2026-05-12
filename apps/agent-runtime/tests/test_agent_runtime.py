from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from aegisflow_agent_runtime.agents import AgentRuntime
from aegisflow_agent_runtime.config import get_settings
from aegisflow_agent_runtime.main import create_app
from aegisflow_agent_runtime.prompts import PromptRegistry
from aegisflow_agent_runtime.schemas import AgentExecutionRequest
from aegisflow_agent_runtime.tools import ToolInvocationContext


@pytest.fixture(autouse=True)
def configure_prompt_path(monkeypatch: pytest.MonkeyPatch) -> None:
    app_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PROMPTS_PATH", str(app_root / "prompts"))
    monkeypatch.setenv("ENABLE_TOOL_RUNTIME", "false")
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
    intake = next(agent for agent in response.json()["agents"] if agent["agent_id"] == "intake_agent")
    document = next(agent for agent in response.json()["agents"] if agent["agent_id"] == "document_analysis_agent")
    assert intake["allowed_tools"] == ["borrower_profile_lookup"]
    assert document["allowed_tools"] == ["document_fetch"]


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


def test_intake_agent_invokes_approved_borrower_profile_tool() -> None:
    runtime = AgentRuntime(PromptRegistry(Path(get_settings().prompts_path)), FakeToolClient())

    response = runtime.execute(
        "intake_agent",
        AgentExecutionRequest(
            workflow_id="workflow-1",
            correlation_id="correlation-1",
            workflow_type="MORTGAGE_EXCEPTION_REVIEW",
            workflow_state="INTAKE_IN_PROGRESS",
            priority="HIGH",
            metadata={"case_reference": "MORT-123", "channel": "api"},
        ),
    )

    assert response.output["recommended_next_state"] == "DOCUMENT_ANALYSIS_PENDING"
    assert response.telemetry["tool_invocations"][0]["tool_id"] == "borrower_profile_lookup"
    assert "Governed borrower profile context" in response.output["summary"]


def test_document_analysis_agent_uses_governed_document_metadata() -> None:
    runtime = AgentRuntime(PromptRegistry(Path(get_settings().prompts_path)), FakeToolClient())

    response = runtime.execute(
        "document_analysis_agent",
        AgentExecutionRequest(
            workflow_id="workflow-1",
            correlation_id="correlation-1",
            workflow_type="MORTGAGE_EXCEPTION_REVIEW",
            workflow_state="DOCUMENT_ANALYSIS_PENDING",
            priority="HIGH",
            metadata={"case_reference": "MORT-123"},
        ),
    )

    assert response.output["document_status"] == "COMPLETE"
    assert response.output["missing_documents"] == []
    assert response.telemetry["tool_invocations"][0]["tool_id"] == "document_fetch"
    assert response.requires_human_review is True


class FakeToolClient:
    def invoke(self, *, tool_id: str, agent_id: str, agent_execution_id: str, request, input_payload):
        del agent_id, request, input_payload
        if tool_id == "borrower_profile_lookup":
            output = {
                "profile_status": "FOUND",
                "profile_completeness": "COMPLETE",
            }
        else:
            output = {
                "available_document_types": ["income_verification", "exception_rationale"],
                "missing_document_types": [],
            }
        return ToolInvocationContext(
            tool_invocation_id=f"{agent_execution_id}:{tool_id}",
            tool_id=tool_id,
            status="COMPLETED",
            permission_status="AUTHORIZED",
            input_validation_status="VALIDATED",
            output_validation_status="VALIDATED",
            output=output,
            telemetry={"replay_safe": True, "data_classification": "Confidential"},
        )
