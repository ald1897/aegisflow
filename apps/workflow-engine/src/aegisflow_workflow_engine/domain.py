from enum import StrEnum


class WorkflowState(StrEnum):
    new = "NEW"
    intake_in_progress = "INTAKE_IN_PROGRESS"
    document_analysis_pending = "DOCUMENT_ANALYSIS_PENDING"
    risk_review_pending = "RISK_REVIEW_PENDING"
    human_review_required = "HUMAN_REVIEW_REQUIRED"
    approved = "APPROVED"
    rejected = "REJECTED"
    completed = "COMPLETED"
    failed = "FAILED"


class WorkflowEventType(StrEnum):
    state_changed = "workflow.state_changed"
    failed = "workflow.failed"
    approved = "workflow.approved"
    rejected = "workflow.rejected"
    completed = "workflow.completed"
    agent_execution_completed = "agent.execution_completed"
    agent_execution_failed = "agent.execution_failed"
    tool_invocation_completed = "tool.invocation_completed"
    tool_invocation_failed = "tool.invocation_failed"
    approval_decision_recorded = "approval.decision_recorded"


class TimelineEntryType(StrEnum):
    state_transition = "STATE_TRANSITION"
    agent_execution_completed = "AGENT_EXECUTION_COMPLETED"
    agent_execution_failed = "AGENT_EXECUTION_FAILED"
    tool_invocation_completed = "TOOL_INVOCATION_COMPLETED"
    tool_invocation_failed = "TOOL_INVOCATION_FAILED"
    approval_decision_recorded = "APPROVAL_DECISION_RECORDED"
    event_published = "EVENT_PUBLISHED"
    event_publish_failed = "EVENT_PUBLISH_FAILED"


class OutboxPublishStatus(StrEnum):
    pending = "PENDING"
    published = "PUBLISHED"
    failed = "FAILED"


class ReplayMode(StrEnum):
    history_reconstruction = "history_reconstruction"
    deterministic_validation = "deterministic_validation"
    dry_run_recovery_check = "dry_run_recovery_check"


class ReplayRunStatus(StrEnum):
    requested = "REQUESTED"
    running = "RUNNING"
    completed = "COMPLETED"
    failed = "FAILED"


class ReplayStepStatus(StrEnum):
    pass_ = "PASS"
    warn = "WARN"
    fail = "FAIL"
    skipped = "SKIPPED"


class RecoveryActionType(StrEnum):
    retry_outbox_event = "retry_outbox_event"
    mark_outbox_event_dead_lettered = "mark_outbox_event_dead_lettered"
    clear_retryable_outbox_error = "clear_retryable_outbox_error"
    reconcile_workflow_projection = "reconcile_workflow_projection"
    resume_stuck_workflow_check = "resume_stuck_workflow_check"


class RecoveryActionStatus(StrEnum):
    requested = "REQUESTED"
    running = "RUNNING"
    completed = "COMPLETED"
    failed = "FAILED"
    rejected = "REJECTED"


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
    WorkflowState.human_review_required: {WorkflowState.approved, WorkflowState.rejected, WorkflowState.failed},
    WorkflowState.approved: {WorkflowState.completed, WorkflowState.failed},
    WorkflowState.rejected: {WorkflowState.completed, WorkflowState.failed},
    WorkflowState.completed: set(),
    WorkflowState.failed: set(),
}


def is_valid_transition(prior_state: WorkflowState, new_state: WorkflowState) -> bool:
    return new_state in ALLOWED_STATE_TRANSITIONS[prior_state]
