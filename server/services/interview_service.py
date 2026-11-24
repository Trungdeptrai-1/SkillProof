"""Interview scheduling and evaluation workflows."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol
from urllib.parse import urlsplit

from app.services.auth_service import SessionManager
from server.services.workflow_result import Record, WorkflowResult

logger = logging.getLogger(__name__)

INTERVIEW_STATUSES = {
    "scheduled": frozenset({"in_progress", "completed", "cancelled", "no_show"}),
    "in_progress": frozenset({"completed", "cancelled", "no_show"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "no_show": frozenset(),
}
RECOMMENDATIONS = frozenset({"strong_hire", "hire", "no_hire", "strong_no_hire"})


class InterviewModel(Protocol):
    def create_interview(
        self,
        company_id: int,
        candidate_id: int,
        *,
        title: str,
        description: str,
        scheduled_at: str,
        duration_min: int,
        meeting_url: str | None,
        expert_ids: Sequence[int],
    ) -> Record | None: ...

    def list_user_interviews(self, user_id: int, role: str) -> Sequence[Record]: ...

    def get_interview_for_user(
        self, interview_id: int, user_id: int, role: str
    ) -> Record | None: ...

    def update_interview_status(
        self, interview_id: int, user_id: int, role: str, status: str
    ) -> Record | None: ...

    def can_evaluate_interview(self, interview_id: int, expert_id: int) -> bool: ...

    def save_interview_evaluation(
        self,
        interview_id: int,
        expert_id: int,
        *,
        technical_score: int,
        communication_score: int,
        problem_solving_score: int,
        overall_rating: int,
        feedback: str,
        recommendation: str,
    ) -> Record | None: ...

    def list_interview_evaluations(
        self, interview_id: int, user_id: int, role: str
    ) -> Sequence[Record]: ...

    def list_interview_participants(
        self, company_id: int, interview_id: int
    ) -> Sequence[Record]: ...

class InterviewService:
    SUCCESS = "success"
    NOT_LOGGED_IN = "not_logged_in"
    WRONG_ROLE = "wrong_role"
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    INVALID_TRANSITION = "invalid_transition"
    DB_ERROR = "db_error"

    _MESSAGES = {
        SUCCESS: "Thao tác thành công.",
        NOT_LOGGED_IN: "Vui lòng đăng nhập trước.",
        WRONG_ROLE: "Bạn không có quyền thực hiện thao tác này.",
        INVALID_INPUT: "Dữ liệu đầu vào không hợp lệ.",
        NOT_FOUND: "Không tìm thấy buổi phỏng vấn.",
        FORBIDDEN: "Bạn không có quyền truy cập buổi phỏng vấn này.",
        INVALID_TRANSITION: "Chuyển trạng thái phỏng vấn không hợp lệ.",
        DB_ERROR: "Lỗi dữ liệu phỏng vấn. Vui lòng thử lại.",
    }

    def __init__(self, model: InterviewModel) -> None:
        self._model = model

    @classmethod
    def _result(
        cls,
        status: str,
        *,
        record: Record | None = None,
        records: Sequence[Record] = (),
        value: object | None = None,
    ) -> WorkflowResult:
        return WorkflowResult(
            status,
            cls._MESSAGES[status],
            record=record,
            records=records,
            value=value,
        )

    @staticmethod
    def _identity(roles: set[str]) -> tuple[int, str] | WorkflowResult:
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return WorkflowResult(
                InterviewService.NOT_LOGGED_IN,
                InterviewService._MESSAGES[InterviewService.NOT_LOGGED_IN],
            )
        if session.current_user.role not in roles:
            return WorkflowResult(
                InterviewService.WRONG_ROLE,
                InterviewService._MESSAGES[InterviewService.WRONG_ROLE],
            )
        return session.current_user.id, session.current_user.role

    @staticmethod
    def _valid_id(value: int) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    @staticmethod
    def _safe_meeting_url(value: object) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            return None
        try:
            parsed = urlsplit(value.strip())
        except ValueError:
            return None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        return value.strip()

    def schedule(
        self,
        candidate_id: int,
        title: str,
        scheduled_at: str,
        *,
        description: str = "",
        duration_min: int = 60,
        meeting_url: str | None = None,
        expert_ids: Sequence[int] = (),
    ) -> WorkflowResult:
        identity = self._identity({"company"})
        if isinstance(identity, WorkflowResult):
            return identity
        if (
            not self._valid_id(candidate_id)
            or not isinstance(title, str)
            or not title.strip()
            or len(title) > 200
            or not isinstance(description, str)
            or len(description) > 8_000
            or not isinstance(scheduled_at, str)
            or not isinstance(duration_min, int)
            or isinstance(duration_min, bool)
            or not 1 <= duration_min <= 480
            or (
                meeting_url is not None
                and (not isinstance(meeting_url, str) or len(meeting_url) > 2_000)
            )
            or not isinstance(expert_ids, Sequence)
            or isinstance(expert_ids, (str, bytes))
            or any(not self._valid_id(expert_id) for expert_id in expert_ids)
            or len(set(expert_ids)) != len(expert_ids)
        ):
            return self._result(self.INVALID_INPUT)
        try:
            scheduled = datetime.fromisoformat(scheduled_at)
        except ValueError:
            return self._result(self.INVALID_INPUT)
        if scheduled <= datetime.now(scheduled.tzinfo):
            return self._result(self.INVALID_INPUT)
        safe_meeting_url = self._safe_meeting_url(meeting_url)
        if meeting_url and safe_meeting_url is None:
            return self._result(self.INVALID_INPUT)
        try:
            record = self._model.create_interview(
                identity[0],
                candidate_id,
                title=title.strip(),
                description=description.strip(),
                scheduled_at=scheduled.isoformat(),
                duration_min=duration_min,
                meeting_url=safe_meeting_url,
                expert_ids=tuple(expert_ids),
            )
        except sqlite3.Error:
            logger.exception("Could not schedule interview")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.FORBIDDEN)

    def list_mine(self) -> WorkflowResult:
        identity = self._identity({"company", "expert", "candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        try:
            records = self._model.list_user_interviews(*identity)
        except sqlite3.Error:
            logger.exception("Could not list interviews")
            return self._result(self.DB_ERROR)
        sanitized = []
        for item in records:
            if not isinstance(item, Mapping):
                logger.error("Interview repository returned an invalid record")
                return self._result(self.DB_ERROR)
            record = dict(item)
            link = record.get("meeting_url")
            record["meeting_url"] = self._safe_meeting_url(link) or ""
            sanitized.append(record)
        return self._result(self.SUCCESS, records=sanitized)

    def get(self, interview_id: int) -> WorkflowResult:
        identity = self._identity({"company", "expert", "candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(interview_id):
            return self._result(self.INVALID_INPUT)
        try:
            record = self._model.get_interview_for_user(
                interview_id, identity[0], identity[1]
            )
        except sqlite3.Error:
            logger.exception("Could not load interview")
            return self._result(self.DB_ERROR)
        if record is None:
            return self._result(self.NOT_FOUND)
        safe_record = dict(record)
        safe_record["meeting_url"] = self._safe_meeting_url(
            safe_record.get("meeting_url")
        ) or ""
        return self._result(self.SUCCESS, record=safe_record)

    def get_meeting_link(self, interview_id: int) -> WorkflowResult:
        identity = self._identity({"company", "expert", "candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(interview_id):
            return self._result(self.INVALID_INPUT)
        try:
            interview = self._model.get_interview_for_user(
                interview_id, identity[0], identity[1]
            )
        except sqlite3.Error:
            logger.exception("Could not load interview meeting link")
            return self._result(self.DB_ERROR)
        if interview is None:
            return self._result(self.NOT_FOUND)
        link = self._safe_meeting_url(interview.get("meeting_url"))
        if interview.get("meeting_url") and link is None:
            return self._result(self.INVALID_INPUT)
        return self._result(
            self.SUCCESS,
            record={"id": interview_id, "meeting_url": link or ""},
            value=link,
        )

    def list_participants(self, interview_id: int) -> WorkflowResult:
        identity = self._identity({"company"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(interview_id):
            return self._result(self.INVALID_INPUT)
        try:
            if self._model.get_interview_for_user(
                interview_id, identity[0], identity[1]
            ) is None:
                return self._result(self.NOT_FOUND)
            participants = self._model.list_interview_participants(
                identity[0], interview_id
            )
        except sqlite3.Error:
            logger.exception("Could not list interview participants")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, records=participants)

    def update_status(self, interview_id: int, status: str) -> WorkflowResult:
        identity = self._identity({"company", "expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(interview_id) or not isinstance(status, str):
            return self._result(self.INVALID_INPUT)
        try:
            current = self._model.get_interview_for_user(
                interview_id, identity[0], identity[1]
            )
            if current is None:
                return self._result(self.NOT_FOUND)
            current_status = current.get("status")
            if not isinstance(current_status, str) or status not in INTERVIEW_STATUSES.get(
                current_status, frozenset()
            ):
                return self._result(self.INVALID_TRANSITION)
            record = self._model.update_interview_status(
                interview_id, identity[0], identity[1], status
            )
        except sqlite3.Error:
            logger.exception("Could not update interview status")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.FORBIDDEN)

    def evaluate(
        self,
        interview_id: int,
        *,
        technical_score: int,
        communication_score: int,
        problem_solving_score: int,
        overall_rating: int,
        feedback: str = "",
        recommendation: str = "hire",
    ) -> WorkflowResult:
        identity = self._identity({"expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        scores = (
            technical_score,
            communication_score,
            problem_solving_score,
            overall_rating,
        )
        if (
            not self._valid_id(interview_id)
            or any(
                not isinstance(score, int)
                or isinstance(score, bool)
                or not 1 <= score <= 5
                for score in scores
            )
            or not isinstance(feedback, str)
            or len(feedback) > 8_000
            or not isinstance(recommendation, str)
            or recommendation not in RECOMMENDATIONS
        ):
            return self._result(self.INVALID_INPUT)
        try:
            if not self._model.can_evaluate_interview(interview_id, identity[0]):
                return self._result(self.FORBIDDEN)
            record = self._model.save_interview_evaluation(
                interview_id,
                identity[0],
                technical_score=technical_score,
                communication_score=communication_score,
                problem_solving_score=problem_solving_score,
                overall_rating=overall_rating,
                feedback=feedback.strip(),
                recommendation=recommendation,
            )
        except sqlite3.Error:
            logger.exception("Could not save interview evaluation")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.NOT_FOUND)

    def list_evaluations(self, interview_id: int) -> WorkflowResult:
        identity = self._identity({"company", "expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(interview_id):
            return self._result(self.INVALID_INPUT)
        try:
            if self._model.get_interview_for_user(interview_id, *identity) is None:
                return self._result(self.NOT_FOUND)
            records = self._model.list_interview_evaluations(
                interview_id, identity[0], identity[1]
            )
        except sqlite3.Error:
            logger.exception("Could not list interview evaluations")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, records=records)
