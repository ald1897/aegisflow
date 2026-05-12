import asyncio
from time import perf_counter
from uuid import UUID

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from temporalio.client import Client

from aegisflow_gateway.config import Settings
from aegisflow_gateway.telemetry.metrics import (
    record_approval_decision_dispatch,
    record_temporal_workflow_start,
)
from aegisflow_gateway.telemetry.tracing import inject_trace_context


class TemporalWorkflowStarter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _connect(self) -> Client:
        client: Client | None = None
        for _ in range(10):
            try:
                client = await Client.connect(self.settings.temporal_address)
                break
            except RuntimeError:
                await asyncio.sleep(1)
        if client is None:
            raise RuntimeError(f"Unable to connect to Temporal at {self.settings.temporal_address}")
        return client

    async def start_mortgage_exception_review(
        self,
        *,
        workflow_id: UUID,
        correlation_id: str,
    ) -> tuple[str, str]:
        temporal_workflow_id = f"mortgage-exception-review-{workflow_id}"
        start_time = perf_counter()
        start_status = "started"
        tracer = trace.get_tracer(__name__)
        try:
            with tracer.start_as_current_span(
                "gateway.temporal.start_mortgage_exception_review",
                kind=SpanKind.CLIENT,
            ) as span:
                span.set_attribute("workflow_id", str(workflow_id))
                span.set_attribute("correlation_id", correlation_id)
                span.set_attribute("workflow_type", "MORTGAGE_EXCEPTION_REVIEW")
                span.set_attribute("temporal.workflow_id", temporal_workflow_id)
                span.set_attribute("temporal.task_queue", self.settings.temporal_task_queue)
                client = await self._connect()
                handle = await client.start_workflow(
                    "MortgageExceptionReviewWorkflow",
                    {
                        "workflow_id": str(workflow_id),
                        "correlation_id": correlation_id,
                        "trace_context": inject_trace_context(),
                    },
                    id=temporal_workflow_id,
                    task_queue=self.settings.temporal_task_queue,
                )
                span.set_attribute("temporal.run_id", handle.first_execution_run_id)
                return temporal_workflow_id, handle.first_execution_run_id
        except Exception:
            start_status = "failed"
            span = trace.get_current_span()
            if span.is_recording():
                span.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            record_temporal_workflow_start(
                operation="start_mortgage_exception_review",
                workflow_type="MORTGAGE_EXCEPTION_REVIEW",
                status=start_status,
                duration_seconds=perf_counter() - start_time,
            )

    async def apply_human_review_decision(self, payload: dict) -> dict:
        start_time = perf_counter()
        dispatch_status = "completed"
        decision = str(payload["decision"])
        temporal_workflow_id = f"human-review-decision-{payload['approval_id']}"
        tracer = trace.get_tracer(__name__)
        try:
            with tracer.start_as_current_span(
                "gateway.temporal.apply_human_review_decision",
                kind=SpanKind.CLIENT,
            ) as span:
                span.set_attribute("workflow_id", str(payload["workflow_id"]))
                span.set_attribute("approval_id", str(payload["approval_id"]))
                span.set_attribute("correlation_id", str(payload["correlation_id"]))
                span.set_attribute("approval.decision", decision)
                span.set_attribute("temporal.workflow_id", temporal_workflow_id)
                span.set_attribute("temporal.task_queue", self.settings.temporal_task_queue)
                client = await self._connect()
                handle = await client.start_workflow(
                    "HumanReviewDecisionWorkflow",
                    payload | {"trace_context": inject_trace_context()},
                    id=temporal_workflow_id,
                    task_queue=self.settings.temporal_task_queue,
                )
                result = await handle.result()
                return dict(result)
        except Exception:
            dispatch_status = "failed"
            span = trace.get_current_span()
            if span.is_recording():
                span.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            record_approval_decision_dispatch(
                decision=decision,
                status=dispatch_status,
                duration_seconds=perf_counter() - start_time,
            )
