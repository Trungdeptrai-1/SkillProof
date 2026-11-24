"""Consent-aware exam monitoring and human review workflows."""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import urlsplit

from app.services.auth_service import SessionManager
from server.models.recruitment_models import (
    ExamProctoringSessionModel,
    ExamSessionEventModel,
)
from server.services.workflow_result import Record, WorkflowResult

logger = logging.getLogger(__name__)

CAMERA_EVENTS = frozenset({"camera_active", "camera_disconnected", "camera_ended"})
MONITOR_EVENTS = CAMERA_EVENTS | {"focus_lost", "timeout"}
REVIEW_STATUSES = frozenset({"reviewed", "dismissed", "escalated"})


class ExamMonitoringModel(Protocol):
    def list_candidate_invitations(self, candidate_id: int) -> Sequence[Record]: ...

    """Persistence contract implemented by RecruitmentRepository."""

    def get_candidate_session(self, session_id: int, candidate_id: int) -> Record | None: ...

    def start_exam_proctoring_session(
        self, session_id: int, candidate_id: int, *, consent_for_evidence: bool = False
    ) -> ExamProctoringSessionModel | None: ...

    def get_exam_proctoring_session(
        self, session_id: int, candidate_id: int
    ) -> ExamProctoringSessionModel | None: ...

    def finish_exam_proctoring_session(
        self, session_id: int, candidate_id: int
    ) -> ExamProctoringSessionModel | None: ...

    def record_exam_session_event(
        self,
        session_id: int,
        candidate_id: int,
        event_type: str,
        *,
        is_violation: bool = False,
        details: Mapping[str, object] | None = None,
        evidence_uri: str | None = None,
    ) -> ExamSessionEventModel: ...

    def list_exam_session_events(
        self, session_id: int, candidate_id: int, *, violations_only: bool = False
    ) -> Sequence[ExamSessionEventModel]: ...

    def get_exam_session_context(self, session_id: int) -> Record | None: ...

    def get_company_exam_proctoring_session(
        self, company_id: int, session_id: int, *, requester_id: int | None = None
    ) -> ExamProctoringSessionModel | None: ...

    def list_company_exam_session_events(
        self,
        company_id: int,
        session_id: int,
        *,
        requester_id: int | None = None,
        violations_only: bool = False,
        processing_status: str | None = None,
    ) -> Sequence[ExamSessionEventModel]: ...

    def review_exam_session_event(
        self,
        company_id: int,
        reviewer_id: int,
        event_id: int,
        *,
        processing_status: str,
        notes: str | None = None,
    ) -> ExamSessionEventModel | None: ...


class ExamMonitoringService:
    SUCCESS = "success"
    NOT_LOGGED_IN = "not_logged_in"
    WRONG_ROLE = "wrong_role"
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    EXAM_NOT_ACTIVE = "exam_not_active"
    MONITOR_NOT_ACTIVE = "monitor_not_active"
    ALREADY_FINISHED = "already_finished"
    CONSENT_REQUIRED = "consent_required"
    TIMEOUT_NOT_VERIFIED = "timeout_not_verified"
    DB_ERROR = "db_error"

    _MESSAGES = {
        SUCCESS: "Thao tác thành công.",
        NOT_LOGGED_IN: "Vui lòng đăng nhập trước.",
        WRONG_ROLE: "Bạn không có quyền thực hiện thao tác này.",
        INVALID_INPUT: "Dữ liệu giám sát không hợp lệ.",
        NOT_FOUND: "Không tìm thấy phiên giám sát.",
        FORBIDDEN: "Bạn không có quyền truy cập bằng chứng hoặc sự kiện này.",
        EXAM_NOT_ACTIVE: "Ứng viên không có phiên thi đang hoạt động.",
        MONITOR_NOT_ACTIVE: "Phiên giám sát chưa được khởi tạo hoặc đã kết thúc.",
        ALREADY_FINISHED: "Phiên giám sát đã kết thúc.",
        CONSENT_REQUIRED: "Cần có sự đồng ý rõ ràng trước khi gắn bằng chứng.",
        TIMEOUT_NOT_VERIFIED: "Thời hạn thi chưa được xác nhận là đã hết.",
        DB_ERROR: "Lỗi dữ liệu giám sát. Vui lòng thử lại.",
    }

    def __init__(
        self,
        model: ExamMonitoringModel,
        *,
        focus_review_threshold: int = 3,
    ) -> None:
        if (
            isinstance(focus_review_threshold, bool)
            or not isinstance(focus_review_threshold, int)
            or focus_review_threshold < 1
        ):
            raise ValueError("focus_review_threshold must be a positive integer")
        self._model = model
        self._focus_review_threshold = focus_review_threshold

    @classmethod
    def _result(
        cls,
        status: str,
        *,
        record: Record | None = None,
        records: Sequence[Record] = (),
        value: object | None = None,
        message: str | None = None,
    ) -> WorkflowResult:
        return WorkflowResult(
            status,
            message or cls._MESSAGES[status],
            record=record,
            records=records,
            value=value,
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
    def _record(value: object) -> Record | None:
        if isinstance(value, Mapping):
            return dict(value)
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        return None

    @staticmethod
    def _session_expired(session: Record) -> bool | None:
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
        now = datetime.now(start_time.tzinfo) if start_time.tzinfo else datetime.now()
        return (now - start_time).total_seconds() >= duration * 60

    def get_active_exam_session(self) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        try:
            invitations = self._model.list_candidate_invitations(identity[0])
            for invitation in invitations:
                session_id = invitation.get("exam_session_id")
                if (
                    invitation.get("status") != "accepted"
                    or invitation.get("session_status") != "in_progress"
                    or not self._valid_id(session_id)
                ):
                    continue
                exam = self._model.get_candidate_session(session_id, identity[0])
                if exam is None or exam.get("status") != "in_progress":
                    continue
                started = exam.get("started_at")
                duration = exam.get("duration_min")
                if (
                    not isinstance(started, str)
                    or not isinstance(duration, int)
                    or isinstance(duration, bool)
                    or duration <= 0
                ):
                    continue
                try:
                    start_time = datetime.fromisoformat(started)
                except ValueError:
                    continue
                now = datetime.now(start_time.tzinfo) if start_time.tzinfo else datetime.now()
                remaining = max(
                    0, duration * 60 - int((now - start_time).total_seconds())
                )
                return self._result(
                    self.SUCCESS,
                    record={
                        "session_id": session_id,
                        "title": str(invitation.get("exam_title") or ""),
                        "status": "in_progress",
                        "remaining_seconds": remaining,
                    },
                )
        except sqlite3.Error:
            logger.exception("Could not resolve candidate active exam session")
            return self._result(self.DB_ERROR)
        return self._result(self.EXAM_NOT_ACTIVE)

    @staticmethod
    def _valid_evidence_uri(value: str) -> bool:
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        return (
            parsed.scheme in {"evidence", "https"}
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
        )

    @staticmethod
    def _valid_details(details: Mapping[str, object] | None) -> bool:
        if details is None:
            return True
        if not isinstance(details, Mapping) or len(details) > 20:
            return False
        allowed_keys = {
            "source",
            "state",
            "camera_state",
            "visibility",
            "count",
            "focus_count",
            "elapsed_seconds",
        }
        if any(
            not isinstance(key, str)
            or key.lower() not in allowed_keys
            or not isinstance(value, (str, int, float, bool, type(None)))
            or (isinstance(value, float) and not math.isfinite(value))
            or (isinstance(value, str) and len(value) > 500)
            for key, value in details.items()
        ):
            return False
        try:
            return len(json.dumps(dict(details), ensure_ascii=False)) <= 2_000
        except (TypeError, ValueError):
            return False

    def start_session(
        self, session_id: int, *, consent_for_evidence: bool = False
    ) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id) or not isinstance(consent_for_evidence, bool):
            return self._result(self.INVALID_INPUT)
        try:
            exam = self._model.get_candidate_session(session_id, identity[0])
            if exam is None:
                return self._result(self.NOT_FOUND)
            if exam.get("status") != "in_progress":
                return self._result(self.EXAM_NOT_ACTIVE)
            session = self._record(
                self._model.start_exam_proctoring_session(
                    session_id,
                    identity[0],
                    consent_for_evidence=consent_for_evidence,
                )
            )
        except sqlite3.Error:
            logger.exception("Could not start exam monitoring")
            return self._result(self.DB_ERROR)
        if session is None:
            return self._result(self.EXAM_NOT_ACTIVE)
        if session.get("status") != "active":
            return self._result(self.ALREADY_FINISHED, record=session)
        return self._result(self.SUCCESS, record=session)

    def get_session(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            session = self._record(
                self._model.get_exam_proctoring_session(session_id, identity[0])
            )
        except sqlite3.Error:
            logger.exception("Could not load candidate monitoring session")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=session) if session else self._result(self.NOT_FOUND)

    def finish_session(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            session = self._record(
                self._model.finish_exam_proctoring_session(session_id, identity[0])
            )
        except sqlite3.Error:
            logger.exception("Could not finish exam monitoring")
            return self._result(self.DB_ERROR)
        if session is None:
            return self._result(self.ALREADY_FINISHED)
        return self._result(self.SUCCESS, record=session)

    def record_event(
        self,
        session_id: int,
        event_type: str,
        *,
        details: Mapping[str, object] | None = None,
        evidence_uri: str | None = None,
    ) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if (
            not self._valid_id(session_id)
            or not isinstance(event_type, str)
            or event_type not in MONITOR_EVENTS
            or not self._valid_details(details)
            or (
                evidence_uri is not None
                and (
                    not isinstance(evidence_uri, str)
                    or not evidence_uri.strip()
                    or not self._valid_evidence_uri(evidence_uri.strip())
                )
            )
        ):
            return self._result(self.INVALID_INPUT)
        try:
            exam = self._model.get_candidate_session(session_id, identity[0])
            if exam is None:
                return self._result(self.NOT_FOUND)
            if exam.get("status") != "in_progress":
                return self._result(self.EXAM_NOT_ACTIVE)
            session = self._record(
                self._model.get_exam_proctoring_session(session_id, identity[0])
            )
            if session is None or session.get("status") != "active":
                return self._result(self.MONITOR_NOT_ACTIVE)
            if evidence_uri is not None and not session.get("consent_for_evidence"):
                return self._result(self.CONSENT_REQUIRED)
            if event_type == "timeout" and self._session_expired(exam) is not True:
                return self._result(self.TIMEOUT_NOT_VERIFIED)

            focus_count = 0
            if event_type == "focus_lost":
                previous_events = self._model.list_exam_session_events(
                    session_id, identity[0]
                )
                focus_count = sum(
                    1
                    for item in previous_events
                    if getattr(item, "event_type", None) == "focus_lost"
                    or (
                        isinstance(item, Mapping)
                        and item.get("event_type") == "focus_lost"
                    )
                )
            is_violation = (
                event_type == "focus_lost"
                and focus_count + 1 >= self._focus_review_threshold
            )
            event = self._record(
                self._model.record_exam_session_event(
                    session_id,
                    identity[0],
                    event_type,
                    is_violation=is_violation,
                    details=dict(details) if details is not None else None,
                    evidence_uri=evidence_uri.strip() if evidence_uri else None,
                )
            )
        except sqlite3.Error:
            logger.exception("Could not record exam monitoring event")
            return self._result(self.DB_ERROR)
        if event is None:
            return self._result(self.DB_ERROR)
        if event_type == "focus_lost":
            count = focus_count + 1
            outcome = (
                "manual_review_required"
                if is_violation
                else "warning"
            )
        elif event_type == "camera_disconnected":
            count = focus_count
            outcome = "technical_warning"
        elif event_type == "timeout":
            count = focus_count
            outcome = "timeout_recorded"
        else:
            count = focus_count
            outcome = "camera_status_updated"
        if outcome == "warning":
            message = (
                f"Cảnh báo focus {count}/{self._focus_review_threshold}; "
                "sự kiện chưa xác nhận gian lận."
            )
        elif outcome == "manual_review_required":
            message = (
                "Đã đạt ngưỡng focus; cần người có quyền rà soát, "
                "không tự động kết luận gian lận hoặc hủy bài."
            )
        elif outcome == "technical_warning":
            message = "Camera bị ngắt; đây là cảnh báo kỹ thuật, không phải vi phạm."
        elif outcome == "timeout_recorded":
            message = "Đã ghi nhận hết giờ theo thời gian phiên thi."
        else:
            message = "Đã ghi nhận trạng thái camera."
        return self._result(
            self.SUCCESS,
            record=event,
            value={"outcome": outcome, "focus_event_count": count},
            message=message,
        )

    def list_events(
        self, session_id: int, *, violations_only: bool = False
    ) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id) or not isinstance(violations_only, bool):
            return self._result(self.INVALID_INPUT)
        try:
            events = self._model.list_exam_session_events(
                session_id, identity[0], violations_only=violations_only
            )
        except sqlite3.Error:
            logger.exception("Could not load candidate monitoring events")
            return self._result(self.DB_ERROR)
        return self._result(
            self.SUCCESS,
            records=tuple(
                record
                for event in events
                if (record := self._record(event)) is not None
            ),
        )

    def get_company_session(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"company", "expert", "admin"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            context = self._model.get_exam_session_context(session_id)
            company_id = context.get("company_id") if context else None
            if not self._valid_id(company_id):
                return self._result(self.NOT_FOUND)
            session = self._record(
                self._model.get_company_exam_proctoring_session(
                    company_id, session_id, requester_id=identity[0]
                )
            )
        except sqlite3.Error:
            logger.exception("Could not load reviewer monitoring session")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=session) if session else self._result(self.FORBIDDEN)

    def list_company_events(
        self,
        session_id: int,
        *,
        violations_only: bool = False,
        processing_status: str | None = None,
    ) -> WorkflowResult:
        identity = self._identity({"company", "expert", "admin"})
        if isinstance(identity, WorkflowResult):
            return identity
        if (
            not self._valid_id(session_id)
            or not isinstance(violations_only, bool)
            or (
                processing_status is not None
                and (
                    not isinstance(processing_status, str)
                    or processing_status not in {"pending", *REVIEW_STATUSES}
                )
            )
        ):
            return self._result(self.INVALID_INPUT)
        try:
            context = self._model.get_exam_session_context(session_id)
            company_id = context.get("company_id") if context else None
            if not self._valid_id(company_id):
                return self._result(self.NOT_FOUND)
            if self._model.get_company_exam_proctoring_session(
                company_id, session_id, requester_id=identity[0]
            ) is None:
                return self._result(self.FORBIDDEN)
            events = self._model.list_company_exam_session_events(
                company_id,
                session_id,
                requester_id=identity[0],
                violations_only=violations_only,
                processing_status=processing_status,
            )
        except sqlite3.Error:
            logger.exception("Could not list reviewer monitoring events")
            return self._result(self.DB_ERROR)
        return self._result(
            self.SUCCESS,
            records=tuple(
                record
                for event in events
                if (record := self._record(event)) is not None
            ),
        )

    def review_event(
        self,
        session_id: int,
        event_id: int,
        processing_status: str,
        *,
        notes: str | None = None,
    ) -> WorkflowResult:
        identity = self._identity({"company", "expert", "admin"})
        if isinstance(identity, WorkflowResult):
            return identity
        if (
            not self._valid_id(session_id)
            or not self._valid_id(event_id)
            or not isinstance(processing_status, str)
            or processing_status not in REVIEW_STATUSES
            or (notes is not None and (not isinstance(notes, str) or len(notes) > 8_000))
        ):
            return self._result(self.INVALID_INPUT)
        try:
            context = self._model.get_exam_session_context(session_id)
            company_id = context.get("company_id") if context else None
            if not self._valid_id(company_id):
                return self._result(self.NOT_FOUND)
            if self._model.get_company_exam_proctoring_session(
                company_id, session_id, requester_id=identity[0]
            ) is None:
                return self._result(self.FORBIDDEN)
            pending_events = self._model.list_company_exam_session_events(
                company_id,
                session_id,
                requester_id=identity[0],
                processing_status="pending",
            )
            if not any(
                (record := self._record(item)) is not None
                and record.get("id") == event_id
                for item in pending_events
            ):
                return self._result(self.NOT_FOUND)
            event = self._record(
                self._model.review_exam_session_event(
                    company_id,
                    identity[0],
                    event_id,
                    processing_status=processing_status,
                    notes=notes.strip() if notes else None,
                )
            )
        except sqlite3.Error:
            logger.exception("Could not review monitoring event")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=event) if event else self._result(self.NOT_FOUND)
