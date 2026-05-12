from aegisflow_workflow_engine.domain import WorkflowState, is_valid_transition


def test_phase_2_state_transitions_are_valid() -> None:
    assert is_valid_transition(WorkflowState.new, WorkflowState.intake_in_progress)
    assert is_valid_transition(WorkflowState.intake_in_progress, WorkflowState.document_analysis_pending)
    assert is_valid_transition(WorkflowState.document_analysis_pending, WorkflowState.risk_review_pending)
    assert is_valid_transition(WorkflowState.risk_review_pending, WorkflowState.human_review_required)
    assert is_valid_transition(WorkflowState.human_review_required, WorkflowState.approved)
    assert is_valid_transition(WorkflowState.human_review_required, WorkflowState.rejected)
    assert is_valid_transition(WorkflowState.approved, WorkflowState.completed)
    assert is_valid_transition(WorkflowState.rejected, WorkflowState.completed)


def test_invalid_state_transition_is_rejected() -> None:
    assert not is_valid_transition(WorkflowState.new, WorkflowState.risk_review_pending)
    assert not is_valid_transition(WorkflowState.new, WorkflowState.approved)
    assert not is_valid_transition(WorkflowState.approved, WorkflowState.rejected)
    assert not is_valid_transition(WorkflowState.completed, WorkflowState.failed)
