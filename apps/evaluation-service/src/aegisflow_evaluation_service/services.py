from datetime import datetime, timezone
from uuid import UUID

from aegisflow_evaluation_service.datasets import LOCAL_DATASET_CASES
from aegisflow_evaluation_service.evaluators import DatasetReplayEvaluator, EvaluationScore, evaluate_deterministically
from aegisflow_evaluation_service.evidence import (
    AgentExecutionEvidence,
    EvaluationExpectations,
    ToolInvocationEvidence,
    WorkflowEvaluationEvidence,
)
from aegisflow_evaluation_service.judges import JudgeEvaluationRequest, get_judge_evaluator
from aegisflow_evaluation_service.repository import EvaluationRepository
from aegisflow_evaluation_service.schemas import (
    EvaluationDatasetCaseCreate,
    EvaluationDatasetCaseRead,
    EvaluationDatasetSummary,
    EvaluationResultCreate,
    EvaluationResultRead,
    EvaluationRunDetail,
    EvaluationRunCreate,
    EvaluationRunRead,
    EvaluationRunRequest,
    EvaluationRunSummary,
)


class EvaluationOrchestrationError(Exception):
    error_code = "evaluation_orchestration_error"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class WorkflowNotFoundError(EvaluationOrchestrationError):
    error_code = "workflow_not_found"
    status_code = 404


class WorkflowNotReadyForEvaluationError(EvaluationOrchestrationError):
    error_code = "workflow_not_ready_for_evaluation"
    status_code = 409


class DatasetCaseNotFoundError(EvaluationOrchestrationError):
    error_code = "dataset_case_not_found"
    status_code = 404


REVIEWABLE_OR_TERMINAL_STATES = {"HUMAN_REVIEW_REQUIRED", "APPROVED", "REJECTED", "COMPLETED"}


class EvaluationPersistenceService:
    def __init__(self, repository: EvaluationRepository) -> None:
        self.repository = repository

    async def create_run(self, payload: EvaluationRunCreate):
        return await self.repository.create_run(payload)

    async def get_run(self, evaluation_run_id: str):
        return await self.repository.get_run(evaluation_run_id)

    async def list_runs_for_workflow(self, workflow_id: str):
        return await self.repository.list_runs_for_workflow(workflow_id)

    async def create_result(self, payload: EvaluationResultCreate):
        return await self.repository.create_result(payload)

    async def list_results_for_run(self, evaluation_run_id: str):
        return await self.repository.list_results_for_run(evaluation_run_id)

    async def create_dataset_case(self, payload: EvaluationDatasetCaseCreate):
        return await self.repository.create_dataset_case(payload)

    async def list_dataset_cases(self, dataset_id: str | None = None):
        return await self.repository.list_dataset_cases(dataset_id)


class EvaluationRunService:
    def __init__(self, repository: EvaluationRepository, *, judge_settings) -> None:
        self.repository = repository
        self.judge_settings = judge_settings

    async def create_workflow_run(
        self,
        workflow_id: UUID,
        payload: EvaluationRunRequest,
        *,
        created_by: str,
    ) -> EvaluationRunDetail:
        existing = await self.repository.get_run(str(payload.evaluation_run_id))
        if existing is not None:
            results = await self.repository.list_results_for_run(str(payload.evaluation_run_id))
            return EvaluationRunDetail(
                run=EvaluationRunRead.model_validate(existing),
                results=[EvaluationResultRead.model_validate(result) for result in results],
            )

        evidence = await self.load_workflow_evidence(str(workflow_id))
        dataset_case = await self._get_dataset_case_for_run(payload)
        expectations = self._build_expectations(payload, dataset_case)

        started_at = datetime.now(timezone.utc)
        scores = self._score_evidence(evidence, expectations, payload.evaluation_mode, dataset_case is not None)
        completed_at = datetime.now(timezone.utc)
        run_dataset_id = dataset_case.dataset_id if dataset_case else payload.dataset_id
        run = await self.repository.create_run(
            EvaluationRunCreate(
                evaluation_run_id=payload.evaluation_run_id,
                workflow_id=workflow_id,
                correlation_id=evidence.correlation_id,
                evaluation_scope=payload.evaluation_scope,
                evaluation_mode=payload.evaluation_mode,
                dataset_id=run_dataset_id,
                status="COMPLETED",
                started_at=started_at,
                completed_at=completed_at,
                created_by=created_by,
                run_metadata={
                    **payload.run_metadata,
                    "dataset_case_id": dataset_case.dataset_case_id if dataset_case else payload.dataset_case_id,
                    "agent_execution_count": len(evidence.agent_executions),
                    "tool_invocation_count": len(evidence.tool_invocations),
                    "approval_decision_present": evidence.approval_decision is not None,
                    "replay_boundary": "dataset_evaluation_only" if dataset_case else "none",
                },
            )
        )
        results = []
        for score in scores:
            result = await self.repository.create_result(
                EvaluationResultCreate(
                    evaluation_run_id=payload.evaluation_run_id,
                    workflow_id=workflow_id,
                    agent_execution_id=_uuid_or_none(score.agent_execution_id),
                    prompt_id=score.prompt_id,
                    prompt_version=score.prompt_version,
                    model_name=score.model_name,
                    evaluator_id=score.evaluator_id,
                    evaluator_version=score.evaluator_version,
                    score_name=score.score_name,
                    score_value=score.score_value,
                    score_status=score.score_status,
                    severity=score.severity,
                    rationale=score.rationale,
                    result_metadata=score.result_metadata,
                )
            )
            results.append(result)

        return EvaluationRunDetail(
            run=EvaluationRunRead.model_validate(run),
            results=[EvaluationResultRead.model_validate(result) for result in results],
        )

    async def get_run_detail(self, evaluation_run_id: UUID) -> EvaluationRunDetail | None:
        run = await self.repository.get_run(str(evaluation_run_id))
        if run is None:
            return None
        results = await self.repository.list_results_for_run(str(evaluation_run_id))
        return EvaluationRunDetail(
            run=EvaluationRunRead.model_validate(run),
            results=[EvaluationResultRead.model_validate(result) for result in results],
        )

    async def list_workflow_runs(self, workflow_id: UUID) -> list[EvaluationRunSummary]:
        workflow = await self.repository.get_workflow(str(workflow_id))
        if workflow is None:
            raise WorkflowNotFoundError("workflow was not found")
        runs = await self.repository.list_runs_for_workflow(str(workflow_id))
        summaries: list[EvaluationRunSummary] = []
        for run in runs:
            results = await self.repository.list_results_for_run(run.evaluation_run_id)
            summaries.append(
                EvaluationRunSummary(
                    **EvaluationRunRead.model_validate(run).model_dump(),
                    result_count=len(results),
                )
            )
        return summaries

    async def load_workflow_evidence(self, workflow_id: str) -> WorkflowEvaluationEvidence:
        workflow = await self.repository.get_workflow(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError("workflow was not found")
        if workflow.state not in REVIEWABLE_OR_TERMINAL_STATES:
            raise WorkflowNotReadyForEvaluationError("workflow has not reached a reviewable or terminal state")

        agent_records = await self.repository.list_agent_executions_for_workflow(workflow_id)
        if not agent_records:
            raise WorkflowNotReadyForEvaluationError("workflow has no persisted agent execution evidence")

        tool_records = await self.repository.list_tool_invocations_for_workflow(workflow_id)
        await self.repository.list_timeline_entries_for_workflow(workflow_id)
        approvals = await self.repository.list_approval_records_for_workflow(workflow_id)
        approval_decision = approvals[-1].decision if approvals else None

        return WorkflowEvaluationEvidence(
            workflow_id=workflow.workflow_id,
            workflow_type=workflow.workflow_type or "UNKNOWN",
            workflow_state=workflow.state or "UNKNOWN",
            correlation_id=workflow.correlation_id or "",
            agent_executions=tuple(
                AgentExecutionEvidence(
                    agent_execution_id=agent.agent_execution_id,
                    agent_id=agent.agent_id or "unknown_agent",
                    prompt_id=agent.prompt_id or "unknown_prompt",
                    prompt_version=agent.prompt_version or "unknown",
                    model_name=agent.model_name or "unknown_model",
                    status=agent.status or "UNKNOWN",
                    validation_status=agent.validation_status or "UNKNOWN",
                    confidence_score=float(agent.confidence_score or 0.0),
                    requires_human_review=bool(agent.requires_human_review),
                    output_payload=agent.output_payload or {},
                    execution_metadata=agent.execution_metadata or {},
                )
                for agent in agent_records
            ),
            tool_invocations=tuple(
                ToolInvocationEvidence(
                    tool_invocation_id=tool.tool_invocation_id,
                    agent_execution_id=tool.agent_execution_id,
                    agent_id=tool.agent_id,
                    tool_id=tool.tool_id,
                    status=tool.status,
                    permission_status=tool.permission_status,
                    input_validation_status=tool.input_validation_status,
                    output_validation_status=tool.output_validation_status,
                    output_payload=tool.output_payload or {},
                    execution_metadata=tool.execution_metadata or {},
                )
                for tool in tool_records
            ),
            approval_decision=approval_decision,
        )

    def _score_evidence(
        self,
        evidence: WorkflowEvaluationEvidence,
        expectations: EvaluationExpectations,
        evaluation_mode: str,
        include_dataset_score: bool,
    ) -> list[EvaluationScore]:
        scores = evaluate_deterministically(evidence, expectations)
        if include_dataset_score or evaluation_mode == "dataset_replay":
            scores.extend(DatasetReplayEvaluator().evaluate(evidence, expectations))
        if evaluation_mode == "judge_model_disabled":
            judge_score = get_judge_evaluator(self.judge_settings).evaluate(
                JudgeEvaluationRequest(evidence=evidence, expectations=expectations)
            )
            scores.append(judge_score.to_evaluation_score())
        return scores

    async def list_datasets(self) -> list[EvaluationDatasetSummary]:
        await self._ensure_local_dataset_cases()
        cases = await self.repository.list_dataset_cases()
        grouped: dict[str, list] = {}
        for dataset_case in cases:
            grouped.setdefault(dataset_case.dataset_id, []).append(dataset_case)

        summaries: list[EvaluationDatasetSummary] = []
        for dataset_id, dataset_cases in sorted(grouped.items()):
            version = None
            for dataset_case in dataset_cases:
                version = dataset_case.case_metadata.get("dataset_version")
                if version:
                    break
            summaries.append(
                EvaluationDatasetSummary(
                    dataset_id=dataset_id,
                    workflow_type=dataset_cases[0].workflow_type,
                    case_count=len(dataset_cases),
                    dataset_version=version,
                )
            )
        return summaries

    async def list_dataset_cases(self, dataset_id: str) -> list[EvaluationDatasetCaseRead]:
        await self._ensure_local_dataset_cases()
        cases = await self.repository.list_dataset_cases(dataset_id)
        return [EvaluationDatasetCaseRead.model_validate(dataset_case) for dataset_case in cases]

    async def _get_dataset_case_for_run(self, payload: EvaluationRunRequest):
        if payload.dataset_case_id is None:
            return None
        await self._ensure_local_dataset_cases()
        dataset_case = await self.repository.get_dataset_case(payload.dataset_case_id)
        if dataset_case is None:
            raise DatasetCaseNotFoundError("dataset case was not found")
        if payload.dataset_id and payload.dataset_id != dataset_case.dataset_id:
            raise DatasetCaseNotFoundError("dataset case was not found in the requested dataset")
        return dataset_case

    async def _ensure_local_dataset_cases(self) -> None:
        for dataset_case in LOCAL_DATASET_CASES:
            await self.repository.create_dataset_case(dataset_case)

    def _build_expectations(self, payload: EvaluationRunRequest, dataset_case) -> EvaluationExpectations:
        if dataset_case is None:
            return EvaluationExpectations(
                expected_agents=payload.expected_agents,
                expected_tools=payload.expected_tools,
                expected_human_review=payload.expected_human_review,
                expected_terminal_decision=payload.expected_terminal_decision,
            )

        expected_agents = tuple(dataset_case.expected_agents.get("agent_ids", ()))
        expected_tools = tuple(dataset_case.expected_tools.get("tool_ids", ()))
        return EvaluationExpectations(
            expected_agents=payload.expected_agents or expected_agents,
            expected_tools=payload.expected_tools or expected_tools,
            expected_human_review=(
                payload.expected_human_review
                if payload.expected_human_review is not None
                else dataset_case.expected_human_review
            ),
            expected_terminal_decision=payload.expected_terminal_decision or dataset_case.expected_decision,
        )


def _uuid_or_none(value: str | None) -> UUID | None:
    if value is None:
        return None
    return UUID(value)
