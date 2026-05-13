from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.domain.workflows import RecoveryActionType, WorkflowState
from aegisflow_gateway.persistence.models import WorkflowRecord, WorkflowStateTransition


@dataclass(frozen=True)
class WorkflowRecoveryCheck:
    workflow_id: str
    action_type: RecoveryActionType
    target_resource_type: str
    target_resource_id: str
    allowed: bool
    current_state: str
    proposed_state: str | None
    reason: str
    requires_engine_execution: bool
    metadata: dict = field(default_factory=dict)


class WorkflowRecoveryPlanner:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def check(
        self,
        workflow: WorkflowRecord,
        *,
        action_type: RecoveryActionType,
    ) -> WorkflowRecoveryCheck:
        if action_type == RecoveryActionType.reconcile_workflow_projection:
            return await self._check_projection_reconciliation(workflow)
        if action_type == RecoveryActionType.resume_stuck_workflow_check:
            return self._check_stuck_workflow(workflow)
        return WorkflowRecoveryCheck(
            workflow_id=workflow.workflow_id,
            action_type=action_type,
            target_resource_type="workflow_record",
            target_resource_id=workflow.workflow_id,
            allowed=False,
            current_state=workflow.state,
            proposed_state=None,
            reason=f"Recovery action {action_type.value} is not a workflow recovery command.",
            requires_engine_execution=False,
            metadata={"sensitive_payloads_persisted": False},
        )

    async def _check_projection_reconciliation(self, workflow: WorkflowRecord) -> WorkflowRecoveryCheck:
        latest_transition = await self._latest_transition(workflow.workflow_id)
        if latest_transition is None:
            return WorkflowRecoveryCheck(
                workflow_id=workflow.workflow_id,
                action_type=RecoveryActionType.reconcile_workflow_projection,
                target_resource_type="workflow_record",
                target_resource_id=workflow.workflow_id,
                allowed=False,
                current_state=workflow.state,
                proposed_state=None,
                reason="Workflow has no state transition evidence to reconcile from.",
                requires_engine_execution=False,
                metadata={"sensitive_payloads_persisted": False},
            )
        if latest_transition.new_state == workflow.state:
            return WorkflowRecoveryCheck(
                workflow_id=workflow.workflow_id,
                action_type=RecoveryActionType.reconcile_workflow_projection,
                target_resource_type="workflow_record",
                target_resource_id=workflow.workflow_id,
                allowed=False,
                current_state=workflow.state,
                proposed_state=latest_transition.new_state,
                reason="Workflow projection already matches latest state transition evidence.",
                requires_engine_execution=False,
                metadata={
                    "latest_transition_id": latest_transition.transition_id,
                    "sensitive_payloads_persisted": False,
                },
            )
        return WorkflowRecoveryCheck(
            workflow_id=workflow.workflow_id,
            action_type=RecoveryActionType.reconcile_workflow_projection,
            target_resource_type="workflow_record",
            target_resource_id=workflow.workflow_id,
            allowed=True,
            current_state=workflow.state,
            proposed_state=latest_transition.new_state,
            reason="Workflow projection can be reconciled to the latest state transition evidence.",
            requires_engine_execution=True,
            metadata={
                "latest_transition_id": latest_transition.transition_id,
                "latest_transition_prior_state": latest_transition.prior_state,
                "latest_transition_new_state": latest_transition.new_state,
                "sensitive_payloads_persisted": False,
            },
        )

    def _check_stuck_workflow(self, workflow: WorkflowRecord) -> WorkflowRecoveryCheck:
        terminal_states = {WorkflowState.completed.value, WorkflowState.failed.value}
        allowed = workflow.state not in terminal_states
        return WorkflowRecoveryCheck(
            workflow_id=workflow.workflow_id,
            action_type=RecoveryActionType.resume_stuck_workflow_check,
            target_resource_type="workflow_record",
            target_resource_id=workflow.workflow_id,
            allowed=allowed,
            current_state=workflow.state,
            proposed_state=workflow.state,
            reason=(
                "Workflow is non-terminal and can receive a stuck-workflow dry-run check."
                if allowed
                else "Terminal workflows are not eligible for stuck-workflow resume checks."
            ),
            requires_engine_execution=False,
            metadata={
                "terminal_state": workflow.state in terminal_states,
                "sensitive_payloads_persisted": False,
            },
        )

    async def _latest_transition(self, workflow_id: str) -> WorkflowStateTransition | None:
        result = await self.session.execute(
            select(WorkflowStateTransition)
            .where(WorkflowStateTransition.workflow_id == workflow_id)
            .order_by(WorkflowStateTransition.created_at.desc(), WorkflowStateTransition.transition_id.desc())
        )
        return result.scalars().first()
