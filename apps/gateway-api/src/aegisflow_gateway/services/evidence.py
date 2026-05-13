from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.persistence.models import (
    AgentExecutionRecord,
    ApprovalRecord,
    EvaluationResult,
    EvaluationRun,
    ToolInvocationRecord,
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowStateTransition,
    WorkflowTimelineEntry,
)


@dataclass(frozen=True)
class WorkflowEvidenceArtifact:
    artifact_type: str
    artifact_id: str
    owner: str
    occurred_at: datetime
    correlation_id: str
    status: str | None = None
    state: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowEvidenceDiagnostic:
    code: str
    status: str
    message: str
    artifact_type: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowEvidenceSnapshot:
    workflow_id: str
    workflow_type: str
    workflow_state: str
    correlation_id: str
    temporal_workflow_id: str | None
    temporal_run_id: str | None
    artifacts: tuple[WorkflowEvidenceArtifact, ...]
    diagnostics: tuple[WorkflowEvidenceDiagnostic, ...]
    artifact_counts: dict[str, int]

    def artifacts_by_type(self, artifact_type: str) -> tuple[WorkflowEvidenceArtifact, ...]:
        return tuple(artifact for artifact in self.artifacts if artifact.artifact_type == artifact_type)


class WorkflowEvidenceReconstructor:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reconstruct(self, workflow: WorkflowRecord) -> WorkflowEvidenceSnapshot:
        workflow_id = workflow.workflow_id
        transitions = await self._list_transitions(workflow_id)
        timeline_entries = await self._list_timeline_entries(workflow_id)
        outbox_events = await self._list_outbox_events(workflow_id)
        agent_executions = await self._list_agent_executions(workflow_id)
        tool_invocations = await self._list_tool_invocations(workflow_id)
        approval_records = await self._list_approval_records(workflow_id)
        evaluation_runs = await self._list_evaluation_runs(workflow_id)
        evaluation_results = await self._list_evaluation_results(workflow_id)

        evaluation_run_correlations = {
            evaluation_run.evaluation_run_id: evaluation_run.correlation_id for evaluation_run in evaluation_runs
        }
        artifacts = [
            self._workflow_artifact(workflow),
            *[self._transition_artifact(record) for record in transitions],
            *[self._timeline_artifact(record) for record in timeline_entries],
            *[self._outbox_artifact(record) for record in outbox_events],
            *[self._agent_artifact(record) for record in agent_executions],
            *[self._tool_artifact(record) for record in tool_invocations],
            *[self._approval_artifact(record) for record in approval_records],
            *[self._evaluation_run_artifact(record) for record in evaluation_runs],
            *[
                self._evaluation_result_artifact(
                    record,
                    correlation_id=evaluation_run_correlations.get(record.evaluation_run_id, workflow.correlation_id),
                )
                for record in evaluation_results
            ],
        ]
        ordered_artifacts = tuple(
            sorted(artifacts, key=lambda artifact: (artifact.occurred_at, artifact.artifact_type, artifact.artifact_id))
        )

        diagnostics = tuple(
            self._build_diagnostics(
                workflow=workflow,
                transitions=transitions,
                timeline_entries=timeline_entries,
                agent_executions=agent_executions,
                tool_invocations=tool_invocations,
                approval_records=approval_records,
                evaluation_runs=evaluation_runs,
            )
        )
        counts: dict[str, int] = {}
        for artifact in ordered_artifacts:
            counts[artifact.artifact_type] = counts.get(artifact.artifact_type, 0) + 1

        return WorkflowEvidenceSnapshot(
            workflow_id=workflow.workflow_id,
            workflow_type=workflow.workflow_type,
            workflow_state=workflow.state,
            correlation_id=workflow.correlation_id,
            temporal_workflow_id=workflow.temporal_workflow_id,
            temporal_run_id=workflow.temporal_run_id,
            artifacts=ordered_artifacts,
            diagnostics=diagnostics,
            artifact_counts=counts,
        )

    async def _list_transitions(self, workflow_id: str) -> list[WorkflowStateTransition]:
        result = await self.session.execute(
            select(WorkflowStateTransition)
            .where(WorkflowStateTransition.workflow_id == workflow_id)
            .order_by(WorkflowStateTransition.created_at.asc(), WorkflowStateTransition.transition_id.asc())
        )
        return list(result.scalars().all())

    async def _list_timeline_entries(self, workflow_id: str) -> list[WorkflowTimelineEntry]:
        result = await self.session.execute(
            select(WorkflowTimelineEntry)
            .where(WorkflowTimelineEntry.workflow_id == workflow_id)
            .order_by(WorkflowTimelineEntry.created_at.asc(), WorkflowTimelineEntry.timeline_entry_id.asc())
        )
        return list(result.scalars().all())

    async def _list_outbox_events(self, workflow_id: str) -> list[WorkflowEventOutbox]:
        result = await self.session.execute(
            select(WorkflowEventOutbox)
            .where(WorkflowEventOutbox.workflow_id == workflow_id)
            .order_by(WorkflowEventOutbox.created_at.asc(), WorkflowEventOutbox.event_id.asc())
        )
        return list(result.scalars().all())

    async def _list_agent_executions(self, workflow_id: str) -> list[AgentExecutionRecord]:
        result = await self.session.execute(
            select(AgentExecutionRecord)
            .where(AgentExecutionRecord.workflow_id == workflow_id)
            .order_by(AgentExecutionRecord.created_at.asc(), AgentExecutionRecord.agent_execution_id.asc())
        )
        return list(result.scalars().all())

    async def _list_tool_invocations(self, workflow_id: str) -> list[ToolInvocationRecord]:
        result = await self.session.execute(
            select(ToolInvocationRecord)
            .where(ToolInvocationRecord.workflow_id == workflow_id)
            .order_by(ToolInvocationRecord.created_at.asc(), ToolInvocationRecord.tool_invocation_id.asc())
        )
        return list(result.scalars().all())

    async def _list_approval_records(self, workflow_id: str) -> list[ApprovalRecord]:
        result = await self.session.execute(
            select(ApprovalRecord)
            .where(ApprovalRecord.workflow_id == workflow_id)
            .order_by(ApprovalRecord.reviewed_at.asc(), ApprovalRecord.approval_id.asc())
        )
        return list(result.scalars().all())

    async def _list_evaluation_runs(self, workflow_id: str) -> list[EvaluationRun]:
        result = await self.session.execute(
            select(EvaluationRun)
            .where(EvaluationRun.workflow_id == workflow_id)
            .order_by(EvaluationRun.started_at.asc(), EvaluationRun.evaluation_run_id.asc())
        )
        return list(result.scalars().all())

    async def _list_evaluation_results(self, workflow_id: str) -> list[EvaluationResult]:
        result = await self.session.execute(
            select(EvaluationResult)
            .where(EvaluationResult.workflow_id == workflow_id)
            .order_by(EvaluationResult.created_at.asc(), EvaluationResult.evaluation_result_id.asc())
        )
        return list(result.scalars().all())

    def _workflow_artifact(self, workflow: WorkflowRecord) -> WorkflowEvidenceArtifact:
        return WorkflowEvidenceArtifact(
            artifact_type="workflow_record",
            artifact_id=workflow.workflow_id,
            owner="gateway-api",
            occurred_at=workflow.created_at,
            correlation_id=workflow.correlation_id,
            status=workflow.state,
            state=workflow.state,
            metadata={
                "workflow_type": workflow.workflow_type,
                "priority": workflow.priority,
                "created_by": workflow.created_by,
                "temporal_workflow_id_present": workflow.temporal_workflow_id is not None,
                "temporal_run_id_present": workflow.temporal_run_id is not None,
            },
        )

    def _transition_artifact(self, transition: WorkflowStateTransition) -> WorkflowEvidenceArtifact:
        return WorkflowEvidenceArtifact(
            artifact_type="workflow_state_transition",
            artifact_id=transition.transition_id,
            owner="workflow-engine",
            occurred_at=transition.created_at,
            correlation_id=transition.correlation_id,
            status="RECORDED",
            state=transition.new_state,
            metadata={
                "prior_state": transition.prior_state,
                "new_state": transition.new_state,
                "transition_reason": transition.transition_reason,
                "created_by": transition.created_by,
            },
        )

    def _timeline_artifact(self, entry: WorkflowTimelineEntry) -> WorkflowEvidenceArtifact:
        return WorkflowEvidenceArtifact(
            artifact_type="workflow_timeline_entry",
            artifact_id=entry.timeline_entry_id,
            owner="workflow-engine",
            occurred_at=entry.created_at,
            correlation_id=entry.correlation_id,
            status=entry.entry_type,
            state=entry.state,
            metadata={
                "entry_type": entry.entry_type,
                "message": entry.message,
                "created_by": entry.created_by,
                "metadata_keys": sorted(entry.entry_metadata.keys()),
            },
        )

    def _outbox_artifact(self, event: WorkflowEventOutbox) -> WorkflowEvidenceArtifact:
        return WorkflowEvidenceArtifact(
            artifact_type="workflow_event_outbox",
            artifact_id=event.event_id,
            owner="gateway-api",
            occurred_at=event.created_at,
            correlation_id=event.correlation_id,
            status=event.publish_status,
            state=None,
            metadata={
                "event_type": event.event_type,
                "event_version": event.event_version,
                "retry_count": event.retry_count,
                "last_error_present": event.last_error is not None,
                "published_at_present": event.published_at is not None,
            },
        )

    def _agent_artifact(self, execution: AgentExecutionRecord) -> WorkflowEvidenceArtifact:
        return WorkflowEvidenceArtifact(
            artifact_type="agent_execution_record",
            artifact_id=execution.agent_execution_id,
            owner="agent-runtime",
            occurred_at=execution.created_at,
            correlation_id=execution.correlation_id,
            status=execution.status,
            state=execution.execution_metadata.get("workflow_state"),
            metadata={
                "agent_id": execution.agent_id,
                "prompt_id": execution.prompt_id,
                "prompt_version": execution.prompt_version,
                "model_name": execution.model_name,
                "validation_status": execution.validation_status,
                "requires_human_review": execution.requires_human_review,
                "error_present": execution.error_message is not None,
                "output_keys": sorted(execution.output_payload.keys()),
            },
        )

    def _tool_artifact(self, invocation: ToolInvocationRecord) -> WorkflowEvidenceArtifact:
        return WorkflowEvidenceArtifact(
            artifact_type="tool_invocation_record",
            artifact_id=invocation.tool_invocation_id,
            owner="tool-runtime",
            occurred_at=invocation.created_at,
            correlation_id=invocation.correlation_id,
            status=invocation.status,
            state=None,
            metadata={
                "agent_execution_id": invocation.agent_execution_id,
                "agent_id": invocation.agent_id,
                "tool_id": invocation.tool_id,
                "permission_status": invocation.permission_status,
                "input_validation_status": invocation.input_validation_status,
                "output_validation_status": invocation.output_validation_status,
                "error_present": invocation.error_message is not None,
                "output_keys": sorted(invocation.output_payload.keys()),
            },
        )

    def _approval_artifact(self, approval: ApprovalRecord) -> WorkflowEvidenceArtifact:
        return WorkflowEvidenceArtifact(
            artifact_type="approval_record",
            artifact_id=approval.approval_id,
            owner="workflow-engine",
            occurred_at=approval.reviewed_at,
            correlation_id=approval.correlation_id,
            status=approval.decision,
            state=approval.decision,
            metadata={
                "decision": approval.decision,
                "decision_reason": approval.decision_reason,
                "reviewed_by": approval.reviewed_by,
                "comment_present": bool(approval.comment),
                "metadata_keys": sorted(approval.approval_metadata.keys()),
            },
        )

    def _evaluation_run_artifact(self, run: EvaluationRun) -> WorkflowEvidenceArtifact:
        return WorkflowEvidenceArtifact(
            artifact_type="evaluation_run",
            artifact_id=run.evaluation_run_id,
            owner="evaluation-service",
            occurred_at=run.started_at,
            correlation_id=run.correlation_id,
            status=run.status,
            state=None,
            metadata={
                "evaluation_scope": run.evaluation_scope,
                "evaluation_mode": run.evaluation_mode,
                "dataset_id": run.dataset_id,
                "created_by": run.created_by,
                "metadata_keys": sorted(run.run_metadata.keys()),
            },
        )

    def _evaluation_result_artifact(
        self,
        result: EvaluationResult,
        *,
        correlation_id: str,
    ) -> WorkflowEvidenceArtifact:
        return WorkflowEvidenceArtifact(
            artifact_type="evaluation_result",
            artifact_id=result.evaluation_result_id,
            owner="evaluation-service",
            occurred_at=result.created_at,
            correlation_id=correlation_id,
            status=result.score_status,
            state=None,
            metadata={
                "evaluation_run_id": result.evaluation_run_id,
                "agent_execution_id": result.agent_execution_id,
                "evaluator_id": result.evaluator_id,
                "evaluator_version": result.evaluator_version,
                "score_name": result.score_name,
                "severity": result.severity,
                "metadata_keys": sorted(result.result_metadata.keys()),
            },
        )

    def _build_diagnostics(
        self,
        *,
        workflow: WorkflowRecord,
        transitions: list[WorkflowStateTransition],
        timeline_entries: list[WorkflowTimelineEntry],
        agent_executions: list[AgentExecutionRecord],
        tool_invocations: list[ToolInvocationRecord],
        approval_records: list[ApprovalRecord],
        evaluation_runs: list[EvaluationRun],
    ) -> list[WorkflowEvidenceDiagnostic]:
        diagnostics = []
        if not transitions:
            diagnostics.append(
                WorkflowEvidenceDiagnostic(
                    code="missing_state_transitions",
                    status="WARN",
                    artifact_type="workflow_state_transition",
                    message="No workflow state transition records were found for this workflow.",
                )
            )
        if not timeline_entries:
            diagnostics.append(
                WorkflowEvidenceDiagnostic(
                    code="missing_timeline_entries",
                    status="WARN",
                    artifact_type="workflow_timeline_entry",
                    message="No workflow timeline entries were found for this workflow.",
                )
            )
        if workflow.state != "NEW" and not agent_executions:
            diagnostics.append(
                WorkflowEvidenceDiagnostic(
                    code="missing_agent_execution_records",
                    status="WARN",
                    artifact_type="agent_execution_record",
                    message="Workflow has progressed beyond NEW without persisted agent execution evidence.",
                )
            )
        if agent_executions and not tool_invocations:
            diagnostics.append(
                WorkflowEvidenceDiagnostic(
                    code="missing_tool_invocation_records",
                    status="WARN",
                    artifact_type="tool_invocation_record",
                    message="Agent execution evidence exists without persisted tool invocation evidence.",
                )
            )
        if workflow.state == "HUMAN_REVIEW_REQUIRED" and not approval_records:
            diagnostics.append(
                WorkflowEvidenceDiagnostic(
                    code="human_review_pending",
                    status="WARN",
                    artifact_type="approval_record",
                    message="Workflow is waiting for human review and has no approval record yet.",
                )
            )
        if workflow.state == "COMPLETED" and not approval_records:
            diagnostics.append(
                WorkflowEvidenceDiagnostic(
                    code="missing_terminal_approval_record",
                    status="WARN",
                    artifact_type="approval_record",
                    message="Workflow is completed but no approval or rejection record was found.",
                )
            )
        if workflow.state == "COMPLETED" and not evaluation_runs:
            diagnostics.append(
                WorkflowEvidenceDiagnostic(
                    code="missing_evaluation_runs",
                    status="INFO",
                    artifact_type="evaluation_run",
                    message="Completed workflow has not been evaluated yet.",
                )
            )
        if not diagnostics:
            diagnostics.append(
                WorkflowEvidenceDiagnostic(
                    code="evidence_snapshot_complete",
                    status="PASS",
                    message="Workflow evidence snapshot contains the expected persisted artifact families.",
                )
            )
        return diagnostics
