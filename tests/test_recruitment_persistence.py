"""Integration tests for the real SQLite recruitment repository."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from app.services.auth_service import SessionManager
from server.models.recruitment_repository import RecruitmentRepository
from server.models.user_model import UserModel
from server.services.exam_service import ExamOption, ExamResult, ExamService
from server.services.recruitment_service import RecruitmentResult, RecruitmentService


@pytest.fixture(autouse=True)
def reset_session():
    SessionManager._instance = None
    yield
    SessionManager._instance = None


@pytest.fixture
def recruitment_data(fresh_db):
    connection = fresh_db.get_connection()
    user_ids = {}
    for role in ("company", "candidate", "expert"):
        cursor = connection.execute(
            """
            INSERT INTO users (username, email, password, full_name, role)
            VALUES (?, ?, 'test-hash', ?, ?)
            """,
            (
                f"persistence-{role}",
                f"persistence-{role}@example.test",
                role.title(),
                role,
            ),
        )
        user_ids[role] = cursor.lastrowid
    connection.execute(
        """
        INSERT INTO company_expert_contracts
            (company_id, expert_id, contract_code, status)
        VALUES (?, ?, 'PERSISTENCE-EXPERT-001', 'active')
        """,
        (user_ids["company"], user_ids["expert"]),
    )
    connection.commit()
    return {
        "connection": connection,
        "repository": RecruitmentRepository(connection),
        "user_ids": user_ids,
    }


def _login(role: str, user_id: int) -> None:
    SessionManager.instance().start_session(
        UserModel(
            id=user_id,
            username=f"{role}-{user_id}",
            email=f"{role}-{user_id}@example.test",
            full_name=role.title(),
            role=role,
            avatar_path=None,
            is_active=True,
            created_at="2026-01-01",
            updated_at="2026-01-01",
        )
    )


def _create_exam_with_question(data):
    repository = data["repository"]
    user_ids = data["user_ids"]
    position = repository.create_job_posting(
        user_ids["company"],
        title="Backend engineer",
        description="Build services",
        requirements="Python",
        location="Remote",
        status="published",
    )
    exam = repository.create_exam(
        user_ids["company"],
        title="Python screening",
        description="Recruitment test",
        duration_min=60,
        total_points=10,
    )
    assert position is not None and exam is not None
    question = repository.add_question(
        user_ids["company"],
        exam["id"],
        expert_id=user_ids["expert"],
        title="Python tuple",
        content="Which value is immutable?",
        difficulty="easy",
        points=10,
        options=(
            ExamOption("List", False),
            ExamOption("Tuple", True),
        ),
    )
    assert question is not None
    repository.publish_exam(user_ids["company"], exam["id"])
    invitation = repository.invite_candidate(
        user_ids["company"],
        position["id"],
        exam["id"],
        user_ids["candidate"],
        None,
    )
    assert invitation is not None
    accepted = repository.accept_candidate_invitation(
        invitation["id"], user_ids["candidate"]
    )
    assert accepted is not None and accepted["status"] == "accepted"
    session_id = accepted["exam_session_id"]
    started, session = repository.start_session_once(
        session_id, user_ids["candidate"]
    )
    assert started and session is not None
    return position, exam, question, invitation, session


def test_real_services_persist_full_recruitment_exam_and_result_flow(recruitment_data):
    repository = recruitment_data["repository"]
    user_ids = recruitment_data["user_ids"]
    recruitment_service = RecruitmentService(repository)
    exam_service = ExamService(repository, repository)

    _login("company", user_ids["company"])
    created_position = recruitment_service.create_position(
        "Backend engineer", "Build services", "Python", "Remote"
    )
    assert created_position.status == RecruitmentResult.SUCCESS
    position_id = created_position.position["id"]
    published_position = recruitment_service.update_position(
        position_id,
        "Backend engineer",
        "Build services",
        "Python",
        "Remote",
        "published",
    )
    assert published_position.success

    created_exam = exam_service.create_exam(
        "Python screening", "Recruitment test", 60, 10
    )
    assert created_exam.status == ExamResult.SUCCESS
    exam_id = created_exam.exam["id"]

    missing_owner = exam_service.add_question(
        exam_id,
        "Python tuple",
        "Which value is immutable?",
        (ExamOption("List", False), ExamOption("Tuple", True)),
        10,
        "easy",
    )
    assert missing_owner.status == ExamResult.DB_ERROR
    assert recruitment_data["connection"].execute(
        "SELECT COUNT(*) FROM question_bank"
    ).fetchone()[0] == 0

    question = repository.add_question(
        user_ids["company"],
        exam_id,
        expert_id=user_ids["expert"],
        title="Python tuple",
        content="Which value is immutable?",
        difficulty="easy",
        points=10,
        options=(ExamOption("List", False), ExamOption("Tuple", True)),
    )
    assert question is not None
    stored_owner = recruitment_data["connection"].execute(
        "SELECT expert_id FROM question_bank WHERE id = ?", (question["id"],)
    ).fetchone()["expert_id"]
    assert stored_owner == user_ids["expert"]

    assert exam_service.publish_exam(exam_id).success
    invited = exam_service.invite_candidate(
        position_id, exam_id, user_ids["candidate"]
    )
    assert invited.success
    assert exam_service.invite_candidate(
        position_id, exam_id, user_ids["candidate"]
    ).success
    assert recruitment_data["connection"].execute(
        "SELECT COUNT(*) FROM recruitment_invitations"
    ).fetchone()[0] == 1

    _login("candidate", user_ids["candidate"])
    invitations = exam_service.list_invitations()
    assert invitations.success and len(invitations.invitations) == 1
    invitation_id = invitations.invitations[0]["id"]
    accepted = exam_service.accept_invitation(invitation_id)
    assert accepted.success
    session_id = accepted.invitation["exam_session_id"]
    assert exam_service.start_exam(session_id).success

    questions = exam_service.list_questions(session_id)
    assert questions.success and len(questions.questions) == 1
    public_question = questions.questions[0]
    assert public_question["id"] == question["id"]
    assert "expert_id" not in public_question
    assert "reference_answer" not in public_question
    assert all("is_correct" not in option for option in public_question["options"])
    correct_option_id = next(
        option["id"] for option in question["options"] if option["is_correct"]
    )
    assert exam_service.save_answer(
        session_id, question["id"], correct_option_id
    ).success

    submitted = exam_service.submit_exam(session_id)
    assert submitted.success and submitted.score == 10
    assert exam_service.submit_exam(session_id).status == ExamResult.ALREADY_SUBMITTED
    assert exam_service.get_result(session_id).status == ExamResult.RESULT_NOT_RELEASED

    _login("company", user_ids["company"])
    submissions = exam_service.list_submissions(exam_id)
    assert submissions.success and len(submissions.submissions) == 1
    assert submissions.submissions[0]["candidate_id"] == user_ids["candidate"]
    assert submissions.submissions[0]["score"] == 10
    assert submissions.submissions[0]["status"] == "graded"
    assert exam_service.release_results(exam_id).success

    _login("candidate", user_ids["candidate"])
    result = exam_service.get_result(session_id)
    assert result.success
    assert result.result["score"] == 10
    assert result.result["max_score"] == 10


def test_company_scoping_and_expert_question_ownership(recruitment_data):
    repository = recruitment_data["repository"]
    user_ids = recruitment_data["user_ids"]
    other_company = recruitment_data["connection"].execute(
        """
        INSERT INTO users (username, email, password, full_name, role)
        VALUES ('other-company-persist', 'other-company-persist@example.test',
                'test-hash', 'Other Company', 'company')
        """
    ).lastrowid
    position, exam, question, invitation, session = _create_exam_with_question(
        recruitment_data
    )

    assert repository.get_job_posting(other_company, position["id"]) is None
    assert repository.update_job_posting(
        other_company,
        position["id"],
        title="Hijacked",
        description="",
        requirements="",
        location="",
        status="closed",
    ) is None
    assert repository.get_exam_for_company(other_company, exam["id"]) is None
    assert repository.get_candidate_session(
        session["id"], other_company
    ) is None
    assert repository.get_candidate_invitation(
        invitation["id"], other_company
    ) is None
    assert recruitment_data["connection"].execute(
        "SELECT expert_id FROM question_bank WHERE id = ?", (question["id"],)
    ).fetchone()["expert_id"] == user_ids["expert"]


def test_concurrent_completion_persists_one_submission_atomically(recruitment_data):
    repository = recruitment_data["repository"]
    user_ids = recruitment_data["user_ids"]
    _, exam, question, _, session = _create_exam_with_question(recruitment_data)
    candidate_id = user_ids["candidate"]
    session_id = session["id"]
    correct_option_id = next(
        option["id"] for option in question["options"] if option["is_correct"]
    )
    saved_answer = repository.save_candidate_answer(
        session_id, candidate_id, question["id"], correct_option_id
    )
    assert saved_answer is not None

    question_scores = [
        {"question_id": question["id"], "score": 10, "max_score": 10}
    ]
    with pytest.raises(sqlite3.IntegrityError, match="persisted candidate answers"):
        repository.complete_session_once(
            session_id,
            candidate_id,
            score=0,
            max_score=10,
            question_scores=[
                {"question_id": question["id"], "score": 0, "max_score": 10}
            ],
        )
    assert recruitment_data["connection"].execute(
        "SELECT status FROM exam_sessions WHERE id = ?", (session_id,)
    ).fetchone()["status"] == "in_progress"
    assert recruitment_data["connection"].execute(
        "SELECT COUNT(*) FROM recruitment_submissions"
    ).fetchone()[0] == 0

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                repository.complete_session_once,
                session_id,
                candidate_id,
                score=10,
                max_score=10,
                question_scores=question_scores,
            )
            for _ in range(2)
        ]
    completions = [future.result() for future in futures]

    assert sum(completed for completed, _ in completions) == 1
    connection = recruitment_data["connection"]
    assert connection.execute(
        "SELECT status FROM exam_sessions WHERE id = ?", (session_id,)
    ).fetchone()["status"] == "completed"
    assert connection.execute(
        """
        SELECT COUNT(*) FROM recruitment_submissions
        WHERE exam_session_id = ?
        """,
        (session_id,),
    ).fetchone()[0] == 1
    answer_row = connection.execute(
        """
        SELECT score, max_score, is_graded FROM exam_answers
        WHERE exam_session_id = ? AND question_id = ?
        """,
        (session_id, question["id"]),
    ).fetchone()
    assert (answer_row["score"], answer_row["max_score"], answer_row["is_graded"]) == (
        10,
        10,
        1,
    )
    assert exam["id"] == connection.execute(
        "SELECT exam_paper_id FROM exam_sessions WHERE id = ?", (session_id,)
    ).fetchone()["exam_paper_id"]
