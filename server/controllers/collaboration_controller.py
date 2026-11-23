"""Controllers for expert search, contracts, and assigned tasks."""

from __future__ import annotations

from app.services.contract_service import ContractResult, ContractService
from app.services.expert_search_service import ExpertSearchService, SearchResult
from app.services.task_service import TaskResult, TaskService


class ExpertSearchController:
    def __init__(self, service: ExpertSearchService | None = None) -> None:
        self._service = service if service is not None else ExpertSearchService()

    def search(
        self,
        specialization: str = "",
        availability: str | None = None,
        min_rate: float | None = None,
        max_rate: float | None = None,
        verified_only: bool = False,
    ) -> SearchResult:
        return self._service.search(
            specialization, availability, min_rate, max_rate, verified_only
        )


class ContractController:
    def __init__(self, service: ContractService | None = None) -> None:
        self._service = service if service is not None else ContractService()

    def invite_expert(
        self, expert_profile_id: int, notes: str = "", end_date: str = ""
    ) -> ContractResult:
        return self._service.invite_expert(expert_profile_id, notes, end_date)

    def accept_contract(self, contract_id: int) -> ContractResult:
        return self._service.accept_contract(contract_id)

    def reject_contract(self, contract_id: int, reason: str = "") -> ContractResult:
        return self._service.reject_contract(contract_id, reason)

    def cancel_pending_contract(self, contract_id: int) -> ContractResult:
        return self._service.cancel_pending_contract(contract_id)

    def complete_contract(self, contract_id: int) -> ContractResult:
        return self._service.complete_contract(contract_id)

    def terminate_contract(
        self, contract_id: int, reason: str = ""
    ) -> ContractResult:
        return self._service.terminate_contract(contract_id, reason)

    def list_my_contracts(
        self, status_filter: str | None = None
    ) -> ContractResult:
        return self._service.list_my_contracts(status_filter)


class TaskController:
    def __init__(self, service: TaskService | None = None) -> None:
        self._service = service if service is not None else TaskService()

    def create_task(
        self,
        contract_id: int,
        title: str,
        task_type: str,
        description: str = "",
        priority: str = "normal",
        due_at: str = "",
        exam_session_id: int | None = None,
        interview_id: int | None = None,
    ) -> TaskResult:
        return self._service.create_task(
            contract_id,
            title,
            task_type,
            description,
            priority,
            due_at,
            exam_session_id,
            interview_id,
        )

    def start_task(self, task_id: int) -> TaskResult:
        return self._service.start_task(task_id)

    def complete_task(self, task_id: int) -> TaskResult:
        return self._service.complete_task(task_id)

    def cancel_task(self, task_id: int) -> TaskResult:
        return self._service.cancel_task(task_id)

    def list_my_tasks(
        self,
        status_filter: str | None = None,
        contract_id: int | None = None,
    ) -> TaskResult:
        return self._service.list_my_tasks(status_filter, contract_id)
