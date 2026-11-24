"""SQLite-backed recruitment, exam, submission, and result-release regressions."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.services.auth_service import SessionManager
from app.utils.helpers import hash_password
from client.views.recruitment_contracts import QuestionDraft
from server.controllers.exam_controller import ExamController
from server.controllers.recruitment_controller import RecruitmentController
from server.models.recruitment_repository import RecruitmentRepository
from server.services.exam_service import ExamResult, ExamService
from server.services.recruitment_service import RecruitmentService
from app.integration.recruitment_adapters import (
    CandidateAssessmentAdapter,
    CompanyRecruitmentAdapter,
)


def _create_user(fresh_db, username: str, role: str) -> tuple[str, str]:
    email = f"{username}@recruitment.example.test"
    password = "RecruitmentPass1"
    fresh_db.execute(
        """
        INSERT INTO users
            (username, email, password, full_name, role, is_active, is_deleted)
        VALUES (?, ?, ?, ?, ?, 1, 0)
        """,
        (username, email, hash_password(password), username.title(), role),
    )
    return email, password


def _controllers():
    repository = RecruitmentRepository()
    recruitment = RecruitmentController(RecruitmentService(repository))
    exams = ExamController(ExamService(repository, repository))
    return (
        CompanyRecruitmentAdapter(recruitment, exams),
        CandidateAssessmentAdapter(exams),
        exams,
    )


def test_recruitment_exam_flow_uses_sqlite_and_releases_candidate_result(
    fresh_db, auth
):
    company_email, company_password = _create_user(
        fresh_db, "recruitment-company", "company"
    )
    candidate_email, candidate_password = _create_user(
        fresh_db, "recruitment-candidate", "candidate"
    )
    other_email, other_password = _create_user(
        fresh_db, "other-candidate", "candidate"
    )
    _create_user(fresh_db, "recruitment-expert", "expert")
    company_id = fresh_db.fetchone(
        "SELECT id FROM users WHERE email = ?", (company_email,)
    )["id"]
    expert_id = fresh_db.fetchone(
        "SELECT id FROM users WHERE email = ?",
        ("recruitment-expert@recruitment.example.test",),
    )["id"]
    fresh_db.execute(
        """
        INSERT INTO company_expert_contracts
            (company_id, expert_id, contract_code, status)
        VALUES (?, ?, 'RECRUITMENT-EXPERT-001', 'active')
        """,
        (company_id, expert_id),
    )
    company, candidate, exam_controller = _controllers()

    assert auth.login(company_email, company_password).success
    position = company.create_position(
        "Python Engineer",
        "Build desktop tools",
        "Python and SQLite",
        "Remote",
        "published",
    )
    assert position.success
    position_id = company.list_positions().items[0].id

    authors = company.list_contracted_experts()
    assert authors.success
    assert [author.id for author in authors.items] == [expert_id]
    assessment = company.create_assessment(
        "Python Basics",
        "Multiple-choice assessment",
        30,
        (
            QuestionDraft(
                "Which type is immutable?",
                ("list", "tuple"),
                1,
            ),
        ),
        expert_id=authors.items[0].id,
    )
    assert assessment.success
    assert fresh_db.fetchone(
        "SELECT expert_id FROM question_bank"
    )["expert_id"] == expert_id
    exam_id = company.list_assessments().items[0].id

    candidates = company.list_candidates("recruitment-candidate")
    assert candidates.success
    assert [item.email for item in candidates.items] == [candidate_email]
    invitation = company.send_invitation(
        position_id, exam_id, candidates.items[0].id
    )
    assert invitation.success
    auth.logout()

    assert auth.login(candidate_email, candidate_password).success
    invitations = candidate.list_invitations()
    assert invitations.success
    invitation_id = invitations.items[0].id
    assert invitations.items[0].status == "scheduled"

    loaded = candidate.get_exam(invitation_id)
    assert loaded.success and loaded.exam is not None
    assert len(loaded.exam.questions) == 1
    question = loaded.exam.questions[0]
    assert question.selected_option_id is None
    assert all(
        not hasattr(option, "is_correct")
        for option in question.options
    )
    assert candidate.save_answer(
        invitation_id, question.id, question.options[1].id
    ).success
    resumed = candidate.get_exam(invitation_id)
    assert resumed.success and resumed.exam is not None
    assert resumed.exam.questions[0].selected_option_id == question.options[1].id

    submitted = candidate.submit_exam(invitation_id)
    assert submitted.success and submitted.result is not None
    assert submitted.result.score is None
    assert submitted.result.max_score is None
    assert submitted.result.status == "submitted"
    assert candidate.get_result(invitation_id).success is False
    assert candidate.submit_exam(invitation_id).success is False
    assert (
        fresh_db.fetchone(
            "SELECT COUNT(*) AS count FROM recruitment_submissions"
        )["count"]
        == 1
    )

    auth.logout()
    assert auth.login(other_email, other_password).success
    session_id = fresh_db.fetchone(
        "SELECT id FROM exam_sessions WHERE candidate_id = "
        "(SELECT id FROM users WHERE email = ?)",
        (candidate_email,),
    )["id"]
    assert exam_controller.list_questions(session_id).status == (
        ExamResult.INVITATION_NOT_FOUND
    )
    auth.logout()

    assert auth.login(company_email, company_password).success
    results = company.list_results()
    assert results.success and len(results.items) == 1
    result = results.items[0]
    assert (result.score, result.max_score, result.status) == (
        10.0,
        10.0,
        "graded",
    )
    assert company.release_results(exam_id).success
    auth.logout()

    assert auth.login(candidate_email, candidate_password).success
    released = candidate.get_result(invitation_id)
    assert released.success and released.result is not None
    assert (released.result.score, released.result.max_score) == (10.0, 10.0)
    assert released.result.status == "released"
