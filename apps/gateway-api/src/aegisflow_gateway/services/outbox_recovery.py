from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.domain.workflows import (
    OutboxFailureCategory,
    OutboxPublishStatus,
    RecoveryActionStatus,
    RecoveryActionType,
)
from aegisflow_gateway.persistence.models import WorkflowEventOutbox, WorkflowRecoveryAction
from aegisflow_gateway.services.events import WorkflowEventPublisher

MAX_RETRYABLE_OUTBOX_ATTEMPTS = 3
TERMINAL_ERROR_MARKERS = (
    "authorization",
    "forbidden",
    "invalid payload",
    "non-retryable",
    "schema validation",
    "validation",
)


@dataclass(frozen=True)
class OutboxEventClassification:
    event_id: str
    workflow_id: str
    event_type: str
    publish_status: str
    retry_count: int
    category: OutboxFailureCategory
    reason: str
    can_retry: bool
    can_dead_letter: bool
    last_error_present: bool
    metadata: dict = field(default_factory=dict)


class OutboxRecoveryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def classify(self, event: WorkflowEventOutbox) -> OutboxEventClassification:
        category = OutboxFailureCategory.informational
        reason = "Outbox event is pending normal publication."
        can_retry = False
        can_dead_letter = False

        if event.publish_status == OutboxPublishStatus.published.value:
            category = OutboxFailureCategory.terminal
            reason = "Outbox event has already been published."
        elif event.publish_status == OutboxPublishStatus.dead_lettered.value:
            category = OutboxFailureCategory.terminal
            reason = "Outbox event is already dead-lettered."
        elif event.publish_status == OutboxPublishStatus.failed.value:
            if _has_terminal_error(event.last_error):
                category = OutboxFailureCategory.dead_letterable
                reason = "Outbox event failed with a terminal-looking publication error."
                can_dead_letter = True
            elif event.retry_count >= MAX_RETRYABLE_OUTBOX_ATTEMPTS:
                category = OutboxFailureCategory.dead_letterable
                reason = "Outbox event exceeded the local retry threshold."
                can_dead_letter = True
            else:
                category = OutboxFailureCategory.retryable
                reason = "Outbox event failed below the local retry threshold."
                can_retry = True
                can_dead_letter = True
        elif event.publish_status != OutboxPublishStatus.pending.value:
            category = OutboxFailureCategory.terminal
            reason = "Outbox event has an unsupported publication status."

        return OutboxEventClassification(
            event_id=event.event_id,
            workflow_id=event.workflow_id,
            event_type=event.event_type,
            publish_status=event.publish_status,
            retry_count=event.retry_count,
            category=category,
            reason=reason,
            can_retry=can_retry,
            can_dead_letter=can_dead_letter,
            last_error_present=event.last_error is not None,
            metadata={
                "retry_threshold": MAX_RETRYABLE_OUTBOX_ATTEMPTS,
                "published_at_present": event.published_at is not None,
                "sensitive_payloads_persisted": False,
            },
        )

    async def retry_event(
        self,
        event: WorkflowEventOutbox,
        *,
        requested_by: str,
        reason: str,
        publisher: WorkflowEventPublisher | None = None,
    ) -> WorkflowRecoveryAction:
        classification = self.classify(event)
        if not classification.can_retry:
            raise ValueError(classification.reason)

        previous_publish_status = event.publish_status
        previous_retry_count = event.retry_count
        previous_last_error_present = event.last_error is not None
        event.publish_status = OutboxPublishStatus.pending.value
        event.last_error = None
        event.published_at = None

        recovery_action = WorkflowRecoveryAction(
            workflow_id=event.workflow_id,
            correlation_id=event.correlation_id,
            action_type=RecoveryActionType.retry_outbox_event.value,
            target_resource_type="workflow_event_outbox",
            target_resource_id=event.event_id,
            status=RecoveryActionStatus.running.value if publisher is not None else RecoveryActionStatus.completed.value,
            requested_by=requested_by,
            reason=reason,
            result_metadata={
                "classification": classification.category.value,
                "previous_publish_status": previous_publish_status,
                "previous_retry_count": previous_retry_count,
                "previous_last_error_present": previous_last_error_present,
                "queued_publish_status": OutboxPublishStatus.pending.value,
                "publisher_invoked": publisher is not None,
                "sensitive_payloads_persisted": False,
            },
        )
        self.session.add(recovery_action)
        await self.session.commit()
        await self.session.refresh(recovery_action)

        if publisher is not None:
            await publisher.publish_event_by_id(self.session, event.event_id)
            await self.session.refresh(event)
            if event.publish_status == OutboxPublishStatus.published.value:
                recovery_action.status = RecoveryActionStatus.completed.value
                recovery_action.completed_at = event.published_at
            else:
                recovery_action.status = RecoveryActionStatus.failed.value
            recovery_action.result_metadata = {
                **recovery_action.result_metadata,
                "final_publish_status": event.publish_status,
                "final_retry_count": event.retry_count,
                "final_last_error_present": event.last_error is not None,
            }
            await self.session.commit()
            await self.session.refresh(recovery_action)

        return recovery_action

    async def mark_dead_lettered(
        self,
        event: WorkflowEventOutbox,
        *,
        requested_by: str,
        reason: str,
    ) -> WorkflowRecoveryAction:
        classification = self.classify(event)
        if not classification.can_dead_letter:
            raise ValueError(classification.reason)

        previous_publish_status = event.publish_status
        previous_retry_count = event.retry_count
        previous_last_error_present = event.last_error is not None
        event.publish_status = OutboxPublishStatus.dead_lettered.value
        event.published_at = None

        recovery_action = WorkflowRecoveryAction(
            workflow_id=event.workflow_id,
            correlation_id=event.correlation_id,
            action_type=RecoveryActionType.mark_outbox_event_dead_lettered.value,
            target_resource_type="workflow_event_outbox",
            target_resource_id=event.event_id,
            status=RecoveryActionStatus.completed.value,
            requested_by=requested_by,
            reason=reason,
            result_metadata={
                "classification": classification.category.value,
                "previous_publish_status": previous_publish_status,
                "previous_retry_count": previous_retry_count,
                "previous_last_error_present": previous_last_error_present,
                "final_publish_status": OutboxPublishStatus.dead_lettered.value,
                "sensitive_payloads_persisted": False,
            },
        )
        self.session.add(recovery_action)
        await self.session.commit()
        await self.session.refresh(recovery_action)
        return recovery_action


def _has_terminal_error(last_error: str | None) -> bool:
    if not last_error:
        return False
    normalized_error = last_error.lower()
    return any(marker in normalized_error for marker in TERMINAL_ERROR_MARKERS)
