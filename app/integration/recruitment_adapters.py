"""Composition and View adapters for recruitment and exam Controllers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from client.views.recruitment_contracts import (
    ActionResult,
    Assessment,
    AssessmentResultRow,
    Candidate,
    CandidateInvitation,
    CandidateResult,
    CandidateResultResponse,
    CompanyRecruitmentController,
    ExamDetails,
    ExamLoadResult,
    ExamOption as ViewExamOption,
    ExamQuestion,
    ListResult,
    Position,
    QuestionDraft,
    SubmitResult,
)
from server.controllers.exam_controller import ExamController
from server.controllers.recruitment_controller import RecruitmentController
from server.models.recruitment_repository import RecruitmentRepository
from server.services.exam_service import (
    ExamOption,
    ExamResult,
    ExamService,
)
from server.services.recruitment_service import RecruitmentResult, RecruitmentService

Record = Mapping[str, object]


def _record(value: object) -> Record | None:
    return value if isinstance(value, Mapping) else None


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


class CompanyRecruitmentAdapter:
    """Translate View operations to the existing recruitment and exam APIs."""

    def __init__(
        self,
        recruitment: RecruitmentController,
        exams: ExamController,
    ) -> None:
        self._recruitment = recruitment
        self._exams = exams

    def list_positions(self) -> ListResult[Position]:
        result = self._recruitment.list_positions()
        if not result.success:
            return ListResult(False, message=result.message)
        positions: list[Position] = []
        for value in result.positions:
            row = _record(value)
            if row is None:
                return ListResult(False, message="Dữ liệu vị trí tuyển dụng không hợp lệ.")
            position_id = _integer(row.get("id"))
            title = _text(row.get("title"))
            status = _text(row.get("status"))
            if position_id is None or title is None or status is None:
                return ListResult(False, message="Dữ liệu vị trí tuyển dụng không đầy đủ.")
            positions.append(
                Position(
                    id=position_id,
                    title=title,
                    location=_text(row.get("location")) or "",
                    status=status,
                    description=_text(row.get("description")) or "",
                    requirements=_text(row.get("requirements")) or "",
                )
            )
        return ListResult(True, tuple(positions))

    def create_position(
        self,
        title: str,
        description: str,
        requirements: str,
        location: str,
        status: str,
    ) -> ActionResult:
        result = self._recruitment.create_position(
            title, description, requirements, location, status
        )
        return ActionResult(result.success, result.message)

    def update_position(
        self,
        position_id: int,
        title: str,
        description: str,
        requirements: str,
        location: str,
        status: str,
    ) -> ActionResult:
        result = self._recruitment.update_position(
            position_id,
            title,
            description,
            requirements,
            location,
            status,
        )
        return ActionResult(result.success, result.message)

    def list_assessments(self) -> ListResult[Assessment]:
        result = self._exams.list_exams()
        if not result.success:
            return ListResult(False, message=result.message)
        assessments: list[Assessment] = []
        for value in result.exams:
            row = _record(value)
            if row is None:
                return ListResult(False, message="Dữ liệu bài thi không hợp lệ.")
            exam_id = _integer(row.get("id"))
            title = _text(row.get("title"))
            duration = _integer(row.get("duration_min"))
            question_count = _integer(row.get("question_count"))
            if None in (exam_id, title, duration, question_count):
                return ListResult(False, message="Dữ liệu bài thi không đầy đủ.")
            assessments.append(
                Assessment(exam_id, title, duration, question_count)
            )
        return ListResult(True, tuple(assessments))

    def create_assessment(
        self,
        title: str,
        description: str,
        duration_minutes: int,
        questions: tuple[QuestionDraft, ...],
    ) -> ActionResult:
        if not questions:
            return ActionResult(False, "Thêm ít nhất một câu hỏi trước khi lưu.")
        created = self._exams.create_exam(
            title,
            description,
            duration_minutes,
            total_points=10 * len(questions),
        )
        if not created.success:
            return ActionResult(False, created.message)
        exam = _record(created.exam)
        exam_id = _integer(exam.get("id")) if exam is not None else None
        if exam_id is None:
            return ActionResult(False, "Controller không trả về mã bài thi hợp lệ.")

        for draft in questions:
            options = tuple(
                ExamOption(option, index == draft.correct_option_index)
                for index, option in enumerate(draft.options)
            )
            added = self._exams.add_question(
                exam_id,
                draft.prompt,
                draft.prompt,
                options,
                points=10,
            )
            if not added.success:
                return ActionResult(
                    False,
                    f"Bài thi nháp #{exam_id} chưa được công bố: {added.message}",
                )
        published = self._exams.publish_exam(exam_id)
        if not published.success:
            return ActionResult(
                False,
                f"Bài thi nháp #{exam_id} chưa được công bố: {published.message}",
            )
        return ActionResult(True, published.message)

    def list_candidates(self, search: str = "") -> ListResult[Candidate]:
        result = self._recruitment.list_candidates(search)
        if not result.success:
            return ListResult(False, message=result.message)
        candidates: list[Candidate] = []
        for value in result.candidates:
            row = _record(value)
            if row is None:
                return ListResult(False, message="Dữ liệu ứng viên không hợp lệ.")
            candidate_id = _integer(row.get("id"))
            full_name = _text(row.get("full_name"))
            email = _text(row.get("email"))
            if candidate_id is None or full_name is None or email is None:
                return ListResult(False, message="Dữ liệu ứng viên không đầy đủ.")
            candidates.append(Candidate(candidate_id, full_name, email))
        return ListResult(True, tuple(candidates))

    def send_invitation(
        self, position_id: int, assessment_id: int, candidate_id: int
    ) -> ActionResult:
        result = self._exams.invite_candidate(
            position_id, assessment_id, candidate_id
        )
        return ActionResult(result.success, result.message)

    def list_results(self) -> ListResult[AssessmentResultRow]:
        exams = self._exams.list_exams()
        if not exams.success:
            return ListResult(False, message=exams.message)
        results: list[AssessmentResultRow] = []
        for value in exams.exams:
            exam = _record(value)
            exam_id = _integer(exam.get("id")) if exam is not None else None
            if exam_id is None:
                return ListResult(False, message="Dữ liệu bài thi không đầy đủ.")
            submissions = self._exams.list_submissions(exam_id)
            if not submissions.success:
                return ListResult(False, message=submissions.message)
            for value in submissions.submissions:
                row = _record(value)
                if row is None:
                    return ListResult(False, message="Dữ liệu kết quả không hợp lệ.")
                candidate_name = _text(row.get("candidate_name"))
                position_title = _text(row.get("position_title"))
                assessment_title = _text(row.get("assessment_title"))
                status = _text(row.get("status"))
                submitted_at = _text(row.get("submitted_at"))
                invitation_id = _integer(row.get("invitation_id"))
                if None in (
                    candidate_name,
                    position_title,
                    assessment_title,
                    status,
                    submitted_at,
                    invitation_id,
                ):
                    return ListResult(False, message="Dữ liệu kết quả không đầy đủ.")
                score_value = row.get("score")
                max_score_value = row.get("max_score")
                score = (
                    float(score_value)
                    if isinstance(score_value, (int, float))
                    and not isinstance(score_value, bool)
                    else None
                )
                max_score = (
                    float(max_score_value)
                    if isinstance(max_score_value, (int, float))
                    and not isinstance(max_score_value, bool)
                    else None
                )
                results.append(
                    AssessmentResultRow(
                        candidate_name,
                        position_title,
                        assessment_title,
                        score,
                        max_score,
                        status,
                        submitted_at,
                        exam_id=exam_id,
                        invitation_id=invitation_id,
                    )
                )
        return ListResult(True, tuple(results))

    def release_results(self, exam_id: int) -> ActionResult:
        result = self._exams.release_results(exam_id)
        return ActionResult(result.success, result.message)


class CandidateAssessmentAdapter:
    """Translate invitation-oriented View calls to session-oriented APIs."""

    def __init__(self, exams: ExamController) -> None:
        self._exams = exams
        self._session_ids: dict[int, int] = {}
        self._invitations: dict[int, Record] = {}

    def list_invitations(self) -> ListResult[CandidateInvitation]:
        result = self._exams.list_invitations()
        if not result.success:
            return ListResult(False, message=result.message)
        invitations: list[CandidateInvitation] = []
        self._session_ids.clear()
        self._invitations.clear()
        for value in result.invitations:
            row = _record(value)
            if row is None:
                return ListResult(False, message="Dữ liệu lời mời không hợp lệ.")
            invitation_id = _integer(row.get("id"))
            company_name = _text(row.get("company_name"))
            position_title = _text(row.get("position_title"))
            assessment_title = _text(row.get("exam_title"))
            duration = _integer(row.get("duration_min"))
            status = _text(row.get("status"))
            if None in (
                invitation_id,
                company_name,
                position_title,
                assessment_title,
                duration,
                status,
            ):
                return ListResult(False, message="Dữ liệu lời mời không đầy đủ.")
            session_id = _integer(row.get("exam_session_id"))
            if session_id is not None:
                self._session_ids[invitation_id] = session_id
            self._invitations[invitation_id] = row
            invitations.append(
                CandidateInvitation(
                    invitation_id,
                    company_name,
                    position_title,
                    assessment_title,
                    duration,
                    self._view_invitation_status(row),
                    _text(row.get("scheduled_at")) or "",
                )
            )
        return ListResult(True, tuple(invitations))

    @staticmethod
    def _view_invitation_status(invitation: Record) -> str:
        status = invitation.get("status")
        if status == "pending":
            return "scheduled"
        if status == "accepted":
            session_status = invitation.get("session_status")
            return session_status if isinstance(session_status, str) else "accepted"
        return status if isinstance(status, str) else "unknown"

    def _session_id_for(self, invitation_id: int) -> int | None:
        session_id = self._session_ids.get(invitation_id)
        if session_id is not None:
            return session_id
        self.list_invitations()
        return self._session_ids.get(invitation_id)

    def get_exam(self, invitation_id: int) -> ExamLoadResult:
        if invitation_id not in self._invitations:
            self.list_invitations()
        invitation = self._invitations.get(invitation_id)
        if invitation is None:
            return ExamLoadResult(False, message="Không tìm thấy lời mời.")
        if invitation.get("status") == "pending":
            accepted = self._exams.accept_invitation(invitation_id)
            if not accepted.success:
                return ExamLoadResult(False, message=accepted.message)
            invitation = _record(accepted.invitation)
            if invitation is None:
                return ExamLoadResult(
                    False, message="Controller không trả về lời mời hợp lệ."
                )
            self._invitations[invitation_id] = invitation
        session_id = _integer(invitation.get("exam_session_id"))
        if session_id is None:
            session_id = self._session_ids.get(invitation_id)
        if session_id is None:
            return ExamLoadResult(False, message="Lời mời chưa có phiên thi.")
        self._session_ids[invitation_id] = session_id

        started = self._exams.start_exam(session_id)
        if not started.success:
            return ExamLoadResult(False, message=started.message)
        questions_result = self._exams.list_questions(session_id)
        if not questions_result.success:
            return ExamLoadResult(False, message=questions_result.message)

        questions: list[ExamQuestion] = []
        for value in questions_result.questions:
            row = _record(value)
            if row is None:
                return ExamLoadResult(False, message="Dữ liệu câu hỏi không hợp lệ.")
            question_id = _integer(row.get("id"))
            prompt = _text(row.get("content")) or _text(row.get("title"))
            if question_id is None or prompt is None:
                return ExamLoadResult(False, message="Dữ liệu câu hỏi không đầy đủ.")
            options_value = row.get("options")
            if not isinstance(options_value, Sequence) or isinstance(
                options_value, (str, bytes)
            ):
                return ExamLoadResult(False, message="Dữ liệu phương án không hợp lệ.")
            options: list[ViewExamOption] = []
            for option_value in options_value:
                option = _record(option_value)
                if option is None:
                    return ExamLoadResult(False, message="Dữ liệu phương án không hợp lệ.")
                option_id = _integer(option.get("id"))
                option_text = _text(option.get("content"))
                if option_id is None or option_text is None:
                    return ExamLoadResult(False, message="Dữ liệu phương án không đầy đủ.")
                options.append(ViewExamOption(option_id, option_text))
            selected = _integer(row.get("selected_option_id"))
            questions.append(
                ExamQuestion(
                    question_id,
                    prompt,
                    tuple(options),
                    selected_option_id=selected,
                )
            )

        exam_title = _text(invitation.get("exam_title"))
        duration = _integer(invitation.get("duration_min"))
        if exam_title is None or duration is None:
            return ExamLoadResult(False, message="Dữ liệu bài thi không đầy đủ.")
        return ExamLoadResult(
            True,
            ExamDetails(invitation_id, exam_title, duration, tuple(questions)),
        )

    def save_answer(
        self, invitation_id: int, question_id: int, option_id: int
    ) -> ActionResult:
        session_id = self._session_id_for(invitation_id)
        if session_id is None:
            return ActionResult(False, "Mở lời mời hợp lệ trước khi lưu đáp án.")
        result = self._exams.save_answer(session_id, question_id, option_id)
        return ActionResult(result.success, result.message)

    def submit_exam(self, invitation_id: int) -> SubmitResult:
        session_id = self._session_id_for(invitation_id)
        if session_id is None:
            return SubmitResult(False, message="Không tìm thấy phiên thi.")
        result = self._exams.submit_exam(session_id)
        if not result.success:
            return SubmitResult(False, message=result.message)
        return SubmitResult(
            True,
            CandidateResult(
                invitation_id,
                None,
                None,
                "submitted",
                message="Bài thi đã nộp; kết quả sẽ hiển thị sau khi được công bố.",
            ),
        )

    def get_result(self, invitation_id: int) -> CandidateResultResponse:
        session_id = self._session_id_for(invitation_id)
        if session_id is None:
            return CandidateResultResponse(
                False, message="Không tìm thấy phiên thi."
            )
        result = self._exams.get_result(session_id)
        if not result.success:
            return CandidateResultResponse(False, message=result.message)
        row = _record(result.result)
        if row is None:
            return CandidateResultResponse(
                False, message="Controller không trả về kết quả hợp lệ."
            )
        score = row.get("total_score", row.get("score"))
        max_score = row.get("max_score")
        submitted_at = _text(row.get("submitted_at")) or ""
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or isinstance(max_score, bool)
            or not isinstance(max_score, (int, float))
        ):
            return CandidateResultResponse(
                False, message="Kết quả đã công bố nhưng thiếu điểm hợp lệ."
            )
        return CandidateResultResponse(
            True,
            CandidateResult(
                invitation_id,
                float(score),
                float(max_score),
                "released",
                submitted_at,
                "Kết quả đã được công bố.",
            ),
        )


def create_recruitment_view_controllers() -> tuple[
    CompanyRecruitmentController, CandidateAssessmentAdapter
]:
    repository = RecruitmentRepository()
    recruitment = RecruitmentController(RecruitmentService(repository))
    exam_service = ExamService(repository, repository)
    exams = ExamController(exam_service)
    return CompanyRecruitmentAdapter(recruitment, exams), CandidateAssessmentAdapter(
        exams
    )
