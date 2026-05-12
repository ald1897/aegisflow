from aegisflow_evaluation_service.schemas import EvaluationDatasetCaseCreate

LOCAL_MORTGAGE_EXCEPTION_DATASET_ID = "mortgage-exception-local-v1"


LOCAL_DATASET_CASES: tuple[EvaluationDatasetCaseCreate, ...] = (
    EvaluationDatasetCaseCreate(
        dataset_case_id=f"{LOCAL_MORTGAGE_EXCEPTION_DATASET_ID}:approval",
        dataset_id=LOCAL_MORTGAGE_EXCEPTION_DATASET_ID,
        case_name="approval",
        workflow_type="MORTGAGE_EXCEPTION_REVIEW",
        expected_agents={"agent_ids": ["intake_agent", "document_analysis_agent"]},
        expected_tools={"tool_ids": ["borrower_profile_lookup", "document_fetch"]},
        expected_human_review=True,
        expected_decision="APPROVED",
        expected_signals={
            "requires_human_review": True,
            "expected_terminal_state": "COMPLETED",
        },
        case_metadata={
            "dataset_version": "v1",
            "scenario": "local approval path",
            "replay_boundary": "dataset_evaluation_only",
        },
    ),
    EvaluationDatasetCaseCreate(
        dataset_case_id=f"{LOCAL_MORTGAGE_EXCEPTION_DATASET_ID}:rejection",
        dataset_id=LOCAL_MORTGAGE_EXCEPTION_DATASET_ID,
        case_name="rejection",
        workflow_type="MORTGAGE_EXCEPTION_REVIEW",
        expected_agents={"agent_ids": ["intake_agent", "document_analysis_agent"]},
        expected_tools={"tool_ids": ["borrower_profile_lookup", "document_fetch"]},
        expected_human_review=True,
        expected_decision="REJECTED",
        expected_signals={
            "requires_human_review": True,
            "expected_terminal_state": "COMPLETED",
        },
        case_metadata={
            "dataset_version": "v1",
            "scenario": "local rejection path",
            "replay_boundary": "dataset_evaluation_only",
        },
    ),
    EvaluationDatasetCaseCreate(
        dataset_case_id=f"{LOCAL_MORTGAGE_EXCEPTION_DATASET_ID}:human-review",
        dataset_id=LOCAL_MORTGAGE_EXCEPTION_DATASET_ID,
        case_name="human-review",
        workflow_type="MORTGAGE_EXCEPTION_REVIEW",
        expected_agents={"agent_ids": ["intake_agent", "document_analysis_agent"]},
        expected_tools={"tool_ids": ["borrower_profile_lookup", "document_fetch"]},
        expected_human_review=True,
        expected_decision=None,
        expected_signals={
            "requires_human_review": True,
            "expected_terminal_state": "HUMAN_REVIEW_REQUIRED",
        },
        case_metadata={
            "dataset_version": "v1",
            "scenario": "local queued human review path",
            "replay_boundary": "dataset_evaluation_only",
        },
    ),
)
