from aegisflow_workflow_engine.domain import WorkflowState, is_valid_transition


def test_phase_2_state_transitions_are_valid() -> None:
    assert is_valid_transition(WorkflowState.new, WorkflowState.intake_in_progress)
    assert is_valid_transition(WorkflowState.intake_in_progress, WorkflowState.document_analysis_pending)
    assert is_valid_transition(WorkflowState.document_analysis_pending, WorkflowState.risk_review_pending)
    assert is_valid_transition(WorkflowState.risk_review_pending, WorkflowState.human_review_required)


def test_invalid_state_transition_is_rejected() -> None:
    assert not is_valid_transition(WorkflowState.new, WorkflowState.risk_review_pending)
    assert not is_valid_transition(WorkflowState.completed, WorkflowState.failed)
