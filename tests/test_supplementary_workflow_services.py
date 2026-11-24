from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from app.services.auth_service import SessionManager
from server.controllers.supplementary_workflow_controller import (
    CertificateController,
    ExamMonitoringController,
    InterviewController,
    ManualAssessmentController,
)
from server.models.user_model import UserModel
from server.services.certificate_service import CertificateModel, CertificateService
from server.services.exam_monitoring_service import (
    ExamMonitoringModel,
    ExamMonitoringService,
)
from server.services.interview_service import InterviewModel, InterviewService
from server.services.manual_assessment_service import (
    ManualAssessmentModel,
    ManualAssessmentService,
)


@pytest.fixture(autouse=True)
def reset_session():
    SessionManager._instance = None
    yield
    SessionManager._instance = None


def _session(role: str, user_id: int = 41) -> None:
    SessionManager.instance().start_session(
        UserModel(
            id=user_id,
            username=f"{role}-{user_id}",
            email=f"{role}-{user_id}@test.local",
            full_name="Test Account",
            role=role,
            avatar_path=None,
            is_active=True,
            created_at="2026-01-01",
            updated_at="2026-01-01",
        )
    )


def _manual_controller():
    model = Mock(spec=ManualAssessmentModel)
    return model, ManualAssessmentController(ManualAssessmentService(model))


def _interview_controller():
    model = Mock(spec=InterviewModel)
    return model, InterviewController(InterviewService(model))


def _certificate_controller():
    model = Mock(spec=CertificateModel)
    return model, CertificateController(CertificateService(model))


def _monitoring_controller():
    model = Mock(spec=ExamMonitoringModel)
    return model, ExamMonitoringController(ExamMonitoringService(model))


def _active_exam_session():
    return {
        "status": "in_progress",
        "started_at": "2999-01-01T00:00:00",
        "duration_min": 60,
    }


def _active_proctoring_session(consent_for_evidence: bool = False):
    return {
        "id": 13,
        "exam_session_id": 3,
        "candidate_id": 9,
        "status": "active",
        "consent_for_evidence": consent_for_evidence,
    }


def test_candidate_receives_manual_prompts_without_answer_material():
    _session("candidate", 9)
    model, controller = _manual_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.list_candidate_questions.return_value = [
        {
            "id": 5,
            "question_type": "coding",
            "content": "Write a parser",
            "test_cases": "hidden inputs",
            "reference_answer": "hidden solution",
            "points": 10,
        }
    ]

    result = controller.list_questions(3)

    assert result.success
    assert result.records == (
        {
            "id": 5,
            "question_type": "coding",
            "content": "Write a parser",
            "points": 10,
        },
    )


@pytest.mark.parametrize(
    ("question_type", "payload_name"),
    [("essay", "answer_text"), ("coding", "answer_code")],
)
def test_candidate_saves_essay_or_code_without_execution(question_type, payload_name):
    _session("candidate", 9)
    model, controller = _manual_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.list_candidate_questions.return_value = [
        {"id": 5, "question_type": question_type}
    ]
    model.save_candidate_response.return_value = {"id": 6}
    payload = "print('not executed')"

    result = controller.save_response(
        3, 5, **{payload_name: payload}
    )

    assert result.success
    assert model.save_candidate_response.call_args.kwargs[payload_name] == payload


def test_manual_answer_validation_and_ownership_are_enforced():
    _session("candidate", 9)
    model, controller = _manual_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.list_candidate_questions.return_value = [{"id": 5, "question_type": "essay"}]

    invalid = controller.save_response(3, 5, answer_text=" ", answer_code="source")
    missing = controller.save_response(3, 999, answer_text="answer")

    assert invalid.status == ManualAssessmentService.INVALID_INPUT
    assert missing.status == ManualAssessmentService.NOT_FOUND
    model.save_candidate_response.assert_not_called()


def test_candidate_submission_requires_manual_questions_and_active_session():
    _session("candidate", 9)
    model, controller = _manual_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.list_candidate_questions.return_value = [
        {"id": 5, "question_type": "multiple_choice"}
    ]

    result = controller.submit(3)

    assert result.status == ManualAssessmentService.UNSUPPORTED_QUESTION
    model.submit_manual_session_once.assert_not_called()


def test_candidate_cannot_read_result_until_company_releases_it():
    _session("candidate", 9)
    model, controller = _manual_controller()
    model.get_candidate_submission.return_value = {"status": "graded"}

    result = controller.get_result(3)

    assert result.status == ManualAssessmentService.RESULT_NOT_RELEASED
    model.get_candidate_result.assert_not_called()


def test_manual_grading_checks_scope_score_and_revision_reason():
    _session("expert", 12)
    model, controller = _manual_controller()
    model.can_grade_session.return_value = True
    model.get_manual_answer_for_grading.return_value = {
        "question_type": "essay",
        "max_score": 10,
        "is_graded": False,
    }
    model.grade_manual_answer_once.return_value = {"score": 8}

    too_high = controller.grade_answer(3, 5, 11, "Good")
    valid = controller.grade_answer(3, 5, 8, "Clear explanation")

    assert too_high.status == ManualAssessmentService.INVALID_INPUT
    assert valid.success
    model.grade_manual_answer_once.assert_called_once()

    model.get_manual_answer_for_grading.return_value["is_graded"] = True
    revision_without_reason = controller.grade_answer(3, 5, 9, "Improved")
    revision_with_reason = controller.grade_answer(
        3, 5, 9, "Improved", reason="Second review"
    )
    assert revision_without_reason.status == ManualAssessmentService.INVALID_INPUT
    assert revision_with_reason.success


def test_manual_grading_requires_all_answers_before_finalization():
    _session("company", 12)
    model, controller = _manual_controller()
    model.can_grade_session.return_value = True
    model.get_manual_grading_progress.return_value = {
        "question_count": 2,
        "graded_count": 1,
    }

    result = controller.finalize_grading(3)

    assert result.status == ManualAssessmentService.GRADING_INCOMPLETE
    model.finalize_manual_grading_once.assert_not_called()


def test_manual_service_reports_sqlite_errors():
    import sqlite3

    _session("candidate", 9)
    model, controller = _manual_controller()
    model.get_candidate_session.side_effect = sqlite3.OperationalError("locked")

    result = controller.list_questions(3)

    assert result.status == ManualAssessmentService.DB_ERROR


def test_company_can_schedule_interview_and_only_valid_transitions_apply():
    _session("company", 12)
    model, controller = _interview_controller()
    model.create_interview.return_value = {"id": 4, "status": "scheduled"}
    model.get_interview_for_user.return_value = {"status": "scheduled"}
    model.update_interview_status.return_value = {"status": "in_progress"}
    future = (datetime.now() + timedelta(days=1)).isoformat()

    scheduled = controller.schedule(9, "Technical", future, expert_ids=[31])
    invalid_transition = controller.update_status(4, "invalid")
    started = controller.update_status(4, "in_progress")

    assert scheduled.success
    assert invalid_transition.status == InterviewService.INVALID_TRANSITION
    assert started.success
    assert model.update_interview_status.call_count == 1


def test_interview_schedule_and_evaluation_validate_data_and_permissions():
    _session("company", 12)
    model, controller = _interview_controller()
    past = (datetime.now() - timedelta(days=1)).isoformat()
    invalid_schedule = controller.schedule(9, "Technical", past)
    assert invalid_schedule.status == InterviewService.INVALID_INPUT

    _session("expert", 31)
    model.can_evaluate_interview.return_value = False
    denied = controller.evaluate(
        4,
        technical_score=5,
        communication_score=4,
        problem_solving_score=4,
        overall_rating=4,
    )
    assert denied.status == InterviewService.FORBIDDEN
    model.save_interview_evaluation.assert_not_called()


def test_interview_evaluator_can_save_scored_feedback():
    _session("expert", 31)
    model, controller = _interview_controller()
    model.can_evaluate_interview.return_value = True
    model.save_interview_evaluation.return_value = {"overall_rating": 4}

    result = controller.evaluate(
        4,
        technical_score=5,
        communication_score=4,
        problem_solving_score=4,
        overall_rating=4,
        feedback="Strong debugging",
        recommendation="hire",
    )

    assert result.success
    assert model.save_interview_evaluation.call_args.kwargs["feedback"] == "Strong debugging"


def test_interview_links_are_https_and_returned_only_to_interview_participants():
    _session("candidate", 9)
    model, controller = _interview_controller()
    model.get_interview_for_user.return_value = {
        "id": 4,
        "meeting_url": "https://meet.example.test/room",
    }

    link = controller.get_meeting_link(4)
    participants = controller.list_participants(4)

    assert link.success and link.value == "https://meet.example.test/room"
    assert participants.status == InterviewService.WRONG_ROLE
    model.list_interview_participants.assert_not_called()

    _session("company", 12)
    model.get_interview_for_user.return_value = {"id": 4, "company_id": 12}
    model.list_interview_participants.return_value = [{"expert_id": 31}]
    participants = controller.list_participants(4)
    assert participants.success and participants.records == ({"expert_id": 31},)

    unsafe_link = controller.schedule(
        9,
        "Technical",
        (datetime.now() + timedelta(days=1)).isoformat(),
        meeting_url="javascript:alert(1)",
    )
    assert unsafe_link.status == InterviewService.INVALID_INPUT
    model.create_interview.assert_not_called()


def test_certificate_requires_approved_candidate_result_and_blocks_duplicates():
    _session("admin", 1)
    model, controller = _certificate_controller()
    model.get_account_role.return_value = "candidate"
    model.is_active_candidate.return_value = True
    model.get_approved_assessment.return_value = {"status": "approved", "score": 92}
    model.get_certificate_for_candidate.return_value = None
    model.issue_certificate.return_value = {"id": 5, "status": "active"}

    issued = controller.issue(9, 3)
    assert issued.success
    assert model.issue_certificate.call_args.kwargs["score"] == 92
    assert len(model.issue_certificate.call_args.kwargs["cert_code"]) >= 30

    model.get_certificate_for_candidate.return_value = {"id": 5}
    duplicate = controller.issue(9, 3)
    assert duplicate.status == CertificateService.CERTIFICATE_EXISTS
    assert model.issue_certificate.call_count == 1


def test_certificate_issue_requires_approved_result_and_admin():
    _session("admin", 1)
    model, controller = _certificate_controller()
    model.get_account_role.return_value = "candidate"
    model.is_active_candidate.return_value = True
    model.get_approved_assessment.return_value = {"status": "pending", "score": 92}
    assert controller.issue(9, 3).status == CertificateService.RESULT_NOT_APPROVED

    _session("candidate", 9)
    assert controller.issue(9, 3).status == CertificateService.WRONG_ROLE


def test_certificate_verification_is_scoped_and_revoke_requires_admin():
    _session("candidate", 9)
    model, controller = _certificate_controller()
    model.get_certificate_by_code.return_value = {
        "id": 5,
        "candidate_id": 8,
        "status": "active",
    }
    model.can_view_certificate.return_value = False

    denied = controller.verify("certificate-code")
    assert denied.status == CertificateService.FORBIDDEN

    _session("admin", 1)
    model.get_certificate_by_id.return_value = {"id": 5, "status": "active"}
    model.revoke_certificate.return_value = {"id": 5, "status": "revoked"}
    revoked = controller.revoke(5)
    assert revoked.success


def test_monitoring_starts_only_for_active_candidate_session_with_recorded_consent():
    _session("candidate", 9)
    model, controller = _monitoring_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.start_exam_proctoring_session.return_value = _active_proctoring_session(True)

    started = controller.start_session(3, consent_for_evidence=True)
    assert started.success
    assert model.start_exam_proctoring_session.call_args.kwargs[
        "consent_for_evidence"
    ] is True

    model.get_candidate_session.return_value = {"status": "completed"}
    rejected = controller.start_session(3)
    assert rejected.status == ExamMonitoringService.EXAM_NOT_ACTIVE
    assert model.start_exam_proctoring_session.call_count == 1


def test_controller_resolves_candidate_active_invitation_for_ui():
    _session("candidate", 9)
    model, controller = _monitoring_controller()
    model.list_candidate_invitations.return_value = [
        {
            "status": "accepted",
            "session_status": "in_progress",
            "exam_session_id": 3,
            "exam_title": "Backend assessment",
        }
    ]
    model.get_candidate_session.return_value = _active_exam_session()

    active = controller.get_active_session()

    assert active.success
    assert active.record["session_id"] == 3
    assert active.record["title"] == "Backend assessment"
    assert active.record["status"] == "in_progress"
    assert active.record["remaining_seconds"] > 0


def test_monitoring_focus_threshold_requests_human_review_not_a_guilt_finding():
    _session("candidate", 9)
    model, controller = _monitoring_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.get_exam_proctoring_session.return_value = _active_proctoring_session()
    model.list_exam_session_events.return_value = [
        {"event_type": "focus_lost"},
        {"event_type": "focus_lost"},
    ]
    model.record_exam_session_event.return_value = {
        "event_type": "focus_lost",
        "is_violation": True,
    }

    result = controller.record_event(3, "focus_lost")

    assert result.success
    assert result.value["outcome"] == "manual_review_required"
    assert result.value["focus_event_count"] == 3
    assert "cheat" not in result.message.lower()
    assert model.record_exam_session_event.call_args.kwargs["is_violation"] is True
    model.finish_exam_proctoring_session.assert_not_called()


def test_monitoring_threshold_is_configurable_without_auto_ending_exam():
    _session("candidate", 9)
    model = Mock(spec=ExamMonitoringModel)
    controller = ExamMonitoringController(
        ExamMonitoringService(model, focus_review_threshold=1)
    )
    model.get_candidate_session.return_value = _active_exam_session()
    model.get_exam_proctoring_session.return_value = _active_proctoring_session()
    model.list_exam_session_events.return_value = []
    model.record_exam_session_event.return_value = {
        "event_type": "focus_lost",
        "is_violation": True,
    }

    result = controller.record_event(3, "focus_lost")

    assert result.success
    assert result.value["outcome"] == "manual_review_required"
    assert model.record_exam_session_event.call_args.kwargs["is_violation"] is True
    model.finish_exam_proctoring_session.assert_not_called()


def test_camera_disconnection_is_technical_and_not_a_violation():
    _session("candidate", 9)
    model, controller = _monitoring_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.get_exam_proctoring_session.return_value = _active_proctoring_session()
    model.record_exam_session_event.return_value = {
        "event_type": "camera_disconnected",
        "is_violation": False,
    }
    camera = controller.record_camera_status(3, "disconnected")

    assert camera.success
    assert camera.value["outcome"] == "technical_warning"
    assert model.record_exam_session_event.call_args.args[2] == "camera_disconnected"
    assert model.record_exam_session_event.call_args.kwargs["is_violation"] is False


def test_timeout_event_requires_server_verified_deadline():
    _session("candidate", 9)
    model, controller = _monitoring_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.get_exam_proctoring_session.return_value = _active_proctoring_session()

    too_early = controller.record_event(3, "timeout")
    assert too_early.status == ExamMonitoringService.TIMEOUT_NOT_VERIFIED
    model.record_exam_session_event.assert_not_called()


def test_timeout_event_is_non_accusatory_and_does_not_change_exam_state():
    _session("candidate", 9)
    model, controller = _monitoring_controller()
    model.get_candidate_session.return_value = {
        "status": "in_progress",
        "started_at": (datetime.now() - timedelta(minutes=5)).isoformat(),
        "duration_min": 1,
    }
    model.get_exam_proctoring_session.return_value = _active_proctoring_session()
    model.record_exam_session_event.return_value = {
        "event_type": "timeout",
        "is_violation": False,
    }

    result = controller.record_event(3, "timeout")

    assert result.success
    assert result.value["outcome"] == "timeout_recorded"
    assert model.record_exam_session_event.call_args.kwargs["is_violation"] is False
    model.finish_exam_proctoring_session.assert_not_called()


def test_evidence_reference_requires_explicit_persisted_consent():
    _session("candidate", 9)
    model, controller = _monitoring_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.get_exam_proctoring_session.return_value = _active_proctoring_session(False)

    result = controller.record_event(
        3, "camera_disconnected", evidence_uri="evidence://session/13/frame"
    )

    assert result.status == ExamMonitoringService.CONSENT_REQUIRED
    model.record_exam_session_event.assert_not_called()


def test_consented_evidence_reference_is_still_opaque_and_never_media_bytes():
    _session("candidate", 9)
    model, controller = _monitoring_controller()
    model.get_candidate_session.return_value = _active_exam_session()
    model.get_exam_proctoring_session.return_value = _active_proctoring_session(True)
    model.record_exam_session_event.return_value = {
        "id": 18,
        "event_type": "camera_active",
        "evidence_uri": "evidence://vault/capture/18",
    }

    result = controller.record_camera_status(
        3,
        "active",
        evidence_uri="evidence://vault/capture/18",
    )

    assert result.success
    assert model.record_exam_session_event.call_args.kwargs["evidence_uri"] == (
        "evidence://vault/capture/18"
    )
    assert not controller.record_camera_status(
        3,
        "active",
        evidence_uri="data:image/jpeg;base64,abc",
    ).success


def test_monitoring_event_details_reject_media_or_answer_payloads():
    _session("candidate", 9)
    model, controller = _monitoring_controller()

    result = controller.record_event(
        3,
        "focus_lost",
        details={"screenshot_data": "x"},
    )

    assert result.status == ExamMonitoringService.INVALID_INPUT
    model.record_exam_session_event.assert_not_called()


def test_finish_monitoring_closes_only_the_monitor_session():
    _session("candidate", 9)
    model, controller = _monitoring_controller()
    model.finish_exam_proctoring_session.return_value = {
        "status": "completed",
        "ended_at": "2026-11-24T11:00:00",
    }

    result = controller.finish_session(3)

    assert result.success
    model.finish_exam_proctoring_session.assert_called_once_with(3, 9)
    model.get_candidate_session.assert_not_called()


def test_company_or_contracted_expert_can_review_events_through_repository_scope():
    _session("expert", 12)
    model, controller = _monitoring_controller()
    model.get_exam_session_context.return_value = {"company_id": 8}
    model.get_company_exam_proctoring_session.return_value = _active_proctoring_session()
    model.list_company_exam_session_events.return_value = [
        {"id": 5, "event_type": "focus_lost", "is_violation": True}
    ]
    model.review_exam_session_event.return_value = {
        "event_type": "focus_lost",
        "processing_status": "reviewed",
    }

    events = controller.list_company_events(3, violations_only=True)
    reviewed = controller.review_event(3, 5, "reviewed", notes="Reviewed context")

    assert events.success and len(events.records) == 1
    assert reviewed.success
    assert model.list_company_exam_session_events.call_args.kwargs[
        "requester_id"
    ] == 12
    assert model.review_exam_session_event.call_args.args[:3] == (8, 12, 5)


def test_controllers_reject_malformed_ids_without_calling_services():
    model, controller = _manual_controller()
    result = controller.submit(True)
    assert result.status == ManualAssessmentService.INVALID_INPUT
    model.submit_manual_session_once.assert_not_called()
