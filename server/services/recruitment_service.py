"""Company job-posting workflows pending the recruitment data model."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Protocol

from app.services.auth_service import SessionManager

logger = logging.getLogger(__name__)

Record = Mapping[str, object]
JOB_POSTING_STATUSES = ("draft", "published", "closed")


class RecruitmentModel(Protocol):
    """Persistence contract required from the recruitment Model layer."""

    def create_job_posting(
        self,
        company_id: int,
        *,
        title: str,
        description: str,
        requirements: str,
        location: str,
        status: str,
    ) -> Record | None: ...

    def update_job_posting(
        self,
        company_id: int,
        position_id: int,
        *,
        title: str,
        description: str,
        requirements: str,
        location: str,
        status: str,
    ) -> Record | None: ...

    def get_job_posting(
        self, company_id: int, position_id: int
    ) -> Record | None: ...

    def list_job_postings(self, company_id: int) -> Sequence[Record]: ...

    def list_candidates(
        self, company_id: int, search: str = ""
    ) -> Sequence[Record]: ...


class RecruitmentResult:
    SUCCESS = "success"
    NOT_LOGGED_IN = "not_logged_in"
    WRONG_ROLE = "wrong_role"
    INVALID_INPUT = "invalid_input"
    INVALID_STATUS = "invalid_status"
    EMPTY_TITLE = "empty_title"
    POSITION_NOT_FOUND = "position_not_found"
    DB_ERROR = "db_error"

    MESSAGES = {
        SUCCESS: "Thao tác thành công.",
        NOT_LOGGED_IN: "Vui lòng đăng nhập trước.",
        WRONG_ROLE: "Chức năng này chỉ dành cho tài khoản doanh nghiệp.",
        INVALID_INPUT: "Dữ liệu đầu vào không hợp lệ.",
        INVALID_STATUS: "Trạng thái vị trí tuyển dụng không hợp lệ.",
        EMPTY_TITLE: "Tiêu đề vị trí không được để trống.",
        POSITION_NOT_FOUND: "Không tìm thấy vị trí tuyển dụng.",
        DB_ERROR: "Lỗi dữ liệu tuyển dụng. Vui lòng thử lại.",
    }

    def __init__(
        self,
        status: str,
        *,
        position: Record | None = None,
        positions: Sequence[Record] | None = None,
        candidates: Sequence[Record] | None = None,
    ) -> None:
        self.status = status
        self.position = position
        self.positions = list(positions) if positions is not None else []
        self.candidates = list(candidates) if candidates is not None else []
        self.success = status == self.SUCCESS
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")


class RecruitmentService:
    """Validate company requests and scope all position access to that company."""

    def __init__(self, model: RecruitmentModel) -> None:
        self._model = model

    @staticmethod
    def _company_id() -> int | RecruitmentResult:
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return RecruitmentResult(RecruitmentResult.NOT_LOGGED_IN)
        if session.current_user.role != "company":
            return RecruitmentResult(RecruitmentResult.WRONG_ROLE)
        return session.current_user.id

    @staticmethod
    def _valid_id(value: int) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    @staticmethod
    def _validate_position(
        title: str,
        description: str,
        requirements: str,
        location: str,
        status: str,
    ) -> RecruitmentResult | None:
        if not all(
            isinstance(value, str)
            for value in (title, description, requirements, location, status)
        ):
            return RecruitmentResult(RecruitmentResult.INVALID_INPUT)
        if not title.strip():
            return RecruitmentResult(RecruitmentResult.EMPTY_TITLE)
        if status not in JOB_POSTING_STATUSES:
            return RecruitmentResult(RecruitmentResult.INVALID_STATUS)
        return None

    def create_position(
        self,
        title: str,
        description: str = "",
        requirements: str = "",
        location: str = "",
        status: str = "draft",
    ) -> RecruitmentResult:
        company_id = self._company_id()
        if isinstance(company_id, RecruitmentResult):
            return company_id
        invalid = self._validate_position(
            title, description, requirements, location, status
        )
        if invalid:
            return invalid

        try:
            position = self._model.create_job_posting(
                company_id,
                title=title.strip(),
                description=description.strip(),
                requirements=requirements.strip(),
                location=location.strip(),
                status=status,
            )
        except sqlite3.Error as exc:
            logger.error("Database error creating job posting: %s", exc)
            return RecruitmentResult(RecruitmentResult.DB_ERROR)
        if position is None:
            return RecruitmentResult(RecruitmentResult.DB_ERROR)
        return RecruitmentResult(RecruitmentResult.SUCCESS, position=position)

    def update_position(
        self,
        position_id: int,
        title: str,
        description: str = "",
        requirements: str = "",
        location: str = "",
        status: str | None = None,
    ) -> RecruitmentResult:
        company_id = self._company_id()
        if isinstance(company_id, RecruitmentResult):
            return company_id
        if not self._valid_id(position_id):
            return RecruitmentResult(RecruitmentResult.INVALID_INPUT)
        try:
            existing = self._model.get_job_posting(company_id, position_id)
        except sqlite3.Error as exc:
            logger.error("Database error retrieving job posting for update: %s", exc)
            return RecruitmentResult(RecruitmentResult.DB_ERROR)
        if existing is None:
            return RecruitmentResult(RecruitmentResult.POSITION_NOT_FOUND)
        current_status = existing.get("status")
        if status is None:
            if not isinstance(current_status, str):
                return RecruitmentResult(RecruitmentResult.DB_ERROR)
            status = current_status
        invalid = self._validate_position(
            title, description, requirements, location, status
        )
        if invalid:
            return invalid

        try:
            position = self._model.update_job_posting(
                company_id,
                position_id,
                title=title.strip(),
                description=description.strip(),
                requirements=requirements.strip(),
                location=location.strip(),
                status=status,
            )
        except sqlite3.Error as exc:
            logger.error("Database error updating job posting: %s", exc)
            return RecruitmentResult(RecruitmentResult.DB_ERROR)
        if position is None:
            return RecruitmentResult(RecruitmentResult.POSITION_NOT_FOUND)
        return RecruitmentResult(RecruitmentResult.SUCCESS, position=position)

    def get_position(self, position_id: int) -> RecruitmentResult:
        company_id = self._company_id()
        if isinstance(company_id, RecruitmentResult):
            return company_id
        if not self._valid_id(position_id):
            return RecruitmentResult(RecruitmentResult.INVALID_INPUT)

        try:
            position = self._model.get_job_posting(company_id, position_id)
        except sqlite3.Error as exc:
            logger.error("Database error retrieving job posting: %s", exc)
            return RecruitmentResult(RecruitmentResult.DB_ERROR)
        if position is None:
            return RecruitmentResult(RecruitmentResult.POSITION_NOT_FOUND)
        return RecruitmentResult(RecruitmentResult.SUCCESS, position=position)

    def list_positions(self) -> RecruitmentResult:
        company_id = self._company_id()
        if isinstance(company_id, RecruitmentResult):
            return company_id
        try:
            positions = self._model.list_job_postings(company_id)
        except sqlite3.Error as exc:
            logger.error("Database error listing job postings: %s", exc)
            return RecruitmentResult(RecruitmentResult.DB_ERROR)
        return RecruitmentResult(
            RecruitmentResult.SUCCESS,
            positions=positions,
        )

    def list_candidates(self, search: str = "") -> RecruitmentResult:
        company_id = self._company_id()
        if isinstance(company_id, RecruitmentResult):
            return company_id
        if not isinstance(search, str):
            return RecruitmentResult(RecruitmentResult.INVALID_INPUT)
        try:
            candidates = self._model.list_candidates(company_id, search.strip())
        except sqlite3.Error as exc:
            logger.error("Database error listing candidates: %s", exc)
            return RecruitmentResult(RecruitmentResult.DB_ERROR)
        return RecruitmentResult(
            RecruitmentResult.SUCCESS,
            candidates=candidates,
        )
