"""Request boundaries for manual assessments, interviews, certificates, and monitoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from server.services.certificate_service import CertificateService
from server.services.exam_monitoring_service import ExamMonitoringService
from server.services.interview_service import InterviewService
from server.services.manual_assessment_service import ManualAssessmentService
from server.services.workflow_result import WorkflowResult


def _invalid_input() -> WorkflowResult:
    return WorkflowResult("invalid_input", "Dữ liệu đầu vào không hợp lệ.")


class ManualAssessmentController:
    def __init__(self, service: ManualAssessmentService) -> None:
        self._service = service

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
        if not all(
            isinstance(value, str)
            for value in (title, content, question_type, difficulty, test_cases, reference_answer)
        ):
            return _invalid_input()
        if isinstance(points, bool) or not isinstance(points, (int, float)):
            return _invalid_input()
        return self._service.create_question(
            title,
            content,
            question_type,
            points,
            difficulty=difficulty,
            test_cases=test_cases,
            reference_answer=reference_answer,
        )

    def publish_question(self, question_id: int) -> WorkflowResult:
        if isinstance(question_id, bool) or not isinstance(question_id, int):
            return _invalid_input()
        return self._service.publish_question(question_id)

    def attach_question(
        self, exam_id: int, question_id: int, points: float
    ) -> WorkflowResult:
        if (
            isinstance(exam_id, bool)
            or not isinstance(exam_id, int)
            or isinstance(question_id, bool)
            or not isinstance(question_id, int)
            or isinstance(points, bool)
            or not isinstance(points, (int, float))
        ):
            return _invalid_input()
        return self._service.attach_question(exam_id, question_id, points)

    def list_questions(self, session_id: int) -> WorkflowResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return _invalid_input()
        return self._service.list_questions(session_id)

    def save_response(
        self,
        session_id: int,
        question_id: int,
        *,
        answer_text: str | None = None,
        answer_code: str | None = None,
        programming_language: str | None = None,
    ) -> WorkflowResult:
        if (
            isinstance(session_id, bool)
            or not isinstance(session_id, int)
            or isinstance(question_id, bool)
            or not isinstance(question_id, int)
            or (answer_text is not None and not isinstance(answer_text, str))
            or (answer_code is not None and not isinstance(answer_code, str))
            or (
                programming_language is not None
                and not isinstance(programming_language, str)
            )
        ):
            return _invalid_input()
        arguments = {
            "answer_text": answer_text,
            "answer_code": answer_code,
        }
        if programming_language is not None:
            arguments["programming_language"] = programming_language
        return self._service.save_response(session_id, question_id, **arguments)

    def submit(self, session_id: int) -> WorkflowResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return _invalid_input()
        return self._service.submit(session_id)

    def list_submissions_for_grading(self) -> WorkflowResult:
        return self._service.list_submissions_for_grading()

    def list_answers_for_grading(self, session_id: int) -> WorkflowResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return _invalid_input()
        return self._service.list_answers_for_grading(session_id)

    def grade_answer(
        self,
        session_id: int,
        question_id: int,
        score: float,
        feedback: str,
        *,
        reason: str = "",
    ) -> WorkflowResult:
        if (
            isinstance(session_id, bool)
            or not isinstance(session_id, int)
            or isinstance(question_id, bool)
            or not isinstance(question_id, int)
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not isinstance(feedback, str)
            or not isinstance(reason, str)
        ):
            return _invalid_input()
        return self._service.grade_answer(
            session_id, question_id, score, feedback, reason=reason
        )

    def finalize_grading(self, session_id: int) -> WorkflowResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return _invalid_input()
        return self._service.finalize_grading(session_id)

    def release_result(self, session_id: int) -> WorkflowResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return _invalid_input()
        return self._service.release_result(session_id)

    def get_result(self, session_id: int) -> WorkflowResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return _invalid_input()
        return self._service.get_result(session_id)


class InterviewController:
    def __init__(self, service: InterviewService) -> None:
        self._service = service

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
        if (
            isinstance(candidate_id, bool)
            or not isinstance(candidate_id, int)
            or not isinstance(title, str)
            or not isinstance(scheduled_at, str)
            or not isinstance(description, str)
            or (meeting_url is not None and not isinstance(meeting_url, str))
            or isinstance(duration_min, bool)
            or not isinstance(duration_min, int)
            or isinstance(expert_ids, (str, bytes))
            or not isinstance(expert_ids, Sequence)
        ):
            return _invalid_input()
        return self._service.schedule(
            candidate_id,
            title,
            scheduled_at,
            description=description,
            duration_min=duration_min,
            meeting_url=meeting_url,
            expert_ids=expert_ids,
        )

    def list_mine(self) -> WorkflowResult:
        return self._service.list_mine()

    def get(self, interview_id: int) -> WorkflowResult:
        if isinstance(interview_id, bool) or not isinstance(interview_id, int):
            return _invalid_input()
        return self._service.get(interview_id)

    def get_meeting_link(self, interview_id: int) -> WorkflowResult:
        if isinstance(interview_id, bool) or not isinstance(interview_id, int):
            return _invalid_input()
        return self._service.get_meeting_link(interview_id)

    def list_participants(self, interview_id: int) -> WorkflowResult:
        if isinstance(interview_id, bool) or not isinstance(interview_id, int):
            return _invalid_input()
        return self._service.list_participants(interview_id)

    def update_status(self, interview_id: int, status: str) -> WorkflowResult:
        if (
            isinstance(interview_id, bool)
            or not isinstance(interview_id, int)
            or not isinstance(status, str)
        ):
            return _invalid_input()
        return self._service.update_status(interview_id, status)

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
        scores = (
            technical_score,
            communication_score,
            problem_solving_score,
            overall_rating,
        )
        if (
            isinstance(interview_id, bool)
            or not isinstance(interview_id, int)
            or any(isinstance(score, bool) or not isinstance(score, int) for score in scores)
            or not isinstance(feedback, str)
            or not isinstance(recommendation, str)
        ):
            return _invalid_input()
        return self._service.evaluate(
            interview_id,
            technical_score=technical_score,
            communication_score=communication_score,
            problem_solving_score=problem_solving_score,
            overall_rating=overall_rating,
            feedback=feedback,
            recommendation=recommendation,
        )

    def list_evaluations(self, interview_id: int) -> WorkflowResult:
        if isinstance(interview_id, bool) or not isinstance(interview_id, int):
            return _invalid_input()
        return self._service.list_evaluations(interview_id)


class CertificateController:
    def __init__(self, service: CertificateService) -> None:
        self._service = service

    def issue(
        self, candidate_id: int, skill_id: int, *, expires_at: str | None = None
    ) -> WorkflowResult:
        if (
            isinstance(candidate_id, bool)
            or not isinstance(candidate_id, int)
            or isinstance(skill_id, bool)
            or not isinstance(skill_id, int)
            or (expires_at is not None and not isinstance(expires_at, str))
        ):
            return _invalid_input()
        return self._service.issue(candidate_id, skill_id, expires_at=expires_at)

    def get_mine(self) -> WorkflowResult:
        return self._service.get_mine()

    def verify(self, cert_code: str) -> WorkflowResult:
        if not isinstance(cert_code, str):
            return _invalid_input()
        return self._service.verify(cert_code)

    def revoke(self, certificate_id: int) -> WorkflowResult:
        if isinstance(certificate_id, bool) or not isinstance(certificate_id, int):
            return _invalid_input()
        return self._service.revoke(certificate_id)


class ExamMonitoringController:
    def __init__(self, service: ExamMonitoringService) -> None:
        self._service = service

    def get_active_session(self) -> WorkflowResult:
        return self._service.get_active_exam_session()

    def start_session(
        self, session_id: int, *, consent_for_evidence: bool = False
    ) -> WorkflowResult:
        if (
            isinstance(session_id, bool)
            or not isinstance(session_id, int)
            or not isinstance(consent_for_evidence, bool)
        ):
            return _invalid_input()
        return self._service.start_session(
            session_id, consent_for_evidence=consent_for_evidence
        )

    def get_session(self, session_id: int) -> WorkflowResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return _invalid_input()
        return self._service.get_session(session_id)

    def finish_session(self, session_id: int) -> WorkflowResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return _invalid_input()
        return self._service.finish_session(session_id)

    def record_event(
        self,
        session_id: int,
        event_type: str,
        *,
        details: Mapping[str, object] | None = None,
        evidence_uri: str | None = None,
    ) -> WorkflowResult:
        if (
            isinstance(session_id, bool)
            or not isinstance(session_id, int)
            or not isinstance(event_type, str)
            or (details is not None and not isinstance(details, Mapping))
            or (evidence_uri is not None and not isinstance(evidence_uri, str))
        ):
            return _invalid_input()
        return self._service.record_event(
            session_id,
            event_type,
            details=details,
            evidence_uri=evidence_uri,
        )

    def record_camera_status(
        self,
        session_id: int,
        status: str,
        *,
        evidence_uri: str | None = None,
    ) -> WorkflowResult:
        event_types = {
            "active": "camera_active",
            "disconnected": "camera_disconnected",
            "ended": "camera_ended",
        }
        if (
            isinstance(session_id, bool)
            or not isinstance(session_id, int)
            or not isinstance(status, str)
            or (evidence_uri is not None and not isinstance(evidence_uri, str))
        ):
            return _invalid_input()
        event_type = event_types.get(status)
        if event_type is None:
            return _invalid_input()
        return self._service.record_event(
            session_id, event_type, evidence_uri=evidence_uri
        )

    def list_events(
        self, session_id: int, *, violations_only: bool = False
    ) -> WorkflowResult:
        if (
            isinstance(session_id, bool)
            or not isinstance(session_id, int)
            or not isinstance(violations_only, bool)
        ):
            return _invalid_input()
        return self._service.list_events(
            session_id, violations_only=violations_only
        )

    def get_company_session(self, session_id: int) -> WorkflowResult:
        if isinstance(session_id, bool) or not isinstance(session_id, int):
            return _invalid_input()
        return self._service.get_company_session(session_id)

    def list_company_events(
        self,
        session_id: int,
        *,
        violations_only: bool = False,
        processing_status: str | None = None,
    ) -> WorkflowResult:
        if (
            isinstance(session_id, bool)
            or not isinstance(session_id, int)
            or not isinstance(violations_only, bool)
            or (
                processing_status is not None
                and not isinstance(processing_status, str)
            )
        ):
            return _invalid_input()
        return self._service.list_company_events(
            session_id,
            violations_only=violations_only,
            processing_status=processing_status,
        )

    def review_event(
        self,
        session_id: int,
        event_id: int,
        processing_status: str,
        *,
        notes: str | None = None,
    ) -> WorkflowResult:
        if (
            isinstance(session_id, bool)
            or not isinstance(session_id, int)
            or isinstance(event_id, bool)
            or not isinstance(event_id, int)
            or not isinstance(processing_status, str)
            or (notes is not None and not isinstance(notes, str))
        ):
            return _invalid_input()
        return self._service.review_event(
            session_id, event_id, processing_status, notes=notes
        )
