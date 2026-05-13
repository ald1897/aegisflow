from dataclasses import dataclass, field

from aegisflow_gateway.domain.workflows import (
    PHASE_2_STATE_SEQUENCE,
    ReplayStepStatus,
    WorkflowEventType,
    WorkflowState,
    is_valid_transition,
)
from aegisflow_gateway.services.evidence import WorkflowEvidenceArtifact, WorkflowEvidenceSnapshot


@dataclass(frozen=True)
class ReplayValidationStep:
    sequence_number: int
    artifact_type: str
    status: ReplayStepStatus
    message: str
    artifact_id: str | None = None
    expected_state: str | None = None
    observed_state: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_replay_step_kwargs(self) -> dict:
        return {
            "sequence_number": self.sequence_number,
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "status": self.status,
            "message": self.message,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class DeterministicReplayValidationResult:
    workflow_id: str
    status: ReplayStepStatus
    summary: str
    steps: tuple[ReplayValidationStep, ...]

    @property
    def step_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for step in self.steps:
            counts[step.status.value] = counts.get(step.status.value, 0) + 1
        return counts


class DeterministicReplayValidator:
    def validate(self, snapshot: WorkflowEvidenceSnapshot) -> DeterministicReplayValidationResult:
        artifacts = _Artifacts(snapshot)
        steps = (
            self._validate_state_transition_sequence(snapshot, artifacts),
            self._validate_timeline_milestones(snapshot, artifacts),
            self._validate_agent_evidence(snapshot, artifacts),
            self._validate_tool_evidence(snapshot, artifacts),
            self._validate_human_review_evidence(snapshot, artifacts),
            self._validate_event_outbox_evidence(snapshot, artifacts),
            self._validate_evaluation_boundary(snapshot, artifacts),
        )
        status = _aggregate_status(steps)
        return DeterministicReplayValidationResult(
            workflow_id=snapshot.workflow_id,
            status=status,
            summary=_summary_for(status, steps),
            steps=steps,
        )

    def _validate_state_transition_sequence(
        self,
        snapshot: WorkflowEvidenceSnapshot,
        artifacts: "_Artifacts",
    ) -> ReplayValidationStep:
        transitions = artifacts.by_type("workflow_state_transition")
        observed_states = [artifact.metadata.get("new_state") for artifact in transitions]
        expected_states, decision_state = _expected_state_sequence(snapshot, artifacts)
        invalid_pairs = _invalid_transition_pairs(transitions)

        status = ReplayStepStatus.pass_
        message = "Workflow state transitions match the deterministic mortgage review path."
        if invalid_pairs:
            status = ReplayStepStatus.fail
            message = "Workflow state transitions include invalid adjacent states."
        elif decision_state is None and snapshot.workflow_state == WorkflowState.completed.value:
            status = ReplayStepStatus.fail
            message = "Completed workflow is missing terminal approval or rejection state evidence."
        elif observed_states != expected_states:
            status = ReplayStepStatus.fail
            message = "Workflow state transition sequence does not match the deterministic mortgage review path."

        return ReplayValidationStep(
            sequence_number=1,
            artifact_type="workflow_state_transition",
            artifact_id=transitions[-1].artifact_id if transitions else None,
            expected_state=expected_states[-1] if expected_states else None,
            observed_state=snapshot.workflow_state,
            status=status,
            message=message,
            metadata={
                "expected_states": expected_states,
                "observed_states": observed_states,
                "invalid_transition_pairs": invalid_pairs,
                "sensitive_payloads_persisted": False,
            },
        )

    def _validate_timeline_milestones(
        self,
        snapshot: WorkflowEvidenceSnapshot,
        artifacts: "_Artifacts",
    ) -> ReplayValidationStep:
        timeline_entries = artifacts.by_type("workflow_timeline_entry")
        observed_types = sorted({artifact.metadata.get("entry_type") for artifact in timeline_entries})
        expected_types = ["WORKFLOW_CREATED"]
        if snapshot.workflow_state != WorkflowState.new.value:
            expected_types.extend(
                [
                    "STATE_TRANSITION",
                    "AGENT_EXECUTION_COMPLETED",
                    "TOOL_INVOCATION_COMPLETED",
                ]
            )
        if artifacts.by_type("approval_record"):
            expected_types.append("APPROVAL_DECISION_RECORDED")

        missing_types = sorted(entry_type for entry_type in expected_types if entry_type not in observed_types)
        status = ReplayStepStatus.pass_
        message = "Workflow timeline contains the expected deterministic milestones."
        if missing_types:
            status = ReplayStepStatus.warn
            message = "Workflow timeline is missing one or more expected deterministic milestones."

        return ReplayValidationStep(
            sequence_number=2,
            artifact_type="workflow_timeline_entry",
            artifact_id=timeline_entries[-1].artifact_id if timeline_entries else None,
            expected_state=snapshot.workflow_state,
            observed_state=snapshot.workflow_state,
            status=status,
            message=message,
            metadata={
                "expected_entry_types": sorted(expected_types),
                "observed_entry_types": observed_types,
                "missing_entry_types": missing_types,
                "sensitive_payloads_persisted": False,
            },
        )

    def _validate_agent_evidence(
        self,
        snapshot: WorkflowEvidenceSnapshot,
        artifacts: "_Artifacts",
    ) -> ReplayValidationStep:
        agent_artifacts = artifacts.by_type("agent_execution_record")
        expected_agents = _expected_agents(snapshot)
        observed_agents = sorted({artifact.metadata.get("agent_id") for artifact in agent_artifacts})
        missing_agents = sorted(agent for agent in expected_agents if agent not in observed_agents)
        incomplete_agents = sorted(
            artifact.metadata.get("agent_id")
            for artifact in agent_artifacts
            if artifact.status != "COMPLETED" or artifact.metadata.get("validation_status") != "VALIDATED"
        )

        status = ReplayStepStatus.pass_
        message = "Agent execution evidence is complete for deterministic replay."
        if missing_agents or incomplete_agents:
            status = ReplayStepStatus.fail
            message = "Agent execution evidence is missing or incomplete for deterministic replay."

        return ReplayValidationStep(
            sequence_number=3,
            artifact_type="agent_execution_record",
            artifact_id=agent_artifacts[-1].artifact_id if agent_artifacts else None,
            expected_state=snapshot.workflow_state,
            observed_state=snapshot.workflow_state,
            status=status,
            message=message,
            metadata={
                "expected_agent_ids": expected_agents,
                "observed_agent_ids": observed_agents,
                "missing_agent_ids": missing_agents,
                "incomplete_agent_ids": incomplete_agents,
                "sensitive_payloads_persisted": False,
            },
        )

    def _validate_tool_evidence(
        self,
        snapshot: WorkflowEvidenceSnapshot,
        artifacts: "_Artifacts",
    ) -> ReplayValidationStep:
        tool_artifacts = artifacts.by_type("tool_invocation_record")
        expected_tools = _expected_tools(snapshot)
        observed_tools = sorted({artifact.metadata.get("tool_id") for artifact in tool_artifacts})
        missing_tools = sorted(tool for tool in expected_tools if tool not in observed_tools)
        incomplete_tools = sorted(
            artifact.metadata.get("tool_id")
            for artifact in tool_artifacts
            if artifact.status != "COMPLETED"
            or artifact.metadata.get("permission_status") != "AUTHORIZED"
            or artifact.metadata.get("input_validation_status") != "VALIDATED"
            or artifact.metadata.get("output_validation_status") != "VALIDATED"
        )

        status = ReplayStepStatus.pass_
        message = "Tool invocation evidence is complete for deterministic replay."
        if missing_tools or incomplete_tools:
            status = ReplayStepStatus.fail
            message = "Tool invocation evidence is missing or incomplete for deterministic replay."

        return ReplayValidationStep(
            sequence_number=4,
            artifact_type="tool_invocation_record",
            artifact_id=tool_artifacts[-1].artifact_id if tool_artifacts else None,
            expected_state=snapshot.workflow_state,
            observed_state=snapshot.workflow_state,
            status=status,
            message=message,
            metadata={
                "expected_tool_ids": expected_tools,
                "observed_tool_ids": observed_tools,
                "missing_tool_ids": missing_tools,
                "incomplete_tool_ids": incomplete_tools,
                "sensitive_payloads_persisted": False,
            },
        )

    def _validate_human_review_evidence(
        self,
        snapshot: WorkflowEvidenceSnapshot,
        artifacts: "_Artifacts",
    ) -> ReplayValidationStep:
        approval_artifacts = artifacts.by_type("approval_record")
        approval_statuses = sorted({artifact.status for artifact in approval_artifacts})
        expected_decision = _terminal_decision_state(approval_artifacts)

        status = ReplayStepStatus.pass_
        message = "Human review evidence matches the deterministic workflow state."
        if snapshot.workflow_state == WorkflowState.human_review_required.value and not approval_artifacts:
            status = ReplayStepStatus.warn
            message = "Workflow is waiting for human review and has no terminal approval record yet."
        elif snapshot.workflow_state == WorkflowState.completed.value and expected_decision is None:
            status = ReplayStepStatus.fail
            message = "Completed workflow is missing approved or rejected human review evidence."

        return ReplayValidationStep(
            sequence_number=5,
            artifact_type="approval_record",
            artifact_id=approval_artifacts[-1].artifact_id if approval_artifacts else None,
            expected_state=expected_decision,
            observed_state=snapshot.workflow_state,
            status=status,
            message=message,
            metadata={
                "approval_statuses": approval_statuses,
                "approval_count": len(approval_artifacts),
                "sensitive_payloads_persisted": False,
            },
        )

    def _validate_event_outbox_evidence(
        self,
        snapshot: WorkflowEvidenceSnapshot,
        artifacts: "_Artifacts",
    ) -> ReplayValidationStep:
        outbox_artifacts = artifacts.by_type("workflow_event_outbox")
        observed_event_types = sorted({artifact.metadata.get("event_type") for artifact in outbox_artifacts})
        expected_event_types = _expected_event_types(snapshot, artifacts)
        missing_event_types = sorted(
            event_type for event_type in expected_event_types if event_type not in observed_event_types
        )
        non_published_event_ids = sorted(
            artifact.artifact_id for artifact in outbox_artifacts if artifact.status != "PUBLISHED"
        )

        status = ReplayStepStatus.pass_
        message = "Workflow event outbox evidence is complete and published."
        if missing_event_types:
            status = ReplayStepStatus.fail
            message = "Workflow event outbox is missing expected deterministic event evidence."
        elif non_published_event_ids:
            status = ReplayStepStatus.warn
            message = "Workflow event outbox contains pending or failed event publication evidence."

        return ReplayValidationStep(
            sequence_number=6,
            artifact_type="workflow_event_outbox",
            artifact_id=outbox_artifacts[-1].artifact_id if outbox_artifacts else None,
            expected_state=snapshot.workflow_state,
            observed_state=snapshot.workflow_state,
            status=status,
            message=message,
            metadata={
                "expected_event_types": expected_event_types,
                "observed_event_types": observed_event_types,
                "missing_event_types": missing_event_types,
                "non_published_event_ids": non_published_event_ids,
                "sensitive_payloads_persisted": False,
            },
        )

    def _validate_evaluation_boundary(
        self,
        snapshot: WorkflowEvidenceSnapshot,
        artifacts: "_Artifacts",
    ) -> ReplayValidationStep:
        evaluation_runs = artifacts.by_type("evaluation_run")
        evaluation_results = artifacts.by_type("evaluation_result")
        failed_results = sorted(
            artifact.artifact_id for artifact in evaluation_results if artifact.status not in {"PASS", "WARN"}
        )

        status = ReplayStepStatus.pass_
        message = "Evaluation evidence is present and bounded for deterministic replay."
        if snapshot.workflow_state != WorkflowState.completed.value:
            status = ReplayStepStatus.skipped
            message = "Evaluation boundary is skipped until workflow completion."
        elif not evaluation_runs:
            status = ReplayStepStatus.warn
            message = "Completed workflow has no persisted evaluation run evidence."
        elif not evaluation_results:
            status = ReplayStepStatus.warn
            message = "Completed workflow has evaluation run evidence without result evidence."
        elif failed_results:
            status = ReplayStepStatus.fail
            message = "Completed workflow has failing evaluation result evidence."

        return ReplayValidationStep(
            sequence_number=7,
            artifact_type="evaluation_run",
            artifact_id=evaluation_runs[-1].artifact_id if evaluation_runs else None,
            expected_state=WorkflowState.completed.value,
            observed_state=snapshot.workflow_state,
            status=status,
            message=message,
            metadata={
                "evaluation_run_count": len(evaluation_runs),
                "evaluation_result_count": len(evaluation_results),
                "failed_evaluation_result_ids": failed_results,
                "sensitive_payloads_persisted": False,
            },
        )


class _Artifacts:
    def __init__(self, snapshot: WorkflowEvidenceSnapshot) -> None:
        self.snapshot = snapshot

    def by_type(self, artifact_type: str) -> tuple[WorkflowEvidenceArtifact, ...]:
        return self.snapshot.artifacts_by_type(artifact_type)


def _aggregate_status(steps: tuple[ReplayValidationStep, ...]) -> ReplayStepStatus:
    statuses = {step.status for step in steps}
    if ReplayStepStatus.fail in statuses:
        return ReplayStepStatus.fail
    if ReplayStepStatus.warn in statuses:
        return ReplayStepStatus.warn
    return ReplayStepStatus.pass_


def _summary_for(status: ReplayStepStatus, steps: tuple[ReplayValidationStep, ...]) -> str:
    counts: dict[str, int] = {}
    for step in steps:
        counts[step.status.value] = counts.get(step.status.value, 0) + 1
    return (
        f"Deterministic replay validation finished with {status.value}: "
        f"{counts.get('PASS', 0)} pass, {counts.get('WARN', 0)} warn, "
        f"{counts.get('FAIL', 0)} fail, {counts.get('SKIPPED', 0)} skipped."
    )


def _expected_state_sequence(
    snapshot: WorkflowEvidenceSnapshot,
    artifacts: _Artifacts,
) -> tuple[list[str], str | None]:
    prefix = [WorkflowState.new.value, *[state.value for state in PHASE_2_STATE_SEQUENCE]]
    current_state = snapshot.workflow_state
    decision_state = _terminal_decision_state(artifacts.by_type("approval_record"))

    if current_state == WorkflowState.completed.value:
        expected = [*prefix]
        if decision_state is not None:
            expected.append(decision_state)
        expected.append(WorkflowState.completed.value)
        return expected, decision_state
    if current_state in prefix:
        return prefix[: prefix.index(current_state) + 1], decision_state
    if current_state in {WorkflowState.approved.value, WorkflowState.rejected.value}:
        return [*prefix, current_state], decision_state
    if current_state == WorkflowState.failed.value:
        observed = [
            artifact.metadata.get("new_state")
            for artifact in artifacts.by_type("workflow_state_transition")
            if artifact.metadata.get("new_state") is not None
        ]
        return observed, decision_state
    return prefix, decision_state


def _terminal_decision_state(approval_artifacts: tuple[WorkflowEvidenceArtifact, ...]) -> str | None:
    decisions = [artifact.status for artifact in approval_artifacts if artifact.status in {"APPROVED", "REJECTED"}]
    if len(decisions) != 1:
        return None
    return decisions[0]


def _invalid_transition_pairs(transitions: tuple[WorkflowEvidenceArtifact, ...]) -> list[dict[str, str | None]]:
    invalid_pairs: list[dict[str, str | None]] = []
    for transition in transitions:
        prior_state = transition.metadata.get("prior_state")
        new_state = transition.metadata.get("new_state")
        if prior_state is None:
            if new_state != WorkflowState.new.value:
                invalid_pairs.append({"prior_state": None, "new_state": new_state})
            continue
        try:
            prior = WorkflowState(prior_state)
            new = WorkflowState(new_state)
        except ValueError:
            invalid_pairs.append({"prior_state": prior_state, "new_state": new_state})
            continue
        if not is_valid_transition(prior, new):
            invalid_pairs.append({"prior_state": prior_state, "new_state": new_state})
    return invalid_pairs


def _expected_agents(snapshot: WorkflowEvidenceSnapshot) -> list[str]:
    if snapshot.workflow_state == WorkflowState.new.value:
        return []
    return ["document_analysis_agent", "intake_agent"]


def _expected_tools(snapshot: WorkflowEvidenceSnapshot) -> list[str]:
    if snapshot.workflow_state == WorkflowState.new.value:
        return []
    return ["borrower_profile_lookup", "document_fetch"]


def _expected_event_types(snapshot: WorkflowEvidenceSnapshot, artifacts: _Artifacts) -> list[str]:
    expected = {WorkflowEventType.created.value}
    if snapshot.workflow_state != WorkflowState.new.value:
        expected.update(
            {
                WorkflowEventType.state_changed.value,
                WorkflowEventType.agent_execution_completed.value,
                WorkflowEventType.tool_invocation_completed.value,
            }
        )
    decision_state = _terminal_decision_state(artifacts.by_type("approval_record"))
    if decision_state is not None:
        expected.add(WorkflowEventType.approval_decision_recorded.value)
        expected.add(WorkflowEventType.completed.value)
        if decision_state == WorkflowState.approved.value:
            expected.add(WorkflowEventType.approved.value)
        if decision_state == WorkflowState.rejected.value:
            expected.add(WorkflowEventType.rejected.value)
    return sorted(expected)
