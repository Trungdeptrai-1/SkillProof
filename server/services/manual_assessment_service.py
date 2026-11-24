"""Essay and coding-test workflows with human-only grading."""

from __future__ import annotations

import logging
import math
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.services.auth_service import SessionManager
from server.services.workflow_result import Record, WorkflowResult

logger = logging.getLogger(__name__)

MANUAL_QUESTION_TYPES = frozenset({"essay", "coding"})
MAX_RESPONSE_LENGTH = 100_000
MAX_FEEDBACK_LENGTH = 8_000


class ManualAssessmentModel(Protocol):
    """Persistence boundary; repository operations must be atomic and scoped."""

    def create_manual_question(
        self,
        expert_id: int,
        *,
        title: str,
        content: str,
        question_type: str,
        difficulty: str,
        points: float,
        test_cases: str,
        reference_answer: str,
    ) -> Record | None: ...

    def publish_manual_question(self, expert_id: int, question_id: int) -> Record | None: ...

    def attach_manual_question(
        self, company_id: int, exam_id: int, question_id: int, points: float
    ) -> Record | None: ...

    def get_candidate_session(self, session_id: int, candidate_id: int) -> Record | None: ...

    def list_candidate_questions(
        self, session_id: int, candidate_id: int
    ) -> Sequence[Record]: ...

    def save_candidate_response(
        self,
        session_id: int,
        candidate_id: int,
        question_id: int,
        *,
        answer_text: str | None,
        answer_code: str | None,
        programming_language: str | None = None,
    ) -> Record | None: ...

    def submit_manual_session_once(
        self, session_id: int, candidate_id: int
    ) -> Record | None: ...

    def can_grade_session(self, grader_id: int, role: str, session_id: int) -> bool: ...

    def list_manual_submissions_for_grader(
        self, grader_id: int, role: str
    ) -> Sequence[Record]: ...

    def get_manual_submission_for_grader(
        self, session_id: int, grader_id: int, role: str
    ) -> Record | None: ...

    def list_manual_answers_for_grading(
        self, session_id: int, grader_id: int, role: str
    ) -> Sequence[Record]: ...

    def get_manual_answer_for_grading(
        self, session_id: int, question_id: int, grader_id: int, role: str
    ) -> Record | None: ...

    def grade_manual_answer_once(
        self,
        session_id: int,
        question_id: int,
        grader_id: int,
        *,
        score: float,
        feedback: str,
        reason: str,
    ) -> Record | None: ...

    def get_manual_grading_progress(
        self, session_id: int, grader_id: int, role: str
    ) -> Record | None: ...

    def finalize_manual_grading_once(
        self, session_id: int, grader_id: int, role: str
    ) -> Record | None: ...

    def release_manual_result_once(
        self, session_id: int, company_id: int
    ) -> Record | None: ...

    def get_candidate_submission(
        self, session_id: int, candidate_id: int
    ) -> Record | None: ...

    def get_candidate_result(self, session_id: int, candidate_id: int) -> Record | None: ...


class ManualAssessmentService:
    SUCCESS = "success"
    NOT_LOGGED_IN = "not_logged_in"
    WRONG_ROLE = "wrong_role"
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    SESSION_NOT_ACTIVE = "session_not_active"
    SESSION_EXPIRED = "session_expired"
    UNSUPPORTED_QUESTION = "unsupported_question"
    ALREADY_SUBMITTED = "already_submitted"
    RESULT_NOT_RELEASED = "result_not_released"
    GRADING_INCOMPLETE = "grading_incomplete"
    DB_ERROR = "db_error"

    _MESSAGES = {
        SUCCESS: "Thao tác thành công.",
        NOT_LOGGED_IN: "Vui lòng đăng nhập trước.",
        WRONG_ROLE: "Bạn không có quyền thực hiện thao tác này.",
        INVALID_INPUT: "Dữ liệu đầu vào không hợp lệ.",
        NOT_FOUND: "Không tìm thấy dữ liệu.",
        FORBIDDEN: "Bạn không có quyền truy cập dữ liệu này.",
        SESSION_NOT_ACTIVE: "Phiên thi không còn nhận câu trả lời.",
        SESSION_EXPIRED: "Phiên thi đã hết thời gian.",
        UNSUPPORTED_QUESTION: "Luồng này chỉ hỗ trợ câu hỏi tự luận hoặc lập trình.",
        ALREADY_SUBMITTED: "Bài thi đã được nộp.",
        RESULT_NOT_RELEASED: "Kết quả chưa được công bố.",
        GRADING_INCOMPLETE: "Cần chấm đủ các câu trước khi hoàn tất.",
        DB_ERROR: "Lỗi dữ liệu. Vui lòng thử lại.",
    }

    def __init__(self, model: ManualAssessmentModel) -> None:
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
        return WorkflowResult(status, cls._MESSAGES[status], record=record, records=records, value=value)

    @staticmethod
    def _identity(roles: set[str]) -> tuple[int, str] | WorkflowResult:
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return WorkflowResult(
                ManualAssessmentService.NOT_LOGGED_IN,
                ManualAssessmentService._MESSAGES[ManualAssessmentService.NOT_LOGGED_IN],
            )
        if session.current_user.role not in roles:
            return WorkflowResult(
                ManualAssessmentService.WRONG_ROLE,
                ManualAssessmentService._MESSAGES[ManualAssessmentService.WRONG_ROLE],
            )
        return session.current_user.id, session.current_user.role

    @staticmethod
    def _valid_id(value: int) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    @staticmethod
    def _finite_nonnegative(value: object) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )

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
        return (datetime.now(start_time.tzinfo) - start_time).total_seconds() >= duration * 60

    def create_question(
        self,
        title: str,
        content: str,
        question_type: str,
        points: float,
        *,
        difficulty: str = "medium",
        test_cases: str = "",
        reference_answer: str = "",
    ) -> WorkflowResult:
        identity = self._identity({"expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        expert_id, _ = identity
        if (
            not isinstance(title, str)
            or not title.strip()
            or len(title) > 200
            or not isinstance(content, str)
            or not content.strip()
            or len(content) > MAX_RESPONSE_LENGTH
            or not isinstance(question_type, str)
            or question_type not in MANUAL_QUESTION_TYPES
            or not self._finite_nonnegative(points)
            or points <= 0
            or not isinstance(difficulty, str)
            or difficulty not in {"easy", "medium", "hard"}
            or not isinstance(test_cases, str)
            or len(test_cases) > MAX_RESPONSE_LENGTH
            or not isinstance(reference_answer, str)
            or len(reference_answer) > MAX_RESPONSE_LENGTH
        ):
            return self._result(self.INVALID_INPUT)
        if question_type == "essay" and test_cases:
            return self._result(self.INVALID_INPUT)
        try:
            record = self._model.create_manual_question(
                expert_id,
                title=title.strip(),
                content=content.strip(),
                question_type=question_type,
                difficulty=difficulty,
                points=float(points),
                test_cases=test_cases,
                reference_answer=reference_answer,
            )
        except sqlite3.Error:
            logger.exception("Could not create manual question")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.NOT_FOUND)

    def publish_question(self, question_id: int) -> WorkflowResult:
        identity = self._identity({"expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(question_id):
            return self._result(self.INVALID_INPUT)
        try:
            record = self._model.publish_manual_question(identity[0], question_id)
        except sqlite3.Error:
            logger.exception("Could not publish manual question")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.NOT_FOUND)

    def attach_question(self, exam_id: int, question_id: int, points: float) -> WorkflowResult:
        identity = self._identity({"company"})
        if isinstance(identity, WorkflowResult):
            return identity
        if (
            not self._valid_id(exam_id)
            or not self._valid_id(question_id)
            or not self._finite_nonnegative(points)
            or points <= 0
        ):
            return self._result(self.INVALID_INPUT)
        try:
            record = self._model.attach_manual_question(
                identity[0], exam_id, question_id, float(points)
            )
        except sqlite3.Error:
            logger.exception("Could not attach manual question")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.FORBIDDEN)

    def list_questions(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            session = self._model.get_candidate_session(session_id, identity[0])
            if session is None:
                return self._result(self.NOT_FOUND)
            if session.get("status") != "in_progress":
                return self._result(self.SESSION_NOT_ACTIVE)
            if self._session_expired(session) is True:
                return self._result(self.SESSION_EXPIRED)
            questions = self._model.list_candidate_questions(session_id, identity[0])
        except sqlite3.Error:
            logger.exception("Could not load candidate questions")
            return self._result(self.DB_ERROR)
        safe_questions = []
        for question in questions:
            question_type = question.get("question_type")
            if question_type not in MANUAL_QUESTION_TYPES | {"multiple_choice"}:
                return self._result(self.UNSUPPORTED_QUESTION)
            if question_type not in MANUAL_QUESTION_TYPES:
                continue
            safe_questions.append(
                {
                    key: value
                    for key, value in question.items()
                    if key
                    not in {
                        "reference_answer",
                        "test_cases",
                        "correct_answer",
                        "answer_key",
                    }
                }
            )
        if not safe_questions:
            return self._result(self.UNSUPPORTED_QUESTION)
        return self._result(self.SUCCESS, records=safe_questions)

    def save_response(
        self,
        session_id: int,
        question_id: int,
        *,
        answer_text: str | None = None,
        answer_code: str | None = None,
        programming_language: str | None = None,
    ) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id) or not self._valid_id(question_id):
            return self._result(self.INVALID_INPUT)
        try:
            session = self._model.get_candidate_session(session_id, identity[0])
            if session is None:
                return self._result(self.NOT_FOUND)
            if session.get("status") != "in_progress":
                return self._result(self.SESSION_NOT_ACTIVE)
            expired = self._session_expired(session)
            if expired is True:
                return self._result(self.SESSION_EXPIRED)
            questions = self._model.list_candidate_questions(session_id, identity[0])
            question = next(
                (
                    item
                    for item in questions
                    if item.get("id") == question_id
                    or item.get("question_id") == question_id
                ),
                None,
            )
            if question is None:
                return self._result(self.NOT_FOUND)
            question_type = question.get("question_type")
            if question_type not in MANUAL_QUESTION_TYPES:
                return self._result(self.UNSUPPORTED_QUESTION)
            payload = answer_text if question_type == "essay" else answer_code
            other_payload = answer_code if question_type == "essay" else answer_text
            if (
                not isinstance(payload, str)
                or not payload.strip()
                or len(payload) > MAX_RESPONSE_LENGTH
                or other_payload is not None
                or (
                    programming_language is not None
                    and not isinstance(programming_language, str)
                )
            ):
                return self._result(self.INVALID_INPUT)
            if question_type == "essay" and programming_language is not None:
                return self._result(self.INVALID_INPUT)
            if question_type == "coding":
                if "supported_languages" in question:
                    languages = question.get("supported_languages")
                    if isinstance(languages, str):
                        languages = (languages,)
                    if (
                        not isinstance(languages, Sequence)
                        or isinstance(languages, (str, bytes))
                        or not languages
                        or (
                            programming_language is not None
                            and programming_language not in languages
                        )
                    ):
                        return self._result(self.INVALID_INPUT)
            arguments = {
                "answer_text": payload if question_type == "essay" else None,
                "answer_code": payload if question_type == "coding" else None,
            }
            if programming_language is not None:
                arguments["programming_language"] = programming_language
            record = self._model.save_candidate_response(
                session_id, identity[0], question_id, **arguments
            )
        except sqlite3.Error:
            logger.exception("Could not save manual assessment response")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.NOT_FOUND)

    def submit(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            session = self._model.get_candidate_session(session_id, identity[0])
            if session is None:
                return self._result(self.NOT_FOUND)
            if session.get("status") != "in_progress":
                return self._result(self.ALREADY_SUBMITTED)
            questions = self._model.list_candidate_questions(session_id, identity[0])
            if (
                not questions
                or not any(
                    question.get("question_type") in MANUAL_QUESTION_TYPES
                    for question in questions
                )
                or any(
                    question.get("question_type")
                    not in MANUAL_QUESTION_TYPES | {"multiple_choice"}
                    for question in questions
                )
            ):
                return self._result(self.UNSUPPORTED_QUESTION)
            record = self._model.submit_manual_session_once(session_id, identity[0])
        except sqlite3.Error:
            logger.exception("Could not submit manual assessment")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.ALREADY_SUBMITTED)

    def list_submissions_for_grading(self) -> WorkflowResult:
        identity = self._identity({"company", "expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        try:
            records = self._model.list_manual_submissions_for_grader(*identity)
        except sqlite3.Error:
            logger.exception("Could not list manual submissions")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, records=records)

    def list_answers_for_grading(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"company", "expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            if not self._model.can_grade_session(identity[0], identity[1], session_id):
                return self._result(self.FORBIDDEN)
            submission = self._model.get_manual_submission_for_grader(
                session_id, identity[0], identity[1]
            )
            if submission is None:
                return self._result(self.NOT_FOUND)
            answers = self._model.list_manual_answers_for_grading(
                session_id, identity[0], identity[1]
            )
        except sqlite3.Error:
            logger.exception("Could not load answers for grading")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=submission, records=answers)

    def grade_answer(
        self,
        session_id: int,
        question_id: int,
        score: float,
        feedback: str,
        *,
        reason: str = "",
    ) -> WorkflowResult:
        identity = self._identity({"company", "expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        if (
            not self._valid_id(session_id)
            or not self._valid_id(question_id)
            or not self._finite_nonnegative(score)
            or not isinstance(feedback, str)
            or len(feedback) > MAX_FEEDBACK_LENGTH
            or not isinstance(reason, str)
            or len(reason) > MAX_FEEDBACK_LENGTH
        ):
            return self._result(self.INVALID_INPUT)
        try:
            if not self._model.can_grade_session(identity[0], identity[1], session_id):
                return self._result(self.FORBIDDEN)
            answer = self._model.get_manual_answer_for_grading(
                session_id, question_id, identity[0], identity[1]
            )
            if answer is None:
                return self._result(self.NOT_FOUND)
            if answer.get("question_type") not in MANUAL_QUESTION_TYPES:
                return self._result(self.UNSUPPORTED_QUESTION)
            max_score = answer.get("max_score")
            if (
                not isinstance(max_score, (int, float))
                or isinstance(max_score, bool)
                or not math.isfinite(max_score)
                or max_score <= 0
                or score > max_score
            ):
                return self._result(self.INVALID_INPUT)
            if bool(answer.get("is_graded")) and not reason.strip():
                return self._result(self.INVALID_INPUT)
            record = self._model.grade_manual_answer_once(
                session_id,
                question_id,
                identity[0],
                score=float(score),
                feedback=feedback.strip(),
                reason=reason.strip(),
            )
        except sqlite3.Error:
            logger.exception("Could not grade manual answer")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.NOT_FOUND)

    def finalize_grading(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"company", "expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            if not self._model.can_grade_session(identity[0], identity[1], session_id):
                return self._result(self.FORBIDDEN)
            progress = self._model.get_manual_grading_progress(
                session_id, identity[0], identity[1]
            )
            if progress is None:
                return self._result(self.NOT_FOUND)
            question_count = progress.get("question_count")
            graded_count = progress.get("graded_count")
            if (
                not isinstance(question_count, int)
                or isinstance(question_count, bool)
                or not isinstance(graded_count, int)
                or isinstance(graded_count, bool)
                or question_count <= 0
                or graded_count != question_count
            ):
                return self._result(self.GRADING_INCOMPLETE, record=progress)
            record = self._model.finalize_manual_grading_once(
                session_id, identity[0], identity[1]
            )
        except sqlite3.Error:
            logger.exception("Could not finalize manual grading")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.GRADING_INCOMPLETE)

    def release_result(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"company"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            if not self._model.can_grade_session(identity[0], identity[1], session_id):
                return self._result(self.FORBIDDEN)
            record = self._model.release_manual_result_once(session_id, identity[0])
        except sqlite3.Error:
            logger.exception("Could not release manual result")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.GRADING_INCOMPLETE)

    def get_result(self, session_id: int) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(session_id):
            return self._result(self.INVALID_INPUT)
        try:
            submission = self._model.get_candidate_submission(session_id, identity[0])
            if submission is None:
                return self._result(self.NOT_FOUND)
            if submission.get("status") != "released":
                return self._result(self.RESULT_NOT_RELEASED)
            result = self._model.get_candidate_result(session_id, identity[0])
        except sqlite3.Error:
            logger.exception("Could not load candidate result")
            return self._result(self.DB_ERROR)
        if result is None:
            return self._result(self.NOT_FOUND)
        allowed = {"score", "max_score", "released_at", "status"}
        safe_result = {key: value for key, value in result.items() if key in allowed}
        return self._result(self.SUCCESS, record=safe_result)
