import asyncio
from uuid import UUID

from temporalio.client import Client

from aegisflow_gateway.config import Settings


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
        client = await self._connect()

        handle = await client.start_workflow(
            "MortgageExceptionReviewWorkflow",
            {
                "workflow_id": str(workflow_id),
                "correlation_id": correlation_id,
            },
            id=temporal_workflow_id,
            task_queue=self.settings.temporal_task_queue,
        )
        return temporal_workflow_id, handle.first_execution_run_id

    async def apply_human_review_decision(self, payload: dict) -> dict:
        client = await self._connect()
        handle = await client.start_workflow(
            "HumanReviewDecisionWorkflow",
            payload,
            id=f"human-review-decision-{payload['approval_id']}",
            task_queue=self.settings.temporal_task_queue,
        )
        result = await handle.result()
        return dict(result)
