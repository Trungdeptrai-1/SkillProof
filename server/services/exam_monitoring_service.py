"""Basic exam event intake with conservative, non-accusatory policies."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Protocol

from app.services.auth_service import SessionManager
from server.services.workflow_result import Record, WorkflowResult

logger = logging.getLogger(__name__)

MONITOR_EVENTS = frozenset({"focus_lost", "camera_unavailable", "timeout"})
FOCUS_REVIEW_THRESHOLD = 3


class ExamMonitoringModel(Protocol):
    def get_candidate_session(self, session_id: int, candidate_id: int) -> Record | None: ...

    def record_candidate_monitor_event(
        self,
        session_id: int,
        candidate_id: int,
        event_type: str,
        *,
        timeout_verified: bool,
        focus_review_threshold: int,
    ) -> Record | None: ...

    def can_review_monitor_events(
        self, reviewer_id: int, role: str, session_id: int
    ) -> bool: ...

    def list_monitor_events_for_reviewer(
        self, reviewer_id: int, role: str, session_id: int
    ) -> tuple[Record, ...]: ...


class ExamMonitoringService:
    SUCCESS = "success"
    NOT_LOGGED_IN = "not_logged_in"
    WRONG_ROLE = "wrong_role"
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    SESSION_NOT_ACTIVE = "session_not_active"
    TIMEOUT_NOT_VERIFIED = "timeout_not_verified"
    DB_ERROR = "db_error"

    _MESSAGES = {
        SUCCESS: "Sự kiện đã được ghi nhận.",
        NOT_LOGGED_IN: "Vui lòng đăng nhập trước.",
        WRONG_ROLE: "Bạn không có quyền thực hiện thao tác này.",
        INVALID_INPUT: "Dữ liệu sự kiện không hợp lệ.",
        NOT_FOUND: "Không tìm thấy phiên thi.",
        FORBIDDEN: "Bạn không có quyền xem nhật ký phiên thi này.",
        SESSION_NOT_ACTIVE: "Phiên thi không còn hoạt động.",
        TIMEOUT_NOT_VERIFIED: "Chưa xác nhận được phiên thi đã hết giờ.",
        DB_ERROR: "Lỗi dữ liệu giám sát. Vui lòng thử lại.",
    }

    def __init__(self, model: ExamMonitoringModel) -> None:
        self._model = model

    @classmethod
    def _result(
        cls, status: str, *, record: Record | None = None, records=(), value=None
    ) -> WorkflowResult:
        return WorkflowResult(
            status, cls._MESSAGES[status], record=record, records=records, value=value
        )

    @staticmethod
    def _identity(roles: set[str]) -> tuple[int, str] | WorkflowResult:
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return WorkflowResult(
                ExamMonitoringService.NOT_LOGGED_IN,
                ExamMonitoringService._MESSAGES[ExamMonitoringService.NOT_LOGGED_IN],
            )
        if session.current_user.role not in roles:
            return WorkflowResult(
                ExamMonitoringService.WRONG_ROLE,
                ExamMonitoringService._MESSAGES[ExamMonitoringService.WRONG_ROLE],
            )
        return session.current_user.id, session.current_user.role

    @staticmethod
    def _valid_id(value: int) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    @staticmethod
    def _expired(session: Record) -> bool | None:
        started = session.get("started_at")
        duration = session.get("duration_min")
        if (
            not isinstance(started, str)
            or not isinstance(duration, int)
            or isinstance(duration, bool)
            or duration <= 0
        ):
            return None
        try:
            start_time = datetime.fromisoformat(started)
        except ValueError:
            return None
        return (datetime.now(start_time.tzinfo) - start_time).total_seconds() >= duration * 60

    def record_event(self, session_id: int, event_type: str) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if (
            not self._valid_id(session_id)
            or not isinstance(event_type, str)
            or event_type not in MONITOR_EVENTS
        ):
            return self._result(self.INVALID_INPUT)
        timeout_verified = False
        try:
            session = self._model.get_candidate_session(session_id, identity[0])
            if session is None:
                return self._result(self.NOT_FOUND)
            if session.get("status") != "in_progress":
                return self._result(self.SESSION_NOT_ACTIVE)
            if event_type == "timeout":
                expired = self._expired(session)
                if expired is not True:
                    return self._result(self.TIMEOUT_NOT_VERIFIED)
                timeout_verified = True
            record = self._model.record_candidate_monitor_event(
                session_id,
                identity[0],
                event_type,
                timeout_verified=timeout_verified,
                focus_review_threshold=FOCUS_REVIEW_THRESHOLD,
            )
        except sqlite3.Error:
            logger.exception("Could not record exam monitoring event")
            return self._result(self.DB_ERROR)
        if record is None:
            return self._result(self.SESSION_NOT_ACTIVE)
        outcome = record.get("outcome")
        if event_type == "focus_lost":
            focus_count = record.get("focus_event_count")
            expected_outcome = (
                "manual_review_required"
                if isinstance(focus_count, int)
                and not isinstance(focus_count, bool)
                and focus_count >= FOCUS_REVIEW_THRESHOLD
                else "warning"
            )
        elif event_type == "camera_unavailable":
            expected_outcome = "technical_warning"
        else:
            expected_outcome = "timeout_recorded"
        if not isinstance(outcome, str) or outcome != expected_outcome:
            logger.error("Monitoring repository returned an invalid event outcome")
            return self._result(self.DB_ERROR)
        # A focus signal can request human review; it is never a finding of cheating.
        return self._result(self.SUCCESS, record=record, value=outcome)

    def list_events(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"company", "expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            if not self._model.can_review_monitor_events(
                identity[0], identity[1], session_id
            ):
                return self._result(self.FORBIDDEN)
            records = self._model.list_monitor_events_for_reviewer(
                identity[0], identity[1], session_id
            )
        except sqlite3.Error:
            logger.exception("Could not load exam monitoring events")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, records=records)
