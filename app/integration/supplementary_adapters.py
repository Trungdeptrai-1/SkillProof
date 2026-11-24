"""Adapters connecting supplementary Services and Views to SQLite persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime
from itertools import count

from app.services.auth_service import SessionManager
from client.views.extended_workflow_contracts import (
    ActiveExamSession,
    CandidatePublishedResult,
    CandidateSpecializedAssessment,
    CertificateEntry,
    CertificatePermissions,
    CertificateVerification,
    InterviewEntry,
    PendingGradingSubmission,
    WorkflowActionResult,
    WorkflowListResult,
)
from server.controllers.supplementary_workflow_controller import (
    CertificateController as ServiceCertificateController,
    ExamMonitoringController as ServiceExamMonitoringController,
    InterviewController as ServiceInterviewController,
    ManualAssessmentController as ServiceManualAssessmentController,
)
from server.models.recruitment_repository import RecruitmentRepository
from server.services.certificate_service import CertificateService
from server.services.exam_monitoring_service import ExamMonitoringService
from server.services.interview_service import InterviewService
from server.services.manual_assessment_service import ManualAssessmentService

Record = Mapping[str, object]


def _record(value: object) -> Record | None:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    return None


def _identity() -> tuple[int, str] | None:
    session = SessionManager.instance()
    user = session.current_user
    if not session.is_logged_in or user is None:
        return None
    return user.id, user.role


class _ManualAssessmentRepositoryAdapter:
    def __init__(self, repository: RecruitmentRepository) -> None:
        self._repository = repository

    def create_manual_question(self, *args, **kwargs):
        return None

    def publish_manual_question(self, *args, **kwargs):
        return None

    def attach_manual_question(self, *args, **kwargs):
        return None

    def get_candidate_session(self, session_id: int, candidate_id: int):
        return self._repository.get_candidate_session(session_id, candidate_id)

    def list_candidate_questions(self, session_id: int, candidate_id: int):
        return self._repository.list_candidate_questions(session_id, candidate_id)

    def save_candidate_response(
        self,
        session_id: int,
        candidate_id: int,
        question_id: int,
        *,
        answer_text: str | None,
        answer_code: str | None,
        programming_language: str | None = None,
    ):
        answer = answer_text if answer_text is not None else answer_code
        if answer is None:
            return None
        return self._repository.save_candidate_written_answer(
            session_id,
            candidate_id,
            question_id,
            answer,
            programming_language=programming_language,
        )

    def submit_manual_session_once(self, session_id: int, candidate_id: int):
        return self._repository.submit_exam_for_grading(session_id, candidate_id)

    def can_grade_session(self, grader_id: int, role: str, session_id: int) -> bool:
        context = self._repository.get_exam_session_context(session_id)
        if context is None:
            return False
        company_id = context.get("company_id")
        return (
            isinstance(company_id, int)
            and bool(
                self._repository.list_manual_grading_items(
                    company_id, session_id, grader_id
                )
            )
        )

    def list_manual_submissions_for_grader(self, grader_id: int, role: str):
        results = []
        for row in self._repository.list_reviewer_submissions(grader_id, role):
            session_id = row.get("exam_session_id")
            company_id = row.get("company_id")
            if (
                isinstance(session_id, int)
                and isinstance(company_id, int)
                and self._repository.list_manual_grading_items(
                    company_id, session_id, grader_id
                )
            ):
                results.append(row)
        return results

    def get_manual_submission_for_grader(
        self, session_id: int, grader_id: int, role: str
    ):
        return next(
            (
                item
                for item in self.list_manual_submissions_for_grader(grader_id, role)
                if item.get("exam_session_id") == session_id
            ),
            None,
        )

    def list_manual_answers_for_grading(
        self, session_id: int, grader_id: int, role: str
    ):
        context = self._repository.get_exam_session_context(session_id)
        company_id = context.get("company_id") if context is not None else None
        if not isinstance(company_id, int):
            return []
        answers = self._repository.list_manual_grading_items(
            company_id, session_id, grader_id
        )
        for answer in answers:
            answer["id"] = answer["question_id"]
            answer["question_type"] = answer.get("question_type")
        return answers

    def get_manual_answer_for_grading(
        self, session_id: int, question_id: int, grader_id: int, role: str
    ):
        return next(
            (
                item
                for item in self.list_manual_answers_for_grading(
                    session_id, grader_id, role
                )
                if item.get("question_id") == question_id
            ),
            None,
        )

    def grade_manual_answer_once(
        self,
        session_id: int,
        question_id: int,
        grader_id: int,
        *,
        score: float,
        feedback: str,
        reason: str,
    ):
        context = self._repository.get_exam_session_context(session_id)
        company_id = context.get("company_id") if context is not None else None
        if not isinstance(company_id, int):
            return None
        return _record(
            self._repository.grade_exam_answer(
                company_id,
                grader_id,
                session_id,
                question_id,
                score=score,
                feedback=feedback,
                revision_reason=reason or None,
            )
        )

    def get_manual_grading_progress(
        self, session_id: int, grader_id: int, role: str
    ):
        if not self.can_grade_session(grader_id, role, session_id):
            return None
        answers = self.list_manual_answers_for_grading(session_id, grader_id, role)
        all_answers = self._repository.list_exam_answers_for_grading(
            self._company_id(session_id), session_id, requester_id=grader_id
        )
        return {
            "question_count": len(all_answers),
            "graded_count": sum(answer.is_graded for answer in all_answers),
            "manual_question_count": len(answers),
        }

    def finalize_manual_grading_once(
        self, session_id: int, grader_id: int, role: str
    ):
        submission = self.get_manual_submission_for_grader(
            session_id, grader_id, role
        )
        if submission is None or submission.get("status") != "graded":
            return None
        return submission

    def release_manual_result_once(self, session_id: int, company_id: int):
        return self._repository.release_submission_once(company_id, session_id)

    def get_candidate_submission(self, session_id: int, candidate_id: int):
        return self._repository.get_candidate_submission(session_id, candidate_id)

    def get_candidate_result(self, session_id: int, candidate_id: int):
        result = self._repository.get_candidate_result(session_id, candidate_id)
        if result is None:
            return None
        return {
            "score": result.get("score"),
            "max_score": result.get("max_score"),
            "released_at": result.get("released_at"),
            "status": result.get("submission_status"),
        }

    def _company_id(self, session_id: int) -> int:
        context = self._repository.get_exam_session_context(session_id)
        company_id = context.get("company_id") if context is not None else None
        return company_id if isinstance(company_id, int) else 0


class _MonitoringRepositoryAdapter:
    def __init__(self, repository: RecruitmentRepository) -> None:
        self._repository = repository

    def get_candidate_session(self, session_id: int, candidate_id: int):
        return self._repository.get_candidate_session(session_id, candidate_id)

    def record_candidate_monitor_event(
        self,
        session_id: int,
        candidate_id: int,
        event_type: str,
        *,
        timeout_verified: bool,
        focus_review_threshold: int,
    ):
        if event_type == "timeout":
            self._repository.record_exam_session_event(
                session_id,
                candidate_id,
                "timeout",
                details={"source": "local_exam_timer"},
            )
            return {"outcome": "timeout_recorded", "focus_event_count": 0}
        event = self._repository.record_exam_session_event(
            session_id,
            candidate_id,
            event_type,
            is_violation=False,
            details={"source": "local_application_focus"},
        )
        events = self._repository.list_exam_session_events(
            session_id, candidate_id
        )
        focus_count = sum(item.event_type == "focus_lost" for item in events)
        outcome = (
            "manual_review_required"
            if focus_count >= focus_review_threshold
            else "warning"
        )
        return {
            "event_id": event.id,
            "outcome": outcome,
            "focus_event_count": focus_count,
        }

    def can_review_monitor_events(
        self, reviewer_id: int, role: str, session_id: int
    ) -> bool:
        context = self._repository.get_exam_session_context(session_id)
        company_id = context.get("company_id") if context is not None else None
        return (
            role in {"company", "expert"}
            and isinstance(company_id, int)
            and self._repository.get_company_exam_proctoring_session(
                company_id, session_id, requester_id=reviewer_id
            )
            is not None
        )

    def list_monitor_events_for_reviewer(
        self, reviewer_id: int, role: str, session_id: int
    ):
        context = self._repository.get_exam_session_context(session_id)
        company_id = context.get("company_id") if context is not None else None
        if not isinstance(company_id, int):
            return ()
        events = self._repository.list_company_exam_session_events(
            company_id, session_id, requester_id=reviewer_id
        )
        return tuple(_record(event) for event in events)


class _InterviewRepositoryAdapter:
    def __init__(self, repository: RecruitmentRepository) -> None:
        self._repository = repository

    def create_interview(
        self, company_id: int, candidate_id: int, **kwargs
    ):
        return _record(
            self._repository.schedule_interview(
                company_id,
                candidate_id,
                title=kwargs["title"],
                description=kwargs["description"],
                scheduled_at=kwargs["scheduled_at"],
                duration_min=kwargs["duration_min"],
                meeting_url=kwargs["meeting_url"],
                interviewer_ids=kwargs["expert_ids"],
            )
        )

    def list_user_interviews(self, user_id: int, role: str):
        rows = self._repository.list_user_interview_records(user_id, role)
        return tuple(_record(row) for row in rows)

    def get_interview_for_user(
        self, interview_id: int, user_id: int, role: str
    ):
        return next(
            (
                item
                for item in self.list_user_interviews(user_id, role)
                if item is not None and item.get("id") == interview_id
            ),
            None,
        )

    def update_interview_status(
        self, interview_id: int, user_id: int, role: str, status: str
    ):
        current = self.get_interview_for_user(interview_id, user_id, role)
        if current is None:
            return None
        company_id = current.get("company_id")
        if role == "company":
            company_id = user_id
        if not isinstance(company_id, int):
            return None
        return _record(
            self._repository.set_interview_status(company_id, interview_id, status)
        )

    def can_evaluate_interview(self, interview_id: int, expert_id: int) -> bool:
        return self._repository.can_evaluate_interview(interview_id, expert_id)

    def save_interview_evaluation(self, interview_id: int, expert_id: int, **kwargs):
        return _record(
            self._repository.save_interview_evaluation(
                interview_id,
                expert_id,
                technical_score=kwargs["technical_score"],
                communication_score=kwargs["communication_score"],
                problem_solving_score=kwargs["problem_solving_score"],
                overall_rating=kwargs["overall_rating"],
                feedback=kwargs["feedback"],
                recommendation=kwargs["recommendation"],
            )
        )

    def list_interview_evaluations(
        self, interview_id: int, user_id: int, role: str
    ):
        if role == "company":
            records = self._repository.list_interview_evaluations(
                user_id, interview_id
            )
        elif role == "expert":
            records = self._repository.list_expert_interview_evaluations(
                user_id, interview_id
            )
        else:
            return ()
        return tuple(_record(record) for record in records)


class _CertificateRepositoryAdapter:
    def __init__(self, repository: RecruitmentRepository) -> None:
        self._repository = repository

    def get_approved_assessment(self, candidate_id: int, skill_id: int):
        return self._repository.get_approved_assessment(candidate_id, skill_id)

    def get_account_role(self, user_id: int):
        return self._repository.get_account_role(user_id)

    def is_active_candidate(self, candidate_id: int):
        return self._repository.is_active_candidate(candidate_id)

    def get_certificate_for_candidate(self, candidate_id: int, skill_id: int):
        return self._repository.get_certificate_for_candidate(candidate_id, skill_id)

    def issue_certificate(self, candidate_id: int, skill_id: int, **kwargs):
        return _record(
            self._repository.issue_certificate(
                candidate_id,
                skill_id,
                score=kwargs["score"],
                cert_code=kwargs["cert_code"],
                expires_at=kwargs["expires_at"],
            )
        )

    def get_certificate_by_code(self, cert_code: str):
        return self._repository.get_certificate_by_code(cert_code)

    def get_certificate_by_id(self, certificate_id: int):
        return self._repository.get_certificate_by_id(certificate_id)

    def can_view_certificate(self, certificate_id: int, viewer_id: int, role: str):
        return self._repository.can_view_certificate(certificate_id, viewer_id, role)

    def list_candidate_certificates(self, candidate_id: int):
        return tuple(
            self._repository.list_certificates_for_viewer(candidate_id, "candidate")
        )

    def revoke_certificate(self, certificate_id: int):
        identity = _identity()
        if identity is None or identity[1] != "admin":
            return None
        return _record(
            self._repository.revoke_certificate(
                certificate_id, identity[0], "Revoked by administrator."
            )
        )


class CandidateSpecializedAssessmentViewAdapter:
    def __init__(
        self,
        repository: RecruitmentRepository,
        controller: ServiceManualAssessmentController,
    ) -> None:
        self._repository = repository
        self._controller = controller
        self._assignments: dict[int, tuple[int, int]] = {}

    def list_assignments(self) -> WorkflowListResult[CandidateSpecializedAssessment]:
        identity = _identity()
        if identity is None or identity[1] != "candidate":
            return WorkflowListResult(False, message="Candidate cần đăng nhập.")
        items = []
        assignments: dict[int, tuple[int, int]] = {}
        next_id = count(1)
        for invitation in self._repository.list_candidate_invitations(identity[0]):
            session_id = invitation.get("exam_session_id")
            if (
                invitation.get("status") != "accepted"
                or not isinstance(session_id, int)
            ):
                continue
            submission = self._repository.get_candidate_submission(
                session_id, identity[0]
            )
            status = (
                str(submission["status"])
                if submission is not None
                else str(invitation.get("session_status") or "")
            )
            if status == "in_progress":
                result = self._controller.list_questions(session_id)
                if not result.success:
                    continue
                questions = result.records
            else:
                questions = self._repository.list_candidate_question_summaries(
                    session_id, identity[0]
                )
            for question in questions:
                kind = question.get("question_type")
                if kind not in {"essay", "coding"}:
                    continue
                item_id = next(next_id)
                assignments[item_id] = (session_id, int(question["id"]))
                languages = question.get("supported_languages", ())
                if isinstance(languages, str):
                    try:
                        import json

                        languages = json.loads(languages)
                    except ValueError:
                        return WorkflowListResult(
                            False, message="Ngôn ngữ Coding lưu trong bài thi không hợp lệ."
                        )
                if not isinstance(languages, Sequence):
                    languages = ()
                items.append(
                    CandidateSpecializedAssessment(
                        id=item_id,
                        title=str(question.get("title") or invitation.get("exam_title") or ""),
                        kind=kind,
                        prompt=str(question.get("content") or ""),
                        status=status,
                        duration_minutes=int(invitation.get("duration_min") or 0),
                        supported_languages=tuple(
                            item for item in languages if isinstance(item, str)
                        ),
                        saved_answer=str(
                            question.get("answer_text")
                            or question.get("answer_code")
                            or ""
                        ),
                        saved_language=str(
                            question.get("programming_language") or ""
                        ),
                    )
                )
        self._assignments = assignments
        return WorkflowListResult(True, tuple(items))

    def save_answer(
        self, assignment_id: int, answer: str, language: str
    ) -> WorkflowActionResult:
        identity = _identity()
        if identity is None or identity[1] != "candidate":
            return WorkflowActionResult(False, "Candidate cần đăng nhập.")
        target = self._assignments.get(assignment_id)
        if target is None:
            return WorkflowActionResult(False, "Không tìm thấy câu hỏi đã chọn.")
        session_id, question_id = target
        question = next(
            (
                item
                for item in self._repository.list_candidate_questions(
                    session_id, identity[0]
                )
                if item.get("id") == question_id
            ),
            None,
        )
        if question is None:
            return WorkflowActionResult(False, "Phiên thi không còn nhận câu trả lời.")
        result = self._controller.save_response(
            session_id,
            question_id,
            answer_text=answer if question.get("question_type") == "essay" else None,
            answer_code=answer if question.get("question_type") == "coding" else None,
            programming_language=language or None,
        )
        return WorkflowActionResult(result.success, result.message, result.status)

    def submit_answer(
        self, assignment_id: int, answer: str, language: str
    ) -> WorkflowActionResult:
        saved = self.save_answer(assignment_id, answer, language)
        if not saved.success:
            return saved
        session_id, _ = self._assignments[assignment_id]
        result = self._controller.submit(session_id)
        return WorkflowActionResult(
            result.success,
            result.message,
            "submitted" if result.success else result.status,
        )

    def get_result(self, assignment_id: int) -> CandidatePublishedResult:
        target = self._assignments.get(assignment_id)
        if target is None:
            return CandidatePublishedResult(False, message="Không tìm thấy bài thi.")
        result = self._controller.get_result(target[0])
        record = result.record or {}
        return CandidatePublishedResult(
            success=result.success,
            released=result.success,
            score=record.get("score") if isinstance(record.get("score"), (int, float)) else None,
            max_score=(
                record.get("max_score")
                if isinstance(record.get("max_score"), (int, float))
                else None
            ),
            message=result.message,
        )


class ManualGradingViewAdapter:
    def __init__(self, controller: ServiceManualAssessmentController) -> None:
        self._controller = controller
        self._items: dict[int, tuple[int, int]] = {}

    def list_submissions_for_grading(
        self,
    ) -> WorkflowListResult[PendingGradingSubmission]:
        result = self._controller.list_submissions_for_grading()
        if not result.success:
            return WorkflowListResult(False, message=result.message)
        items: list[PendingGradingSubmission] = []
        mapping: dict[int, tuple[int, int]] = {}
        next_id = count(1)
        for submission in result.records:
            session_id = submission.get("exam_session_id")
            if not isinstance(session_id, int):
                continue
            answer_result = self._controller.list_answers_for_grading(session_id)
            if not answer_result.success:
                continue
            for answer in answer_result.records:
                kind = answer.get("question_type")
                if kind not in {"essay", "coding"}:
                    continue
                item_id = next(next_id)
                mapping[item_id] = (session_id, int(answer["question_id"]))
                items.append(
                    PendingGradingSubmission(
                        id=item_id,
                        candidate_name=str(answer.get("candidate_name") or ""),
                        assessment_title=str(answer.get("exam_title") or ""),
                        kind=kind,
                        prompt=str(answer.get("question_content") or ""),
                        submitted_answer=str(
                            answer.get("answer_text")
                            or answer.get("answer_code")
                            or ""
                        ),
                        status=(
                            "graded"
                            if bool(answer.get("is_graded"))
                            else str(answer.get("submission_status") or "grading")
                        ),
                        max_score=float(answer.get("max_score") or 0),
                        language=str(answer.get("programming_language") or ""),
                        feedback=str(answer.get("feedback") or ""),
                        score=(
                            float(answer["score"])
                            if isinstance(answer.get("score"), (int, float))
                            else None
                        ),
                    )
                )
        self._items = mapping
        return WorkflowListResult(True, tuple(items))

    def save_grade(
        self, submission_id: int, score: float, feedback: str
    ) -> WorkflowActionResult:
        target = self._items.get(submission_id)
        if target is None:
            return WorkflowActionResult(False, "Không tìm thấy bài cần chấm.")
        result = self._controller.grade_answer(
            target[0], target[1], score, feedback
        )
        return WorkflowActionResult(result.success, result.message, result.status)

    def release_result(self, submission_id: int) -> WorkflowActionResult:
        target = self._items.get(submission_id)
        if target is None:
            return WorkflowActionResult(False, "Không tìm thấy bài cần công bố.")
        finalized = self._controller.finalize_grading(target[0])
        if not finalized.success:
            return WorkflowActionResult(False, finalized.message, finalized.status)
        result = self._controller.release_result(target[0])
        return WorkflowActionResult(result.success, result.message, result.status)


class ExamMonitorViewAdapter:
    def __init__(
        self,
        repository: RecruitmentRepository,
        controller: ServiceExamMonitoringController,
    ) -> None:
        self._repository = repository
        self._controller = controller

    def get_active_session(self) -> ActiveExamSession | None:
        identity = _identity()
        if identity is None or identity[1] != "candidate":
            return None
        for invitation in self._repository.list_candidate_invitations(identity[0]):
            session_id = invitation.get("exam_session_id")
            if (
                invitation.get("status") != "accepted"
                or invitation.get("session_status") != "in_progress"
                or not isinstance(session_id, int)
            ):
                continue
            session = self._repository.get_candidate_session(session_id, identity[0])
            if session is None:
                continue
            started_at = session.get("started_at")
            duration = session.get("duration_min")
            if not isinstance(started_at, str) or not isinstance(duration, int):
                continue
            try:
                started = datetime.fromisoformat(started_at)
            except ValueError:
                continue
            now = datetime.now(started.tzinfo) if started.tzinfo else datetime.now()
            remaining = max(0, duration * 60 - int((now - started).total_seconds()))
            return ActiveExamSession(
                session_id,
                str(invitation.get("exam_title") or ""),
                "in_progress",
                remaining,
            )
        return None

    def start_monitoring(self, session_id: int) -> WorkflowActionResult:
        identity = _identity()
        if identity is None or identity[1] != "candidate":
            return WorkflowActionResult(False, "Candidate cần đăng nhập.")
        result = self._repository.start_exam_proctoring_session(
            session_id, identity[0], consent_for_evidence=False
        )
        if result is None or result.status != "active":
            return WorkflowActionResult(False, "Phiên thi không còn hoạt động.")
        return WorkflowActionResult(True, "Đã bắt đầu ghi nhận sự kiện focus.")

    def record_focus_lost(self, session_id: int) -> WorkflowActionResult:
        result = self._controller.record_event(session_id, "focus_lost")
        return WorkflowActionResult(result.success, result.message, str(result.value or ""))

    def record_timeout(self, session_id: int) -> WorkflowActionResult:
        result = self._controller.record_event(session_id, "timeout")
        return WorkflowActionResult(result.success, result.message, str(result.value or ""))

    def stop_monitoring(self, session_id: int) -> WorkflowActionResult:
        identity = _identity()
        if identity is None or identity[1] != "candidate":
            return WorkflowActionResult(False, "Candidate cần đăng nhập.")
        result = self._repository.finish_exam_proctoring_session(
            session_id, identity[0]
        )
        return WorkflowActionResult(
            result is not None,
            "Đã kết thúc ghi nhận sự kiện."
            if result is not None
            else "Không tìm thấy phiên giám sát đang hoạt động.",
        )


class InterviewViewAdapter:
    def __init__(self, controller: ServiceInterviewController) -> None:
        self._controller = controller

    def list_interviews(self) -> WorkflowListResult[InterviewEntry]:
        result = self._controller.list_mine()
        if not result.success:
            return WorkflowListResult(False, message=result.message)
        role = _identity()[1] if _identity() is not None else ""
        entries = []
        for record in result.records:
            if record is None:
                continue
            notes = ""
            if role in {"company", "expert"}:
                evaluations = self._controller.list_evaluations(
                    int(record["id"])
                )
                if evaluations.success:
                    notes = "\n".join(
                        str(item.get("feedback") or "")
                        for item in evaluations.records
                        if item.get("feedback")
                    )
            entries.append(
                InterviewEntry(
                    id=int(record["id"]),
                    title=str(record.get("title") or ""),
                    candidate_name=str(record.get("candidate_name") or ""),
                    scheduled_at=str(record.get("scheduled_at") or ""),
                    status=str(record.get("status") or ""),
                    meeting_url=str(record.get("meeting_url") or ""),
                    evaluation_notes=(
                        notes
                        if role != "candidate"
                        else ""
                    ),
                )
            )
        return WorkflowListResult(True, tuple(entries))

    def save_evaluation(
        self,
        interview_id: int,
        notes: str,
        technical_score: int = 3,
        communication_score: int = 3,
        problem_solving_score: int = 3,
        overall_rating: int = 3,
    ) -> WorkflowActionResult:
        result = self._controller.evaluate(
            interview_id,
            technical_score=technical_score,
            communication_score=communication_score,
            problem_solving_score=problem_solving_score,
            overall_rating=overall_rating,
            feedback=notes,
        )
        return WorkflowActionResult(result.success, result.message, result.status)

    def schedule_interview(
        self,
        candidate_id: int,
        title: str,
        scheduled_at: str,
        expert_ids: tuple[int, ...] = (),
    ) -> WorkflowActionResult:
        result = self._controller.schedule(
            candidate_id,
            title,
            scheduled_at,
            duration_min=60,
            expert_ids=expert_ids,
        )
        return WorkflowActionResult(result.success, result.message, result.status)

    def update_status(
        self, interview_id: int, status: str
    ) -> WorkflowActionResult:
        result = self._controller.update_status(interview_id, status)
        return WorkflowActionResult(result.success, result.message, result.status)


class CertificateViewAdapter:
    def __init__(
        self,
        repository: RecruitmentRepository,
        controller: ServiceCertificateController,
    ) -> None:
        self._repository = repository
        self._controller = controller

    def get_permissions(self) -> CertificatePermissions:
        identity = _identity()
        if identity is None:
            return CertificatePermissions()
        return CertificatePermissions(
            can_issue=identity[1] == "admin",
            can_verify=identity[1] in {"admin", "candidate", "company", "expert"},
        )

    def list_certificates(self) -> WorkflowListResult[CertificateEntry]:
        identity = _identity()
        if identity is None:
            return WorkflowListResult(False, message="Vui lòng đăng nhập.")
        rows = self._repository.list_certificates_for_viewer(*identity)
        entries = tuple(
            CertificateEntry(
                id=int(row["id"]),
                cert_code=str(row["cert_code"]),
                subject_name=str(row["subject_name"]),
                skill_name=str(row["skill_name"]),
                status=str(row["status"]),
                issued_at=str(row["issued_at"]),
                expires_at=str(row.get("expires_at") or ""),
                score=(
                    float(row["score"])
                    if isinstance(row.get("score"), (int, float))
                    else None
                ),
            )
            for row in rows
        )
        return WorkflowListResult(True, entries)

    def issue_certificate(
        self, user_id: int, skill_id: int, score: float | None = None
    ) -> WorkflowActionResult:
        result = self._controller.issue(user_id, skill_id)
        return WorkflowActionResult(result.success, result.message, result.status)

    def verify_certificate(self, cert_code: str) -> CertificateVerification:
        result = self._controller.verify(cert_code)
        if result.record is None:
            return CertificateVerification(False, message=result.message)
        row = result.record
        return CertificateVerification(
            result.success,
            CertificateEntry(
                id=int(row["id"]),
                cert_code=str(row["cert_code"]),
                subject_name=str(row.get("subject_name") or ""),
                skill_name=str(row.get("skill_name") or ""),
                status=str(row.get("status") or ""),
                issued_at=str(row.get("issued_at") or ""),
                expires_at=str(row.get("expires_at") or ""),
                score=(
                    float(row["score"])
                    if isinstance(row.get("score"), (int, float))
                    else None
                ),
            ),
            result.message,
        )

    def revoke_certificate(self, certificate_id: int) -> WorkflowActionResult:
        result = self._controller.revoke(certificate_id)
        return WorkflowActionResult(result.success, result.message, result.status)


def create_supplementary_view_controllers(
    repository: RecruitmentRepository | None = None,
):
    repo = repository or RecruitmentRepository()
    manual_service = ManualAssessmentService(_ManualAssessmentRepositoryAdapter(repo))
    monitoring_service = ExamMonitoringService(_MonitoringRepositoryAdapter(repo))
    interview_service = InterviewService(_InterviewRepositoryAdapter(repo))
    certificate_service = CertificateService(_CertificateRepositoryAdapter(repo))
    manual = ServiceManualAssessmentController(manual_service)
    monitoring = ServiceExamMonitoringController(monitoring_service)
    interview = ServiceInterviewController(interview_service)
    certificate = ServiceCertificateController(certificate_service)
    return (
        CandidateSpecializedAssessmentViewAdapter(repo, manual),
        ManualGradingViewAdapter(manual),
        ExamMonitorViewAdapter(repo, monitoring),
        InterviewViewAdapter(interview),
        CertificateViewAdapter(repo, certificate),
    )
