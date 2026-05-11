import json
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.config import Settings
from aegisflow_gateway.domain.workflows import OutboxPublishStatus
from aegisflow_gateway.persistence.models import WorkflowEventOutbox

logger = logging.getLogger(__name__)


class WorkflowEventPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def publish_event_by_id(self, session: AsyncSession, event_id: str) -> None:
        if not self.settings.enable_event_publishing:
            return

        result = await session.execute(
            select(WorkflowEventOutbox).where(WorkflowEventOutbox.event_id == event_id)
        )
        event = result.scalar_one_or_none()
        if event is None or event.publish_status == OutboxPublishStatus.published.value:
            return

        producer = AIOKafkaProducer(bootstrap_servers=self.settings.kafka_bootstrap_servers)
        try:
            await producer.start()
            await producer.send_and_wait(
                self.settings.kafka_workflow_events_topic,
                key=event.workflow_id.encode("utf-8"),
                value=json.dumps(
                    {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "event_version": event.event_version,
                        "workflow_id": event.workflow_id,
                        "correlation_id": event.correlation_id,
                        "payload": event.payload,
                    },
                    default=str,
                ).encode("utf-8"),
            )
            event.publish_status = OutboxPublishStatus.published.value
            event.published_at = datetime.now(timezone.utc)
            event.last_error = None
            logger.info("workflow event published", extra={"workflow_id": event.workflow_id})
        except Exception as exc:
            event.publish_status = OutboxPublishStatus.failed.value
            event.retry_count += 1
            event.last_error = str(exc)
            logger.exception("workflow event publication failed", extra={"workflow_id": event.workflow_id})
        finally:
            await producer.stop()

        await session.commit()
