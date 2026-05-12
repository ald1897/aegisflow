from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_evaluation_service.models import (
    AgentExecutionRecord,
    ApprovalRecord,
    EvaluationDatasetCase,
    EvaluationResult,
    EvaluationRun,
    ToolInvocationRecord,
    WorkflowRecord,
    WorkflowTimelineEntry,
)
from aegisflow_evaluation_service.schemas import (
    EvaluationDatasetCaseCreate,
    EvaluationResultCreate,
    EvaluationRunCreate,
)


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(self, payload: EvaluationRunCreate) -> EvaluationRun:
        existing = await self.get_run(str(payload.evaluation_run_id))
        if existing is not None:
            return existing

        run = EvaluationRun(
            evaluation_run_id=str(payload.evaluation_run_id),
            workflow_id=str(payload.workflow_id),
            correlation_id=payload.correlation_id,
            evaluation_scope=payload.evaluation_scope,
            evaluation_mode=payload.evaluation_mode,
            dataset_id=payload.dataset_id,
            status=payload.status,
            started_at=payload.started_at,
            completed_at=payload.completed_at,
            created_by=payload.created_by,
            run_metadata=payload.run_metadata,
        )
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def get_run(self, evaluation_run_id: str) -> EvaluationRun | None:
        return await self.session.get(EvaluationRun, evaluation_run_id)

    async def list_runs_for_workflow(self, workflow_id: str) -> list[EvaluationRun]:
        result = await self.session.execute(
            select(EvaluationRun)
            .where(EvaluationRun.workflow_id == workflow_id)
            .order_by(EvaluationRun.started_at.asc(), EvaluationRun.evaluation_run_id.asc())
        )
        return list(result.scalars().all())

    async def create_result(self, payload: EvaluationResultCreate) -> EvaluationResult:
        existing = await self.get_result(str(payload.evaluation_result_id))
        if existing is not None:
            return existing

        evaluation_result = EvaluationResult(
            evaluation_result_id=str(payload.evaluation_result_id),
            evaluation_run_id=str(payload.evaluation_run_id),
            workflow_id=str(payload.workflow_id),
            agent_execution_id=str(payload.agent_execution_id) if payload.agent_execution_id else None,
            prompt_id=payload.prompt_id,
            prompt_version=payload.prompt_version,
            model_name=payload.model_name,
            evaluator_id=payload.evaluator_id,
            evaluator_version=payload.evaluator_version,
            score_name=payload.score_name,
            score_value=payload.score_value,
            score_status=payload.score_status,
            severity=payload.severity,
            rationale=payload.rationale,
            result_metadata=payload.result_metadata,
        )
        self.session.add(evaluation_result)
        await self.session.flush()
        await self.session.refresh(evaluation_result)
        return evaluation_result

    async def get_result(self, evaluation_result_id: str) -> EvaluationResult | None:
        return await self.session.get(EvaluationResult, evaluation_result_id)

    async def list_results_for_run(self, evaluation_run_id: str) -> list[EvaluationResult]:
        result = await self.session.execute(
            select(EvaluationResult)
            .where(EvaluationResult.evaluation_run_id == evaluation_run_id)
            .order_by(EvaluationResult.created_at.asc(), EvaluationResult.evaluation_result_id.asc())
        )
        return list(result.scalars().all())

    async def create_dataset_case(self, payload: EvaluationDatasetCaseCreate) -> EvaluationDatasetCase:
        existing = await self.get_dataset_case(payload.dataset_case_id)
        if existing is not None:
            return existing

        dataset_case = EvaluationDatasetCase(
            dataset_case_id=payload.dataset_case_id,
            dataset_id=payload.dataset_id,
            case_name=payload.case_name,
            workflow_type=payload.workflow_type,
            expected_agents=payload.expected_agents,
            expected_tools=payload.expected_tools,
            expected_human_review=payload.expected_human_review,
            expected_decision=payload.expected_decision,
            expected_signals=payload.expected_signals,
            case_metadata=payload.case_metadata,
        )
        self.session.add(dataset_case)
        await self.session.flush()
        await self.session.refresh(dataset_case)
        return dataset_case

    async def get_dataset_case(self, dataset_case_id: str) -> EvaluationDatasetCase | None:
        return await self.session.get(EvaluationDatasetCase, dataset_case_id)

    async def list_dataset_cases(self, dataset_id: str | None = None) -> list[EvaluationDatasetCase]:
        statement = select(EvaluationDatasetCase)
        if dataset_id is not None:
            statement = statement.where(EvaluationDatasetCase.dataset_id == dataset_id)
        statement = statement.order_by(EvaluationDatasetCase.dataset_id.asc(), EvaluationDatasetCase.case_name.asc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_workflow(self, workflow_id: str) -> WorkflowRecord | None:
        return await self.session.get(WorkflowRecord, workflow_id)

    async def list_agent_executions_for_workflow(self, workflow_id: str) -> list[AgentExecutionRecord]:
        result = await self.session.execute(
            select(AgentExecutionRecord)
            .where(AgentExecutionRecord.workflow_id == workflow_id)
            .order_by(AgentExecutionRecord.started_at.asc(), AgentExecutionRecord.agent_execution_id.asc())
        )
        return list(result.scalars().all())

    async def list_tool_invocations_for_workflow(self, workflow_id: str) -> list[ToolInvocationRecord]:
        result = await self.session.execute(
            select(ToolInvocationRecord)
            .where(ToolInvocationRecord.workflow_id == workflow_id)
            .order_by(ToolInvocationRecord.started_at.asc(), ToolInvocationRecord.tool_invocation_id.asc())
        )
        return list(result.scalars().all())

    async def list_timeline_entries_for_workflow(self, workflow_id: str) -> list[WorkflowTimelineEntry]:
        result = await self.session.execute(
            select(WorkflowTimelineEntry)
            .where(WorkflowTimelineEntry.workflow_id == workflow_id)
            .order_by(WorkflowTimelineEntry.created_at.asc(), WorkflowTimelineEntry.timeline_entry_id.asc())
        )
        return list(result.scalars().all())

    async def list_approval_records_for_workflow(self, workflow_id: str) -> list[ApprovalRecord]:
        result = await self.session.execute(
            select(ApprovalRecord)
            .where(ApprovalRecord.workflow_id == workflow_id)
            .order_by(ApprovalRecord.reviewed_at.asc(), ApprovalRecord.approval_id.asc())
        )
        return list(result.scalars().all())
