from datetime import timedelta

from temporalio import workflow


@workflow.defn(name="MortgageExceptionReviewWorkflow")
class MortgageExceptionReviewWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        workflow_id = payload["workflow_id"]
        correlation_id = payload["correlation_id"]
        trace_context = payload.get("trace_context", {})

        await workflow.execute_activity(
            "advance_workflow_state",
            {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "trace_context": trace_context,
                "target_state": "INTAKE_IN_PROGRESS",
                "transition_reason": "phase_3_start_intake_agent",
                "message": "Workflow advanced to intake agent execution",
            },
            schedule_to_close_timeout=timedelta(seconds=30),
        )
        intake_result = await workflow.execute_activity(
            "execute_agent",
            {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "trace_context": trace_context,
                "agent_id": "intake_agent",
                "workflow_state": "INTAKE_IN_PROGRESS",
            },
            schedule_to_close_timeout=timedelta(seconds=45),
        )

        await workflow.execute_activity(
            "advance_workflow_state",
            {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "trace_context": trace_context,
                "target_state": intake_result["output"]["recommended_next_state"],
                "transition_reason": "phase_3_intake_agent_validated",
                "message": "Workflow advanced using validated intake agent output",
            },
            schedule_to_close_timeout=timedelta(seconds=30),
        )
        document_result = await workflow.execute_activity(
            "execute_agent",
            {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "trace_context": trace_context,
                "agent_id": "document_analysis_agent",
                "workflow_state": "DOCUMENT_ANALYSIS_PENDING",
            },
            schedule_to_close_timeout=timedelta(seconds=45),
        )

        await workflow.execute_activity(
            "advance_workflow_state",
            {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "trace_context": trace_context,
                "target_state": document_result["output"]["recommended_next_state"],
                "transition_reason": "phase_3_document_analysis_agent_validated",
                "message": "Workflow advanced using validated document analysis agent output",
            },
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        await workflow.execute_activity(
            "advance_workflow_state",
            {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "trace_context": trace_context,
                "target_state": "HUMAN_REVIEW_REQUIRED",
                "transition_reason": "phase_3_human_review_required",
                "message": "Workflow requires human review after governed agent execution",
            },
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        return {
            "workflow_id": workflow_id,
            "state": "HUMAN_REVIEW_REQUIRED",
        }
