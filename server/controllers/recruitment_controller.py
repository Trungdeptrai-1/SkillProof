"""Controller for company job-posting requests."""

from __future__ import annotations

from server.services.recruitment_service import RecruitmentResult, RecruitmentService


class RecruitmentController:
    def __init__(self, service: RecruitmentService) -> None:
        self._service = service

    def create_position(
        self,
        title: str,
        description: str = "",
        requirements: str = "",
        location: str = "",
        status: str = "draft",
    ) -> RecruitmentResult:
        if not all(
            isinstance(value, str)
            for value in (title, description, requirements, location, status)
        ):
            return RecruitmentResult(RecruitmentResult.INVALID_INPUT)
        return self._service.create_position(
            title, description, requirements, location, status
        )

    def update_position(
        self,
        position_id: int,
        title: str,
        description: str = "",
        requirements: str = "",
        location: str = "",
        status: str | None = None,
    ) -> RecruitmentResult:
        if (
            isinstance(position_id, bool)
            or not isinstance(position_id, int)
            or (status is not None and not isinstance(status, str))
            or not all(
                isinstance(value, str)
                for value in (title, description, requirements, location)
            )
        ):
            return RecruitmentResult(RecruitmentResult.INVALID_INPUT)
        return self._service.update_position(
            position_id, title, description, requirements, location, status
        )

    def get_position(self, position_id: int) -> RecruitmentResult:
        if isinstance(position_id, bool) or not isinstance(position_id, int):
            return RecruitmentResult(RecruitmentResult.INVALID_INPUT)
        return self._service.get_position(position_id)

    def list_positions(self) -> RecruitmentResult:
        return self._service.list_positions()

    def list_candidates(self, search: str = "") -> RecruitmentResult:
        if not isinstance(search, str):
            return RecruitmentResult(RecruitmentResult.INVALID_INPUT)
        return self._service.list_candidates(search)
