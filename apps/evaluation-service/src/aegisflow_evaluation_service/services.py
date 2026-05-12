from aegisflow_evaluation_service.repository import EvaluationRepository
from aegisflow_evaluation_service.schemas import (
    EvaluationDatasetCaseCreate,
    EvaluationResultCreate,
    EvaluationRunCreate,
)


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
