import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from aegisflow_workflow_engine.config import get_settings
from aegisflow_workflow_engine.domain import (
    OutboxPublishStatus,
    TimelineEntryType,
    WorkflowEventType,
)
from aegisflow_workflow_engine.persistence.database import SessionLocal
from aegisflow_workflow_engine.persistence.models import (
    AgentExecutionRecord,
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowTimelineEntry,
)
from aegisflow_workflow_engine.activities.state_transitions import publish_workflow_event
from aegisflow_workflow_engine.activities.tools import record_tool_invocation

logger = logging.getLogger(__name__)


@activity.defn(name="execute_agent")
async def execute_agent(payload: dict) -> dict:
    agent_id = payload["agent_id"]
    workflow_id = payload["workflow_id"]
    correlation_id = payload["correlation_id"]
    workflow_state = payload["workflow_state"]
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        result = await session.execute(
            select(WorkflowRecord).where(WorkflowRecord.workflow_id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise ApplicationError(
                f"Workflow {workflow_id} was not found",
                non_retryable=True,
            )

        existing_result = await session.execute(
            select(AgentExecutionRecord)
            .where(AgentExecutionRecord.workflow_id == workflow_id)
            .where(AgentExecutionRecord.agent_id == agent_id)
            .where(AgentExecutionRecord.status == "COMPLETED")
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            await _record_tool_invocations_from_agent_telemetry(
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                agent_id=agent_id,
                agent_execution_id=existing.agent_execution_id,
                telemetry=existing.execution_metadata,
                workflow_state=workflow_state,
            )
            return {
                "workflow_id": workflow_id,
                "agent_id": agent_id,
                "agent_execution_id": existing.agent_execution_id,
                "output": existing.output_payload,
                "idempotent": True,
            }

        request_payload = {
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "workflow_type": workflow.workflow_type,
            "workflow_state": workflow_state,
            "priority": workflow.priority,
            "metadata": workflow.workflow_metadata,
        }

    settings = get_settings()
    if not settings.enable_agent_runtime:
        response_payload = _deterministic_agent_fallback(agent_id, request_payload)
    else:
        response_payload = await _call_agent_runtime(settings.agent_runtime_url, agent_id, request_payload)

    completed_at = datetime.now(timezone.utc)
    agent_execution_id = response_payload["execution_id"]
    output_payload = response_payload["output"]
    event_id = f"{workflow_id}:agent.execution_completed:{agent_id}"

    async with SessionLocal() as session:
        session.add(
            AgentExecutionRecord(
                agent_execution_id=agent_execution_id,
                workflow_id=workflow_id,
                agent_id=agent_id,
                prompt_id=response_payload["prompt_id"],
                prompt_version=response_payload["prompt_version"],
                model_name=response_payload["model_name"],
                status=response_payload["status"],
                validation_status=response_payload["validation_status"],
                confidence_score=response_payload["confidence_score"],
                requires_human_review=response_payload["requires_human_review"],
                input_metadata=request_payload,
                output_payload=output_payload,
                execution_metadata=response_payload["telemetry"],
                error_message=None,
                correlation_id=correlation_id,
                created_by="workflow-engine",
                started_at=now,
                completed_at=completed_at,
                created_at=now,
            )
        )
        session.add(
            WorkflowTimelineEntry(
                timeline_entry_id=str(uuid4()),
                workflow_id=workflow_id,
                entry_type=TimelineEntryType.agent_execution_completed.value,
                message=f"Agent execution completed: {agent_id}",
                state=workflow_state,
                correlation_id=correlation_id,
                created_by="workflow-engine",
                entry_metadata={
                    "agent_execution_id": agent_execution_id,
                    "agent_id": agent_id,
                    "prompt_id": response_payload["prompt_id"],
                    "prompt_version": response_payload["prompt_version"],
                    "validation_status": response_payload["validation_status"],
                    "confidence_score": response_payload["confidence_score"],
                    "requires_human_review": response_payload["requires_human_review"],
                    "summary": output_payload.get("summary"),
                    "recommended_next_state": output_payload.get("recommended_next_state"),
                },
                created_at=completed_at,
            )
        )

        existing_event = await session.get(WorkflowEventOutbox, event_id)
        if existing_event is None:
            session.add(
                WorkflowEventOutbox(
                    event_id=event_id,
                    event_type=WorkflowEventType.agent_execution_completed.value,
                    event_version="1",
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    payload={
                        "workflow_id": workflow_id,
                        "agent_execution_id": agent_execution_id,
                        "agent_id": agent_id,
                        "prompt_id": response_payload["prompt_id"],
                        "prompt_version": response_payload["prompt_version"],
                        "validation_status": response_payload["validation_status"],
                        "confidence_score": response_payload["confidence_score"],
                        "requires_human_review": response_payload["requires_human_review"],
                        "recommended_next_state": output_payload.get("recommended_next_state"),
                    },
                    publish_status=OutboxPublishStatus.pending.value,
                    retry_count=0,
                    last_error=None,
                    created_at=completed_at,
                    published_at=None,
                )
            )

        await session.commit()

    await publish_workflow_event(event_id)
    await _record_tool_invocations_from_agent_telemetry(
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        agent_id=agent_id,
        agent_execution_id=agent_execution_id,
        telemetry=response_payload["telemetry"],
        workflow_state=workflow_state,
    )
    logger.info("agent execution completed", extra={"workflow_id": workflow_id, "agent_id": agent_id})
    return {
        "workflow_id": workflow_id,
        "agent_id": agent_id,
        "agent_execution_id": agent_execution_id,
        "output": output_payload,
        "idempotent": False,
    }


async def _record_tool_invocations_from_agent_telemetry(
    *,
    workflow_id: str,
    correlation_id: str,
    agent_id: str,
    agent_execution_id: str,
    telemetry: dict,
    workflow_state: str,
) -> list[dict]:
    recorded_invocations = []
    for invocation in telemetry.get("tool_invocations", []):
        tool_telemetry = invocation.get("telemetry", {})
        recorded_invocations.append(
            await record_tool_invocation(
                {
                    "workflow_id": workflow_id,
                    "correlation_id": correlation_id,
                    "tool_invocation_id": invocation["tool_invocation_id"],
                    "agent_execution_id": agent_execution_id,
                    "agent_id": agent_id,
                    "tool_id": invocation["tool_id"],
                    "status": invocation["status"],
                    "permission_status": invocation["permission_status"],
                    "input_validation_status": invocation["input_validation_status"],
                    "output_validation_status": invocation["output_validation_status"],
                    "input_metadata": {
                        "source": "agent_runtime_telemetry",
                        "workflow_state": workflow_state,
                        "idempotency_key": tool_telemetry.get("idempotency_key"),
                    },
                    "output_payload": {
                        "source": "agent_runtime_telemetry",
                        "tool_result_reference": invocation["tool_invocation_id"],
                    },
                    "execution_metadata": tool_telemetry
                    | {
                        "agent_runtime_recorded": True,
                        "workflow_state": workflow_state,
                    },
                    "error_message": None,
                }
            )
        )
    return recorded_invocations


async def _call_agent_runtime(agent_runtime_url: str, agent_id: str, payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(base_url=agent_runtime_url, timeout=10.0) as client:
            response = await client.post(f"/api/v1/agents/{agent_id}/executions", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise ApplicationError(
            f"Agent runtime call failed for {agent_id}: {exc}",
            non_retryable=False,
        ) from exc


def _deterministic_agent_fallback(agent_id: str, payload: dict) -> dict:
    execution_id = str(uuid4())
    if agent_id == "intake_agent":
        output = {
            "output_type": "intake_agent_output",
            "case_reference": payload["metadata"].get("case_reference"),
            "intake_classification": "MORTGAGE_EXCEPTION_REVIEW",
            "readiness": "READY_FOR_DOCUMENT_ANALYSIS",
            "missing_fields": [],
            "recommended_next_state": "DOCUMENT_ANALYSIS_PENDING",
            "summary": "Fallback intake result produced by workflow-engine for local replay.",
            "confidence_score": 0.80,
            "requires_human_review": False,
        }
        prompt_id = "intake-agent"
    else:
        output = {
            "output_type": "document_analysis_agent_output",
            "document_status": "NEEDS_REVIEW",
            "extracted_signals": ["mortgage_exception_review_case"],
            "missing_documents": [],
            "risk_flags": ["human_review_required"],
            "risk_level": "MEDIUM",
            "recommended_next_state": "RISK_REVIEW_PENDING",
            "summary": "Fallback document analysis result preserves human review.",
            "confidence_score": 0.80,
            "requires_human_review": True,
        }
        prompt_id = "document-analysis-agent"

    return {
        "execution_id": execution_id,
        "agent_id": agent_id,
        "status": "COMPLETED",
        "validation_status": "VALIDATED",
        "prompt_id": prompt_id,
        "prompt_version": "1",
        "model_name": "deterministic-workflow-engine-fallback-v1",
        "confidence_score": output["confidence_score"],
        "requires_human_review": output["requires_human_review"],
        "output": output,
        "telemetry": {
            "workflow_id": payload["workflow_id"],
            "correlation_id": payload["correlation_id"],
            "workflow_state": payload["workflow_state"],
            "fallback": True,
        },
    }
