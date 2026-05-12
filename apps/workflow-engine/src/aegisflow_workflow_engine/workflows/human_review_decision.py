from datetime import timedelta

from temporalio import workflow


@workflow.defn(name="HumanReviewDecisionWorkflow")
class HumanReviewDecisionWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        return await workflow.execute_activity(
            "apply_human_review_decision",
            payload,
            schedule_to_close_timeout=timedelta(seconds=30),
        )
