import json
import logging
from datetime import datetime, timezone
from time import perf_counter

from aiokafka import AIOKafkaProducer
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.config import Settings
from aegisflow_gateway.domain.workflows import OutboxPublishStatus
from aegisflow_gateway.persistence.models import WorkflowEventOutbox
from aegisflow_gateway.telemetry.metrics import record_event_publication

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
        start_time = perf_counter()
        publish_status = "published"
        tracer = trace.get_tracer(__name__)
        try:
            with tracer.start_as_current_span("gateway.kafka.publish_workflow_event", kind=SpanKind.PRODUCER) as span:
                span.set_attribute("workflow_id", event.workflow_id)
                span.set_attribute("correlation_id", event.correlation_id)
                span.set_attribute("event_id", event.event_id)
                span.set_attribute("event.type", event.event_type)
                span.set_attribute("messaging.destination.name", self.settings.kafka_workflow_events_topic)
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
            publish_status = "failed"
            span = trace.get_current_span()
            if span.is_recording():
                span.set_status(Status(StatusCode.ERROR))
            event.publish_status = OutboxPublishStatus.failed.value
            event.retry_count += 1
            event.last_error = str(exc)
            logger.exception("workflow event publication failed", extra={"workflow_id": event.workflow_id})
        finally:
            await producer.stop()
            record_event_publication(
                event_type=event.event_type,
                status=publish_status,
                duration_seconds=perf_counter() - start_time,
            )

        await session.commit()
