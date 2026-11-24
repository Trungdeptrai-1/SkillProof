"""Exam workflows implemented against the pending Exam Model contract."""

from __future__ import annotations

import logging
import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.services.auth_service import SessionManager
from server.services.recruitment_service import RecruitmentModel

logger = logging.getLogger(__name__)

Record = Mapping[str, object]
QuestionScores = Sequence[Mapping[str, int | float]]


@dataclass(frozen=True)
class ExamOption:
    content: str
    is_correct: bool


class ExamModel(Protocol):
    """Persistence contract needed from the recruitment/exam Model layer.

    Candidate/session and Company/exam methods must scope queries by the
    supplied owner. ``complete_session_once`` must atomically change an
    in-progress session to completed and persist grades only once. A false
    completion result means another request already completed that session;
    database failures must raise ``sqlite3.Error``. Answer persistence must
    verify that the option belongs to the requested question and exam.
    Candidate-session records include ``started_at`` and ``duration_min``;
    candidate-submission records expose a ``status`` used to gate results
    until ``released``. Model methods return Mapping-shaped records, adapting
    dataclass DTOs where needed. Candidate-safe payloads must omit answer keys;
    the Service also redacts private fields before returning records.
    """

    def create_exam(
        self,
        company_id: int,
        *,
        title: str,
        description: str,
        duration_min: int,
        total_points: float,
    ) -> Record | None: ...

    def get_exam_for_company(
        self, company_id: int, exam_id: int
    ) -> Record | None: ...

    def list_exams_for_company(self, company_id: int) -> Sequence[Record]: ...

    def list_contracted_experts(self, company_id: int) -> Sequence[Record]: ...

    def add_question(
        self,
        company_id: int,
        exam_id: int,
        *,
        title: str,
        content: str,
        difficulty: str,
        points: float,
        options: Sequence[ExamOption],
        expert_id: int | None = None,
    ) -> Record | None: ...

    def get_user_role(self, user_id: int) -> str | None: ...

    def publish_exam(self, company_id: int, exam_id: int) -> Record | None: ...

    def get_candidate_invitation(
        self, invitation_id: int, candidate_id: int
    ) -> Record | None: ...

    def accept_candidate_invitation(
        self, invitation_id: int, candidate_id: int
    ) -> Record | None: ...

    def expire_candidate_invitation(
        self, invitation_id: int, candidate_id: int
    ) -> None: ...

    def invite_candidate(
        self,
        company_id: int,
        job_posting_id: int,
        exam_id: int,
        candidate_id: int,
        expires_at: str | None,
    ) -> Record | None: ...

    def list_company_submissions(
        self, company_id: int, exam_id: int
    ) -> Sequence[Record]: ...

    def release_results(self, company_id: int, exam_id: int) -> Record | None: ...

    def list_candidate_invitations(self, candidate_id: int) -> Sequence[Record]: ...

    def get_candidate_session(
        self, session_id: int, candidate_id: int
    ) -> Record | None: ...

    def start_session_once(
        self, session_id: int, candidate_id: int
    ) -> tuple[bool, Record | None]: ...

    def list_candidate_questions(
        self, session_id: int, candidate_id: int
    ) -> Sequence[Record]: ...

    def save_candidate_answer(
        self,
        session_id: int,
        candidate_id: int,
        question_id: int,
        selected_option_id: int,
    ) -> Record | None: ...

    def get_grading_questions(self, session_id: int) -> Sequence[Record]: ...

    def get_candidate_answers(
        self, session_id: int, candidate_id: int
    ) -> Sequence[Record]: ...

    def complete_session_once(
        self,
        session_id: int,
        candidate_id: int,
        *,
        score: float,
        max_score: float,
        question_scores: QuestionScores,
    ) -> tuple[bool, Record | None]: ...

    def get_candidate_result(
        self, session_id: int, candidate_id: int
    ) -> Record | None: ...

    def get_candidate_submission(
        self, session_id: int, candidate_id: int
    ) -> Record | None: ...


class ExamResult:
    SUCCESS = "success"
    NOT_LOGGED_IN = "not_logged_in"
    WRONG_ROLE = "wrong_role"
    INVALID_INPUT = "invalid_input"
    EMPTY_TITLE = "empty_title"
    INVALID_DURATION = "invalid_duration"
    INVALID_POINTS = "invalid_points"
    INVALID_OPTIONS = "invalid_options"
    INVALID_CANDIDATE = "invalid_candidate"
    JOB_NOT_FOUND = "job_not_found"
    JOB_NOT_PUBLISHED = "job_not_published"
    EXAM_NOT_FOUND = "exam_not_found"
    EXAM_NOT_PUBLISHED = "exam_not_published"
    EXAM_ALREADY_PUBLISHED = "exam_already_published"
    INVITATION_NOT_FOUND = "invitation_not_found"
    INVITATION_EXPIRED = "invitation_expired"
    INVALID_INVITATION_STATE = "invalid_invitation_state"
    INVALID_SESSION_STATE = "invalid_session_state"
    ALREADY_SUBMITTED = "already_submitted"
    EXAM_EXPIRED = "exam_expired"
    ANSWER_NOT_FOUND = "answer_not_found"
    RESULT_NOT_RELEASED = "result_not_released"
    INVALID_EXAM_CONFIGURATION = "invalid_exam_configuration"
    DB_ERROR = "db_error"

    MESSAGES = {
        SUCCESS: "Thao tác thành công.",
        NOT_LOGGED_IN: "Vui lòng đăng nhập trước.",
        WRONG_ROLE: "Bạn không có quyền thực hiện thao tác này.",
        INVALID_INPUT: "Dữ liệu đầu vào không hợp lệ.",
        EMPTY_TITLE: "Tiêu đề không được để trống.",
        INVALID_DURATION: "Thời lượng bài thi phải là số nguyên dương.",
        INVALID_POINTS: "Điểm phải là số dương hợp lệ.",
        INVALID_OPTIONS: "Câu hỏi trắc nghiệm cần ít nhất hai lựa chọn và đúng một đáp án đúng.",
        INVALID_CANDIDATE: "Không tìm thấy tài khoản ứng viên hợp lệ.",
        JOB_NOT_FOUND: "Không tìm thấy vị trí tuyển dụng.",
        JOB_NOT_PUBLISHED: "Vị trí tuyển dụng chưa được công bố.",
        EXAM_NOT_FOUND: "Không tìm thấy bài thi.",
        EXAM_NOT_PUBLISHED: "Bài thi chưa được công bố.",
        EXAM_ALREADY_PUBLISHED: "Không thể chỉnh sửa câu hỏi sau khi công bố bài thi.",
        INVITATION_NOT_FOUND: "Không tìm thấy lời mời hoặc phiên thi.",
        INVITATION_EXPIRED: "Lời mời đã hết hạn.",
        INVALID_INVITATION_STATE: "Trạng thái lời mời không cho phép thao tác này.",
        INVALID_SESSION_STATE: "Trạng thái phiên thi không cho phép thao tác này.",
        ALREADY_SUBMITTED: "Bài thi đã được nộp trước đó.",
        EXAM_EXPIRED: "Đã hết thời gian làm bài; câu trả lời không thể thay đổi.",
        ANSWER_NOT_FOUND: "Không tìm thấy câu hỏi hoặc lựa chọn hợp lệ.",
        RESULT_NOT_RELEASED: "Kết quả chưa được công bố.",
        INVALID_EXAM_CONFIGURATION: "Cấu hình hoặc dữ liệu bài thi không hợp lệ.",
        DB_ERROR: "Lỗi dữ liệu bài thi. Vui lòng thử lại.",
    }

    def __init__(
        self,
        status: str,
        *,
        exam: Record | None = None,
        exams: Sequence[Record] | None = None,
        question: Record | None = None,
        invitation: Record | None = None,
        invitations: Sequence[Record] | None = None,
        questions: Sequence[Record] | None = None,
        submissions: Sequence[Record] | None = None,
        experts: Sequence[Record] | None = None,
        answer: Record | None = None,
        result: Record | None = None,
        score: float | None = None,
        max_score: float | None = None,
    ) -> None:
        self.status = status
        self.exam = exam
        self.exams = list(exams) if exams is not None else []
        self.question = question
        self.invitation = invitation
        self.invitations = list(invitations) if invitations is not None else []
        self.questions = list(questions) if questions is not None else []
        self.submissions = list(submissions) if submissions is not None else []
        self.experts = list(experts) if experts is not None else []
        self.answer = answer
        self.result = result
        self.score = score
        self.max_score = max_score
        self.success = status == self.SUCCESS
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")


class ExamService:
    _PRIVATE_CANDIDATE_FIELDS = frozenset(
        {
            "answer",
            "answer_key",
            "answer_text",
            "answers",
            "correct",
            "correct_answer",
            "correct_option_id",
            "feedback",
            "graded_at",
            "graded_by",
            "is_correct",
            "is_graded",
            "is_released",
            "reference_answer",
            "result",
            "results",
            "results_released",
            "score",
            "total_score",
        }
    )

    def __init__(
        self,
        model: ExamModel,
        recruitment_model: RecruitmentModel,
    ) -> None:
        self._model = model
        self._recruitment_model = recruitment_model

    @staticmethod
    def _user_id_for_role(role: str) -> int | ExamResult:
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return ExamResult(ExamResult.NOT_LOGGED_IN)
        if session.current_user.role != role:
            return ExamResult(ExamResult.WRONG_ROLE)
        return session.current_user.id

    @staticmethod
    def _valid_id(value: int) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    @staticmethod
    def _valid_points(value: int | float) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value > 0
        )

    @staticmethod
    def _time_limit_error(session: Record) -> str | None:
        started_at = session.get("started_at")
        duration_min = session.get("duration_min")
        if (
            not isinstance(started_at, str)
            or isinstance(duration_min, bool)
            or not isinstance(duration_min, int)
            or duration_min <= 0
        ):
            return ExamResult.INVALID_EXAM_CONFIGURATION
        try:
            start = datetime.fromisoformat(started_at)
        except ValueError:
            return ExamResult.INVALID_EXAM_CONFIGURATION
        current = datetime.now(start.tzinfo) if start.tzinfo else datetime.now()
        if current >= start + timedelta(minutes=duration_min):
            return ExamResult.EXAM_EXPIRED
        return None

    @staticmethod
    def _expiration_error(value: object, *, stored: bool = False) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            return (
                ExamResult.INVALID_INVITATION_STATE
                if stored
                else ExamResult.INVALID_INPUT
            )
        try:
            expiration = datetime.fromisoformat(value)
        except ValueError:
            return (
                ExamResult.INVALID_INVITATION_STATE
                if stored
                else ExamResult.INVALID_INPUT
            )
        current = (
            datetime.now(expiration.tzinfo)
            if expiration.tzinfo
            else datetime.now()
        )
        return (
            ExamResult.INVITATION_EXPIRED
            if current >= expiration
            else None
        )

    def create_exam(
        self,
        title: str,
        description: str = "",
        duration_min: int = 60,
        total_points: int | float = 100,
    ) -> ExamResult:
        company_id = self._user_id_for_role("company")
        if isinstance(company_id, ExamResult):
            return company_id
        if not isinstance(title, str) or not isinstance(description, str):
            return ExamResult(ExamResult.INVALID_INPUT)
        if not title.strip():
            return ExamResult(ExamResult.EMPTY_TITLE)
        if (
            isinstance(duration_min, bool)
            or not isinstance(duration_min, int)
            or duration_min <= 0
        ):
            return ExamResult(ExamResult.INVALID_DURATION)
        if not self._valid_points(total_points):
            return ExamResult(ExamResult.INVALID_POINTS)

        try:
            exam = self._model.create_exam(
                company_id,
                title=title.strip(),
                description=description.strip(),
                duration_min=duration_min,
                total_points=float(total_points),
            )
        except sqlite3.Error as exc:
            logger.error("Database error creating exam: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if exam is None:
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(ExamResult.SUCCESS, exam=exam)

    def get_exam(self, exam_id: int) -> ExamResult:
        company_id = self._user_id_for_role("company")
        if isinstance(company_id, ExamResult):
            return company_id
        if not self._valid_id(exam_id):
            return ExamResult(ExamResult.INVALID_INPUT)
        try:
            exam = self._model.get_exam_for_company(company_id, exam_id)
        except sqlite3.Error as exc:
            logger.error("Database error retrieving exam: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if exam is None:
            return ExamResult(ExamResult.EXAM_NOT_FOUND)
        return ExamResult(ExamResult.SUCCESS, exam=exam)

    def list_exams(self) -> ExamResult:
        company_id = self._user_id_for_role("company")
        if isinstance(company_id, ExamResult):
            return company_id
        try:
            exams = self._model.list_exams_for_company(company_id)
        except sqlite3.Error as exc:
            logger.error("Database error listing exams: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(ExamResult.SUCCESS, exams=exams)

    def list_contracted_experts(self) -> ExamResult:
        company_id = self._user_id_for_role("company")
        if isinstance(company_id, ExamResult):
            return company_id
        try:
            experts = self._model.list_contracted_experts(company_id)
        except sqlite3.Error as exc:
            logger.error("Database error listing contracted experts: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(ExamResult.SUCCESS, experts=experts)

    def publish_exam(self, exam_id: int) -> ExamResult:
        company_id = self._user_id_for_role("company")
        if isinstance(company_id, ExamResult):
            return company_id
        if not self._valid_id(exam_id):
            return ExamResult(ExamResult.INVALID_INPUT)
        try:
            exam = self._model.get_exam_for_company(company_id, exam_id)
            if exam is None:
                return ExamResult(ExamResult.EXAM_NOT_FOUND)
            if exam.get("is_published") in (True, 1):
                return ExamResult(ExamResult.SUCCESS, exam=exam)
            published = self._model.publish_exam(company_id, exam_id)
        except sqlite3.Error as exc:
            logger.error("Database error publishing exam: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if published is None:
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(ExamResult.SUCCESS, exam=published)

    def add_question(
        self,
        exam_id: int,
        title: str,
        content: str,
        options: Sequence[ExamOption],
        points: int | float = 10,
        difficulty: str = "medium",
        expert_id: int | None = None,
    ) -> ExamResult:
        company_id = self._user_id_for_role("company")
        if isinstance(company_id, ExamResult):
            return company_id
        if not self._valid_id(exam_id) or not isinstance(title, str):
            return ExamResult(ExamResult.INVALID_INPUT)
        if not isinstance(content, str) or not isinstance(difficulty, str):
            return ExamResult(ExamResult.INVALID_INPUT)
        if not title.strip() or not content.strip():
            return ExamResult(ExamResult.EMPTY_TITLE)
        if difficulty not in {"easy", "medium", "hard"}:
            return ExamResult(ExamResult.INVALID_INPUT)
        if not self._valid_points(points):
            return ExamResult(ExamResult.INVALID_POINTS)
        if expert_id is not None and not self._valid_id(expert_id):
            return ExamResult(ExamResult.INVALID_INPUT)
        valid_options = self._validate_options(options)
        if valid_options is None:
            return ExamResult(ExamResult.INVALID_OPTIONS)

        try:
            exam = self._model.get_exam_for_company(company_id, exam_id)
            if exam is None:
                return ExamResult(ExamResult.EXAM_NOT_FOUND)
            if exam.get("is_published") in (True, 1):
                return ExamResult(ExamResult.EXAM_ALREADY_PUBLISHED)
            question = self._model.add_question(
                company_id,
                exam_id,
                title=title.strip(),
                content=content.strip(),
                difficulty=difficulty,
                points=float(points),
                options=valid_options,
                expert_id=expert_id,
            )
        except sqlite3.Error as exc:
            logger.error("Database error adding exam question: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if question is None:
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(ExamResult.SUCCESS, question=question)

    @staticmethod
    def _validate_options(
        options: Sequence[ExamOption],
    ) -> tuple[ExamOption, ...] | None:
        if isinstance(options, (str, bytes)) or not isinstance(options, Sequence):
            return None
        if len(options) < 2:
            return None
        if any(
            not isinstance(option, ExamOption)
            or not isinstance(option.content, str)
            or not option.content.strip()
            or not isinstance(option.is_correct, bool)
            for option in options
        ):
            return None
        if sum(option.is_correct for option in options) != 1:
            return None
        return tuple(
            ExamOption(option.content.strip(), option.is_correct)
            for option in options
        )

    def invite_candidate(
        self,
        job_posting_id: int,
        exam_id: int,
        candidate_id: int,
        expires_at: str | None = None,
    ) -> ExamResult:
        company_id = self._user_id_for_role("company")
        if isinstance(company_id, ExamResult):
            return company_id
        if not all(
            self._valid_id(value)
            for value in (job_posting_id, exam_id, candidate_id)
        ):
            return ExamResult(ExamResult.INVALID_INPUT)
        expiration_error = self._expiration_error(expires_at)
        if expiration_error:
            return ExamResult(expiration_error)

        try:
            job = self._recruitment_model.get_job_posting(
                company_id, job_posting_id
            )
            if job is None:
                return ExamResult(ExamResult.JOB_NOT_FOUND)
            if job.get("status") != "published":
                return ExamResult(ExamResult.JOB_NOT_PUBLISHED)
            exam = self._model.get_exam_for_company(company_id, exam_id)
            if exam is None:
                return ExamResult(ExamResult.EXAM_NOT_FOUND)
            if exam.get("is_published") not in (True, 1):
                return ExamResult(ExamResult.EXAM_NOT_PUBLISHED)
            role = self._model.get_user_role(candidate_id)
            if role != "candidate":
                return ExamResult(ExamResult.INVALID_CANDIDATE)
            invitation = self._model.invite_candidate(
                company_id,
                job_posting_id,
                exam_id,
                candidate_id,
                expires_at.strip() if expires_at and expires_at.strip() else None,
            )
        except sqlite3.Error as exc:
            logger.error("Database error inviting candidate: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if invitation is None:
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(ExamResult.SUCCESS, invitation=invitation)

    def accept_invitation(self, invitation_id: int) -> ExamResult:
        candidate_id = self._user_id_for_role("candidate")
        if isinstance(candidate_id, ExamResult):
            return candidate_id
        if not self._valid_id(invitation_id):
            return ExamResult(ExamResult.INVALID_INPUT)
        try:
            invitation = self._model.get_candidate_invitation(
                invitation_id, candidate_id
            )
            if invitation is None:
                return ExamResult(ExamResult.INVITATION_NOT_FOUND)
            status = invitation.get("status")
            if status == "accepted":
                return ExamResult(
                    ExamResult.SUCCESS,
                    invitation=self._redact_candidate_record(invitation),
                )
            if status != "pending":
                if status == "expired":
                    return ExamResult(ExamResult.INVITATION_EXPIRED)
                return ExamResult(ExamResult.INVALID_INVITATION_STATE)
            expiry_error = self._expiration_error(
                invitation.get("expires_at"),
                stored=True,
            )
            if expiry_error == ExamResult.INVITATION_EXPIRED:
                self._model.expire_candidate_invitation(
                    invitation_id, candidate_id
                )
                return ExamResult(ExamResult.INVITATION_EXPIRED)
            if expiry_error:
                return ExamResult(expiry_error)
            accepted = self._model.accept_candidate_invitation(
                invitation_id, candidate_id
            )
        except sqlite3.Error as exc:
            logger.error("Database error accepting exam invitation: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if accepted is None:
            return ExamResult(ExamResult.DB_ERROR)
        if accepted.get("status") == "expired":
            return ExamResult(ExamResult.INVITATION_EXPIRED)
        if accepted.get("status") != "accepted":
            return ExamResult(ExamResult.INVALID_INVITATION_STATE)
        return ExamResult(
            ExamResult.SUCCESS,
            invitation=self._redact_candidate_record(accepted),
        )

    def list_submissions(self, exam_id: int) -> ExamResult:
        company_id = self._user_id_for_role("company")
        if isinstance(company_id, ExamResult):
            return company_id
        if not self._valid_id(exam_id):
            return ExamResult(ExamResult.INVALID_INPUT)
        try:
            exam = self._model.get_exam_for_company(company_id, exam_id)
            if exam is None:
                return ExamResult(ExamResult.EXAM_NOT_FOUND)
            submissions = self._model.list_company_submissions(company_id, exam_id)
        except sqlite3.Error as exc:
            logger.error("Database error listing exam submissions: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(
            ExamResult.SUCCESS,
            exam=exam,
            submissions=submissions,
        )

    def release_results(self, exam_id: int) -> ExamResult:
        company_id = self._user_id_for_role("company")
        if isinstance(company_id, ExamResult):
            return company_id
        if not self._valid_id(exam_id):
            return ExamResult(ExamResult.INVALID_INPUT)
        try:
            released = self._model.release_results(company_id, exam_id)
        except sqlite3.Error as exc:
            logger.error("Database error releasing exam results: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if released is None:
            return ExamResult(ExamResult.EXAM_NOT_FOUND)
        return ExamResult(ExamResult.SUCCESS, exam=released)

    def list_invitations(self) -> ExamResult:
        candidate_id = self._user_id_for_role("candidate")
        if isinstance(candidate_id, ExamResult):
            return candidate_id
        try:
            invitations = self._model.list_candidate_invitations(candidate_id)
        except sqlite3.Error as exc:
            logger.error("Database error listing candidate invitations: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        sanitized: list[Record] = []
        for invitation in invitations:
            public = self._redact_candidate_record(invitation)
            if public is None:
                return ExamResult(ExamResult.DB_ERROR)
            sanitized.append(public)
        return ExamResult(ExamResult.SUCCESS, invitations=sanitized)

    def start_exam(self, session_id: int) -> ExamResult:
        candidate_id = self._user_id_for_role("candidate")
        if isinstance(candidate_id, ExamResult):
            return candidate_id
        if not self._valid_id(session_id):
            return ExamResult(ExamResult.INVALID_INPUT)
        try:
            session = self._model.get_candidate_session(session_id, candidate_id)
            if session is None:
                return ExamResult(ExamResult.INVITATION_NOT_FOUND)
            status = session.get("status")
            if status == "in_progress":
                return ExamResult(
                    ExamResult.SUCCESS,
                    invitation=self._redact_candidate_record(session),
                )
            if status != "scheduled":
                return ExamResult(ExamResult.ALREADY_SUBMITTED if status == "completed"
                                  else ExamResult.INVALID_SESSION_STATE)
            started, updated_session = self._model.start_session_once(
                session_id, candidate_id
            )
        except sqlite3.Error as exc:
            logger.error("Database error starting exam: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if not started:
            if updated_session and updated_session.get("status") == "in_progress":
                return ExamResult(
                    ExamResult.SUCCESS,
                    invitation=self._redact_candidate_record(updated_session),
                )
            if updated_session and updated_session.get("status") == "completed":
                return ExamResult(ExamResult.ALREADY_SUBMITTED)
            return ExamResult(ExamResult.INVALID_SESSION_STATE)
        if updated_session is None:
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(
            ExamResult.SUCCESS,
            invitation=self._redact_candidate_record(updated_session),
        )

    def list_questions(self, session_id: int) -> ExamResult:
        candidate_id = self._user_id_for_role("candidate")
        if isinstance(candidate_id, ExamResult):
            return candidate_id
        if not self._valid_id(session_id):
            return ExamResult(ExamResult.INVALID_INPUT)
        try:
            session = self._model.get_candidate_session(session_id, candidate_id)
            if session is None:
                return ExamResult(ExamResult.INVITATION_NOT_FOUND)
            if session.get("status") != "in_progress":
                return ExamResult(ExamResult.INVALID_SESSION_STATE)
            time_error = self._time_limit_error(session)
            if time_error:
                return ExamResult(time_error)
            rows = self._model.list_candidate_questions(session_id, candidate_id)
        except sqlite3.Error as exc:
            logger.error("Database error retrieving candidate questions: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)

        questions: list[Record] = []
        for row in rows:
            question = self._redact_candidate_record(row)
            if question is None:
                return ExamResult(ExamResult.DB_ERROR)
            options = question.get("options", ())
            if not isinstance(options, list):
                return ExamResult(ExamResult.DB_ERROR)
            questions.append(question)
        return ExamResult(ExamResult.SUCCESS, questions=questions)

    @classmethod
    def _redact_candidate_record(cls, record: Record) -> dict[str, object] | None:
        def redact(value: object) -> object:
            if isinstance(value, Mapping):
                return {
                    key: redact(item)
                    for key, item in value.items()
                    if not (
                        isinstance(key, str)
                        and key.lower() in cls._PRIVATE_CANDIDATE_FIELDS
                    )
                }
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                return [redact(item) for item in value]
            return value

        public = redact(record)
        return public if isinstance(public, dict) else None

    def save_answer(
        self, session_id: int, question_id: int, selected_option_id: int
    ) -> ExamResult:
        candidate_id = self._user_id_for_role("candidate")
        if isinstance(candidate_id, ExamResult):
            return candidate_id
        if not all(
            self._valid_id(value)
            for value in (session_id, question_id, selected_option_id)
        ):
            return ExamResult(ExamResult.INVALID_INPUT)
        try:
            session = self._model.get_candidate_session(session_id, candidate_id)
            if session is None:
                return ExamResult(ExamResult.INVITATION_NOT_FOUND)
            if session.get("status") != "in_progress":
                return ExamResult(ExamResult.INVALID_SESSION_STATE)
            time_error = self._time_limit_error(session)
            if time_error:
                return ExamResult(time_error)
            answer = self._model.save_candidate_answer(
                session_id,
                candidate_id,
                question_id,
                selected_option_id,
            )
        except sqlite3.Error as exc:
            logger.error("Database error saving exam answer: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if answer is None:
            return ExamResult(ExamResult.ANSWER_NOT_FOUND)
        return ExamResult(ExamResult.SUCCESS, answer=answer)

    def submit_exam(self, session_id: int) -> ExamResult:
        candidate_id = self._user_id_for_role("candidate")
        if isinstance(candidate_id, ExamResult):
            return candidate_id
        if not self._valid_id(session_id):
            return ExamResult(ExamResult.INVALID_INPUT)

        try:
            session = self._model.get_candidate_session(session_id, candidate_id)
            if session is None:
                return ExamResult(ExamResult.INVITATION_NOT_FOUND)
            status = session.get("status")
            if status == "completed":
                return ExamResult(ExamResult.ALREADY_SUBMITTED)
            if status != "in_progress":
                return ExamResult(ExamResult.INVALID_SESSION_STATE)
            time_error = self._time_limit_error(session)
            if time_error == ExamResult.INVALID_EXAM_CONFIGURATION:
                return ExamResult(time_error)

            questions = self._model.get_grading_questions(session_id)
            answers = self._model.get_candidate_answers(session_id, candidate_id)
            grade = self._calculate_grade(questions, answers)
            if grade is None:
                return ExamResult(ExamResult.INVALID_EXAM_CONFIGURATION)
            score, max_score, question_scores = grade
            completed, submission = self._model.complete_session_once(
                session_id,
                candidate_id,
                score=score,
                max_score=max_score,
                question_scores=question_scores,
            )
        except sqlite3.Error as exc:
            logger.error("Database error submitting exam: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)

        if not completed:
            return ExamResult(ExamResult.ALREADY_SUBMITTED)
        if submission is None:
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(
            ExamResult.SUCCESS,
            result={"status": "submitted"},
        )

    @classmethod
    def _calculate_grade(
        cls,
        questions: Sequence[Record],
        answers: Sequence[Record],
    ) -> tuple[float, float, list[dict[str, int | float]]] | None:
        if not questions:
            return None
        answers_by_question: dict[int, int] = {}
        for answer in answers:
            question_id = answer.get("question_id")
            option_id = answer.get("selected_option_id")
            if (
                not cls._valid_id(question_id)
                or not cls._valid_id(option_id)
                or question_id in answers_by_question
            ):
                return None
            answers_by_question[question_id] = option_id

        score = 0.0
        max_score = 0.0
        question_scores: list[dict[str, int | float]] = []
        seen_questions: set[int] = set()
        for question in questions:
            question_id = question.get("id")
            points = question.get("points")
            options = question.get("options")
            if (
                not cls._valid_id(question_id)
                or question_id in seen_questions
                or not cls._valid_points(points)
                or not isinstance(options, Sequence)
                or isinstance(options, (str, bytes))
            ):
                return None
            seen_questions.add(question_id)

            correct_ids: list[int] = []
            option_ids: set[int] = set()
            for option in options:
                if not isinstance(option, Mapping):
                    return None
                option_id = option.get("id")
                if not cls._valid_id(option_id) or option_id in option_ids:
                    return None
                option_ids.add(option_id)
                if option.get("is_correct") in (True, 1):
                    correct_ids.append(option_id)
            if len(correct_ids) != 1:
                return None

            max_score += float(points)
            question_score = (
                float(points)
                if answers_by_question.get(question_id) == correct_ids[0]
                else 0.0
            )
            score += question_score
            question_scores.append(
                {
                    "question_id": question_id,
                    "score": question_score,
                    "max_score": float(points),
                }
            )

        if any(question_id not in seen_questions for question_id in answers_by_question):
            return None
        return score, max_score, question_scores

    def get_result(self, session_id: int) -> ExamResult:
        candidate_id = self._user_id_for_role("candidate")
        if isinstance(candidate_id, ExamResult):
            return candidate_id
        if not self._valid_id(session_id):
            return ExamResult(ExamResult.INVALID_INPUT)
        try:
            session = self._model.get_candidate_session(session_id, candidate_id)
            if session is None:
                return ExamResult(ExamResult.INVITATION_NOT_FOUND)
            if session.get("status") != "completed":
                return ExamResult(ExamResult.INVALID_SESSION_STATE)
            submission = self._model.get_candidate_submission(
                session_id, candidate_id
            )
            if submission is None:
                return ExamResult(ExamResult.INVITATION_NOT_FOUND)
            if submission.get("status") != "released":
                return ExamResult(ExamResult.RESULT_NOT_RELEASED)
            result = self._model.get_candidate_result(session_id, candidate_id)
        except sqlite3.Error as exc:
            logger.error("Database error retrieving candidate result: %s", exc)
            return ExamResult(ExamResult.DB_ERROR)
        if result is None:
            return ExamResult(ExamResult.DB_ERROR)
        return ExamResult(ExamResult.SUCCESS, result=result)
