from enum import StrEnum


class WorkflowState(StrEnum):
    new = "NEW"
    intake_in_progress = "INTAKE_IN_PROGRESS"
    document_analysis_pending = "DOCUMENT_ANALYSIS_PENDING"
    risk_review_pending = "RISK_REVIEW_PENDING"
    human_review_required = "HUMAN_REVIEW_REQUIRED"
    completed = "COMPLETED"
    failed = "FAILED"


class WorkflowEventType(StrEnum):
    state_changed = "workflow.state_changed"
    failed = "workflow.failed"


class TimelineEntryType(StrEnum):
    state_transition = "STATE_TRANSITION"
    event_published = "EVENT_PUBLISHED"
    event_publish_failed = "EVENT_PUBLISH_FAILED"


class OutboxPublishStatus(StrEnum):
    pending = "PENDING"
    published = "PUBLISHED"
    failed = "FAILED"


PHASE_2_STATE_SEQUENCE: tuple[WorkflowState, ...] = (
    WorkflowState.intake_in_progress,
    WorkflowState.document_analysis_pending,
    WorkflowState.risk_review_pending,
    WorkflowState.human_review_required,
)


ALLOWED_STATE_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.new: {WorkflowState.intake_in_progress, WorkflowState.failed},
    WorkflowState.intake_in_progress: {WorkflowState.document_analysis_pending, WorkflowState.failed},
    WorkflowState.document_analysis_pending: {WorkflowState.risk_review_pending, WorkflowState.failed},
    WorkflowState.risk_review_pending: {WorkflowState.human_review_required, WorkflowState.failed},
    WorkflowState.human_review_required: {WorkflowState.completed, WorkflowState.failed},
    WorkflowState.completed: set(),
    WorkflowState.failed: set(),
}


def is_valid_transition(prior_state: WorkflowState, new_state: WorkflowState) -> bool:
    return new_state in ALLOWED_STATE_TRANSITIONS[prior_state]
