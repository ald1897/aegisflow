from datetime import timedelta

from temporalio import workflow

PHASE_2_STATE_SEQUENCE: tuple[str, ...] = (
    "INTAKE_IN_PROGRESS",
    "DOCUMENT_ANALYSIS_PENDING",
    "RISK_REVIEW_PENDING",
    "HUMAN_REVIEW_REQUIRED",
)


@workflow.defn(name="MortgageExceptionReviewWorkflow")
class MortgageExceptionReviewWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        workflow_id = payload["workflow_id"]
        correlation_id = payload["correlation_id"]

        for state in PHASE_2_STATE_SEQUENCE:
            await workflow.execute_activity(
                "advance_workflow_state",
                {
                    "workflow_id": workflow_id,
                    "correlation_id": correlation_id,
                    "target_state": state,
                    "transition_reason": f"phase_2_progression_to_{state.lower()}",
                    "message": f"Workflow advanced to {state}",
                },
                schedule_to_close_timeout=timedelta(seconds=30),
            )

        return {
            "workflow_id": workflow_id,
            "state": PHASE_2_STATE_SEQUENCE[-1],
        }
