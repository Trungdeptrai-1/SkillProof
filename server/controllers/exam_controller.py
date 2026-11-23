"""Controller for Company exam creation and Candidate exam-taking requests."""

from __future__ import annotations

from collections.abc import Sequence

from server.services.exam_service import ExamOption, ExamResult, ExamService


class ExamController:
    def __init__(self, service: ExamService) -> None:
        self._service = service

    def create_exam(
        self,
        title: str,
        description: str = "",
        duration_min: int = 60,
        total_points: int | float = 100,
    ) -> ExamResult:
        if not isinstance(title, str) or not isinstance(description, str):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.create_exam(
            title, description, duration_min, total_points
        )

    def get_exam(self, exam_id: int) -> ExamResult:
        if isinstance(exam_id, bool) or not isinstance(exam_id, int):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.get_exam(exam_id)

    def list_exams(self) -> ExamResult:
        return self._service.list_exams()

    def publish_exam(self, exam_id: int) -> ExamResult:
        if isinstance(exam_id, bool) or not isinstance(exam_id, int):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.publish_exam(exam_id)

    def add_question(
        self,
        exam_id: int,
        title: str,
        content: str,
        options: Sequence[ExamOption],
        points: int | float = 10,
        difficulty: str = "medium",
    ) -> ExamResult:
        if (
            isinstance(exam_id, bool)
            or not isinstance(exam_id, int)
            or not isinstance(title, str)
            or not isinstance(content, str)
            or not isinstance(difficulty, str)
            or not isinstance(options, Sequence)
        ):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.add_question(
            exam_id, title, content, options, points, difficulty
        )

    def invite_candidate(
        self,
        job_posting_id: int,
        exam_id: int,
        candidate_id: int,
        expires_at: str | None = None,
    ) -> ExamResult:
        if (
            isinstance(job_posting_id, bool)
            or not isinstance(job_posting_id, int)
            or isinstance(exam_id, bool)
            or not isinstance(exam_id, int)
            or isinstance(candidate_id, bool)
            or not isinstance(candidate_id, int)
            or (expires_at is not None and not isinstance(expires_at, str))
        ):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.invite_candidate(
            job_posting_id, exam_id, candidate_id, expires_at
        )

    def accept_invitation(self, invitation_id: int) -> ExamResult:
        if isinstance(invitation_id, bool) or not isinstance(invitation_id, int):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.accept_invitation(invitation_id)

    def list_submissions(self, exam_id: int) -> ExamResult:
        if isinstance(exam_id, bool) or not isinstance(exam_id, int):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.list_submissions(exam_id)

    def release_results(self, exam_id: int) -> ExamResult:
        if isinstance(exam_id, bool) or not isinstance(exam_id, int):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.release_results(exam_id)

    def list_invitations(self) -> ExamResult:
        return self._service.list_invitations()

    def start_exam(self, session_id: int) -> ExamResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.start_exam(session_id)

    def list_questions(self, session_id: int) -> ExamResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.list_questions(session_id)

    def save_answer(
        self, session_id: int, question_id: int, selected_option_id: int
    ) -> ExamResult:
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (session_id, question_id, selected_option_id)
        ):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.save_answer(
            session_id, question_id, selected_option_id
        )

    def submit_exam(self, session_id: int) -> ExamResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.submit_exam(session_id)

    def get_result(self, session_id: int) -> ExamResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return ExamResult(ExamResult.INVALID_INPUT)
        return self._service.get_result(session_id)
