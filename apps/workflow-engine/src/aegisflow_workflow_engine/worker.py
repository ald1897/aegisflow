import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from aegisflow_workflow_engine.activities.agents import execute_agent
from aegisflow_workflow_engine.activities.state_transitions import advance_workflow_state
from aegisflow_workflow_engine.activities.tools import record_tool_invocation
from aegisflow_workflow_engine.config import get_settings
from aegisflow_workflow_engine.workflows.mortgage_exception_review import MortgageExceptionReviewWorkflow


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    logger = logging.getLogger(__name__)
    client: Client | None = None
    for attempt in range(1, 31):
        try:
            client = await Client.connect(settings.temporal_address)
            break
        except RuntimeError:
            logger.warning(
                "temporal connection unavailable; retrying",
                extra={"attempt": attempt},
            )
            await asyncio.sleep(2)

    if client is None:
        raise RuntimeError(f"Unable to connect to Temporal at {settings.temporal_address}")

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[MortgageExceptionReviewWorkflow],
        activities=[advance_workflow_state, execute_agent, record_tool_invocation],
    )
    logger.info(
        "workflow-engine worker started on task queue %s",
        settings.temporal_task_queue,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
