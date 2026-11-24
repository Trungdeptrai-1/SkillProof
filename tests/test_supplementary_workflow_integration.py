"""SQLite-backed integration checks for the supplementary demo workflows."""

from datetime import datetime, timedelta

import pytest

from app.integration.supplementary_adapters import (
    create_supplementary_view_controllers,
)
from app.services.auth_service import SessionManager
from app.utils.helpers import hash_password
from server.models.recruitment_repository import RecruitmentRepository


def _account(fresh_db, name: str, role: str) -> tuple[int, str, str]:
    email = f"{name}@supplementary.example.test"
    password = "SupplementaryPass1"
    cursor = fresh_db.execute(
        """
        INSERT INTO users
            (username, email, password, full_name, role, is_active, is_deleted)
        VALUES (?, ?, ?, ?, ?, 1, 0)
        """,
        (name, email, hash_password(password), name.replace("-", " ").title(), role),
    )
    return int(cursor.lastrowid), email, password


def test_candidate_grading_monitoring_and_certificate_flow(fresh_db, auth):
    company_id, company_email, company_password = _account(
        fresh_db, "workflow-company", "company"
    )
    candidate_id, candidate_email, candidate_password = _account(
        fresh_db, "workflow-candidate", "candidate"
    )
    other_id, other_email, other_password = _account(
        fresh_db, "workflow-other-candidate", "candidate"
    )
    admin_id, admin_email, admin_password = _account(
        fresh_db, "workflow-admin", "admin"
    )
    expert_id, _, _ = _account(fresh_db, "workflow-expert", "expert")
    skill_id = fresh_db.execute(
        "INSERT INTO skills(name) VALUES ('Supplementary workflow skill')"
    ).lastrowid
    fresh_db.execute(
        """
        INSERT INTO company_expert_contracts
            (company_id, expert_id, contract_code, status)
        VALUES (?, ?, 'SUPPLEMENTARY-WORKFLOW-EXPERT', 'active')
        """,
        (company_id, expert_id),
    )
    repository = RecruitmentRepository(fresh_db.get_connection())
    position = repository.create_job_posting(
        company_id,
        title="Python engineer",
        description="",
        requirements="",
        location="Remote",
        status="published",
    )
    exam = repository.create_exam(
        company_id,
        title="Written and coding assessment",
        description="",
        duration_min=60,
        total_points=25,
        skill_id=skill_id,
    )
    assert position is not None and exam is not None
    essay = repository.add_question(
        company_id,
        exam["id"],
        expert_id=expert_id,
        title="Explain transactions",
        content="Explain why transactions are useful.",
        difficulty="medium",
        points=10,
        question_type="essay",
    )
    coding = repository.add_question(
        company_id,
        exam["id"],
        expert_id=expert_id,
        title="Add two values",
        content="Write a program that prints the sum of two integers.",
        difficulty="easy",
        points=10,
        question_type="coding",
        test_cases=({"input": "1 2", "expected_output": "3", "is_hidden": True},),
        supported_languages=("python",),
    )
    mcq = repository.add_question(
        company_id,
        exam["id"],
        expert_id=expert_id,
        title="Immutable sequence",
        content="Which is immutable?",
        difficulty="easy",
        points=5,
        question_type="multiple_choice",
        options=(
            _Option("list", False),
            _Option("tuple", True),
        ),
    )
    assert essay and coding and mcq
    assert repository.publish_exam(company_id, exam["id"])
    invitation = repository.invite_candidate(
        company_id, position["id"], exam["id"], candidate_id, None
    )
    assert invitation is not None
    other_invitation = repository.invite_candidate(
        company_id, position["id"], exam["id"], other_id, None
    )
    assert other_invitation is not None
    accepted = repository.accept_candidate_invitation(
        invitation["id"], candidate_id
    )
    assert accepted is not None
    session_id = accepted["exam_session_id"]
    started, _ = repository.start_session_once(session_id, candidate_id)
    assert started

    candidate_view, grader_view, monitor_view, _, certificate_view = (
        create_supplementary_view_controllers(repository)
    )
    assert auth.login(candidate_email, candidate_password).success
    active = monitor_view.get_active_session()
    assert active is not None and active.id == session_id
    assert monitor_view.start_monitoring(session_id).success
    assert monitor_view.record_focus_lost(session_id).success
    events = repository.list_exam_session_events(session_id, candidate_id)
    assert len(events) == 1
    assert events[0].event_type == "focus_lost"
    assert not events[0].is_violation

    assignments = candidate_view.list_assignments()
    assert assignments.success
    assert {item.kind for item in assignments.items} == {"essay", "coding"}
    assert all(
        not hasattr(item, "reference_answer")
        and not hasattr(item, "test_cases")
        for item in assignments.items
    )
    essay_item = next(item for item in assignments.items if item.kind == "essay")
    coding_item = next(item for item in assignments.items if item.kind == "coding")
    assert candidate_view.save_answer(
        essay_item.id, "Transactions group related database changes.", ""
    ).success
    assert candidate_view.save_answer(
        coding_item.id, "a, b = map(int, input().split())\nprint(a + b)", "python"
    ).success
    submitted = candidate_view.submit_answer(
        essay_item.id, "Transactions group related database changes.", ""
    )
    assert submitted.success
    assert not candidate_view.submit_answer(
        essay_item.id, "duplicate submit", ""
    ).success
    assert not candidate_view.get_result(essay_item.id).success
    assert repository.get_candidate_submission(session_id, candidate_id)["status"] == "grading"
    auth.logout()

    assert auth.login(other_email, other_password).success
    from server.controllers.supplementary_workflow_controller import (
        ManualAssessmentController,
    )
    from server.services.manual_assessment_service import ManualAssessmentService
    from app.integration.supplementary_adapters import (
        _ManualAssessmentRepositoryAdapter,
    )

    unauthorized = ManualAssessmentController(
        ManualAssessmentService(_ManualAssessmentRepositoryAdapter(repository))
    )
    assert not unauthorized.list_questions(session_id).success
    accepted_other = repository.accept_candidate_invitation(
        other_invitation["id"], other_id
    )
    assert accepted_other is not None
    other_session_id = accepted_other["exam_session_id"]
    started_other, _ = repository.start_session_once(other_session_id, other_id)
    assert started_other
    other_assignments = candidate_view.list_assignments()
    assert other_assignments.success and len(other_assignments.items) == 2
    for assignment in other_assignments.items:
        assert candidate_view.save_answer(
            assignment.id,
            "A reviewed answer.",
            "python" if assignment.kind == "coding" else "",
        ).success
    assert candidate_view.submit_answer(
        other_assignments.items[0].id,
        "A reviewed answer.",
        "",
    ).success
    auth.logout()

    assert auth.login(company_email, company_password).success
    submissions = grader_view.list_submissions_for_grading()
    assert submissions.success
    assert len(submissions.items) == 4
    for submission in submissions.items:
        assert grader_view.save_grade(
            submission.id, 7.0, "Reviewed by the assigned Company."
        ).success
    graded = grader_view.list_submissions_for_grading()
    assert graded.success and all(item.status == "graded" for item in graded.items)
    candidate_submission = next(
        item for item in graded.items if item.candidate_name == "Workflow Candidate"
    )
    assert grader_view.release_result(candidate_submission.id).success
    assert repository.get_candidate_submission(session_id, candidate_id)["status"] == "released"
    assert repository.get_candidate_submission(
        other_session_id, other_id
    )["status"] == "graded"
    approved = repository.get_approved_assessment(candidate_id, skill_id)
    assert approved is not None and approved["status"] == "approved"
    assert approved["approved_by"] == company_id
    auth.logout()

    assert auth.login(candidate_email, candidate_password).success
    released_assignments = candidate_view.list_assignments()
    released_item = next(item for item in released_assignments.items if item.kind == "essay")
    result = candidate_view.get_result(released_item.id)
    assert result.success and result.released
    assert result.score == 14.0
    assert result.max_score == 25.0
    auth.logout()

    assert auth.login(other_email, other_password).success
    other_released_items = candidate_view.list_assignments()
    assert other_released_items.success
    assert not candidate_view.get_result(other_released_items.items[0].id).success
    auth.logout()

    assert auth.login(admin_email, admin_password).success
    issued = certificate_view.issue_certificate(candidate_id, skill_id)
    assert issued.success
    certificate = certificate_view.list_certificates()
    assert certificate.success and len(certificate.items) == 1
    assert certificate.items[0].score == pytest.approx(56.0)
    verified = certificate_view.verify_certificate(certificate.items[0].cert_code)
    assert verified.success and verified.certificate is not None
    assert certificate_view.revoke_certificate(certificate.items[0].id).success
    assert not certificate_view.verify_certificate(
        certificate.items[0].cert_code
    ).success


def test_interview_schedule_status_and_private_evaluation(fresh_db, auth):
    company_id, company_email, company_password = _account(
        fresh_db, "interview-company", "company"
    )
    candidate_id, candidate_email, candidate_password = _account(
        fresh_db, "interview-candidate", "candidate"
    )
    expert_id, expert_email, expert_password = _account(
        fresh_db, "interview-expert", "expert"
    )
    fresh_db.execute(
        """
        INSERT INTO company_expert_contracts
            (company_id, expert_id, contract_code, status)
        VALUES (?, ?, 'INTERVIEW-WORKFLOW-EXPERT', 'active')
        """,
        (company_id, expert_id),
    )
    repository = RecruitmentRepository(fresh_db.get_connection())
    _, _, _, interview_view, _ = create_supplementary_view_controllers(repository)

    assert auth.login(company_email, company_password).success
    scheduled_at = (datetime.now() + timedelta(days=1)).isoformat()
    scheduled = interview_view.schedule_interview(
        candidate_id, "Technical interview", scheduled_at, (expert_id,)
    )
    assert scheduled.success
    interview = interview_view.list_interviews().items[0]
    assert interview.candidate_name == "Interview Candidate"
    assert interview_view.update_status(interview.id, "in_progress").success
    auth.logout()

    assert auth.login(expert_email, expert_password).success
    expert_interviews = interview_view.list_interviews()
    assert expert_interviews.success and len(expert_interviews.items) == 1
    assert interview_view.save_evaluation(
        expert_interviews.items[0].id,
        "Strong system design discussion.",
        5,
        4,
        5,
        5,
    ).success
    auth.logout()

    assert auth.login(candidate_email, candidate_password).success
    candidate_interviews = interview_view.list_interviews()
    assert candidate_interviews.success
    assert candidate_interviews.items[0].evaluation_notes == ""
    auth.logout()

    assert auth.login(company_email, company_password).success
    company_interviews = interview_view.list_interviews()
    assert "Strong system design discussion." in company_interviews.items[0].evaluation_notes


class _Option:
    def __init__(self, content: str, is_correct: bool) -> None:
        self.content = content
        self.is_correct = is_correct
