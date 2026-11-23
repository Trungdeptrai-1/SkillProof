"""Recruitment model and data-integrity coverage."""

import sqlite3

import pytest

from server.database.schema import (
    _mig_006_create_recruitment_workflow,
    create_all_tables,
)
from server.models.recruitment_models import (
    CandidateExamResultModel,
    ExamAnswerModel,
    ExamPaperModel,
    ExamQuestionModel,
    ExamSessionModel,
    JobPostingModel,
    QuestionOptionModel,
    RecruitmentInvitationModel,
    RecruitmentSubmissionModel,
)


@pytest.fixture
def recruitment_setup(fresh_db):
    conn = fresh_db.get_connection()
    user_ids = {}
    for username, role in (
        ("recruitment-company", "company"),
        ("recruitment-candidate", "candidate"),
        ("recruitment-expert", "expert"),
    ):
        cursor = conn.execute(
            """
            INSERT INTO users (username, email, password, full_name, role)
            VALUES (?, ?, 'test-hash', ?, ?)
            """,
            (username, f"{username}@example.test", username, role),
        )
        user_ids[role] = cursor.lastrowid

    paper_cursor = conn.execute(
        """
        INSERT INTO exam_papers
            (title, description, created_by, total_points, duration_min, is_published)
        VALUES ('Recruitment test', 'Test paper', ?, 10, 30, 1)
        """,
        (user_ids["expert"],),
    )
    paper_id = paper_cursor.lastrowid

    question_cursor = conn.execute(
        """
        INSERT INTO question_bank
            (expert_id, title, content, question_type, difficulty, points,
             reference_answer, test_cases, is_published)
        VALUES (?, 'Question 1', 'Pick the right option', 'multiple_choice',
                'easy', 10, 'hidden answer', 'hidden cases', 1)
        """,
        (user_ids["expert"],),
    )
    question_id = question_cursor.lastrowid
    conn.execute(
        """
        INSERT INTO exam_paper_questions (exam_paper_id, question_id, points, sort_order)
        VALUES (?, ?, 10, 1)
        """,
        (paper_id, question_id),
    )

    option_ids = []
    for content, is_correct in (("Correct option", 1), ("Wrong option", 0)):
        cursor = conn.execute(
            """
            INSERT INTO question_options (question_id, content, is_correct, sort_order)
            VALUES (?, ?, ?, ?)
            """,
            (question_id, content, is_correct, len(option_ids) + 1),
        )
        option_ids.append(cursor.lastrowid)

    job_cursor = conn.execute(
        """
        INSERT INTO job_postings (company_id, title, description, requirements, location, status)
        VALUES (?, 'Python developer', 'Build software', 'Python', 'Remote', 'published')
        """,
        (user_ids["company"],),
    )
    return {
        "conn": conn,
        "user_ids": user_ids,
        "paper_id": paper_id,
        "question_id": question_id,
        "option_ids": option_ids,
        "job_id": job_cursor.lastrowid,
    }


def _create_accepted_invitation(setup):
    conn = setup["conn"]
    user_ids = setup["user_ids"]
    session_cursor = conn.execute(
        """
        INSERT INTO exam_sessions
            (exam_paper_id, candidate_id, company_id, status, max_score)
        VALUES (?, ?, ?, 'scheduled', 10)
        """,
        (setup["paper_id"], user_ids["candidate"], user_ids["company"]),
    )
    session_id = session_cursor.lastrowid
    invitation_cursor = conn.execute(
        """
        INSERT INTO recruitment_invitations
            (job_posting_id, company_id, candidate_id, exam_paper_id)
        VALUES (?, ?, ?, ?)
        """,
        (
            setup["job_id"],
            user_ids["company"],
            user_ids["candidate"],
            setup["paper_id"],
        ),
    )
    invitation_id = invitation_cursor.lastrowid
    conn.execute(
        """
        UPDATE recruitment_invitations
        SET status = 'accepted', exam_session_id = ?, responded_at = datetime('now')
        WHERE id = ?
        """,
        (session_id, invitation_id),
    )
    return invitation_id, session_id


def _result_row(conn, session_id):
    return conn.execute(
        """
        SELECT es.id AS exam_session_id, es.total_score, es.max_score,
               rs.status AS submission_status, rs.graded_at, rs.released_at
        FROM exam_sessions es
        JOIN recruitment_submissions rs ON rs.exam_session_id = es.id
        WHERE es.id = ?
        """,
        (session_id,),
    ).fetchone()


def test_job_paper_questions_and_options_are_candidate_safe(recruitment_setup):
    conn = recruitment_setup["conn"]
    job_row = conn.execute(
        "SELECT * FROM job_postings WHERE id = ?", (recruitment_setup["job_id"],)
    ).fetchone()
    paper_row = conn.execute(
        "SELECT * FROM exam_papers WHERE id = ?", (recruitment_setup["paper_id"],)
    ).fetchone()
    question_row = conn.execute(
        """
        SELECT epq.exam_paper_id, qb.id AS question_id, qb.skill_id, qb.title,
               qb.content, qb.question_type, qb.difficulty,
               COALESCE(epq.points, qb.points) AS points, epq.sort_order,
               qb.reference_answer, qb.test_cases
        FROM exam_paper_questions epq
        JOIN question_bank qb ON qb.id = epq.question_id
        WHERE epq.exam_paper_id = ?
        """,
        (recruitment_setup["paper_id"],),
    ).fetchone()
    option_row = conn.execute(
        "SELECT * FROM question_options WHERE id = ?",
        (recruitment_setup["option_ids"][0],),
    ).fetchone()

    job = JobPostingModel.from_row(job_row)
    paper = ExamPaperModel.from_row(paper_row)
    question = ExamQuestionModel.from_row(question_row)
    option = QuestionOptionModel.from_row(option_row)

    assert job.company_id == recruitment_setup["user_ids"]["company"]
    assert job.status == "published"
    assert paper.is_published
    assert question.question_id == recruitment_setup["question_id"]
    assert not hasattr(question, "reference_answer")
    assert not hasattr(question, "test_cases")
    assert option.content == "Correct option"
    assert not hasattr(option, "is_correct")


def test_invitation_session_submission_grading_and_result_release(recruitment_setup):
    conn = recruitment_setup["conn"]
    user_ids = recruitment_setup["user_ids"]
    invitation_id, session_id = _create_accepted_invitation(recruitment_setup)

    invitation_row = conn.execute(
        "SELECT * FROM recruitment_invitations WHERE id = ?", (invitation_id,)
    ).fetchone()
    invitation = RecruitmentInvitationModel.from_row(invitation_row)
    assert invitation.status == "accepted"
    assert invitation.exam_session_id == session_id

    conn.execute(
        """
        UPDATE exam_sessions
        SET status = 'in_progress', started_at = datetime('now')
        WHERE id = ?
        """,
        (session_id,),
    )
    answer_cursor = conn.execute(
        """
        INSERT INTO exam_answers (exam_session_id, question_id, selected_option_id)
        VALUES (?, ?, ?)
        """,
        (
            session_id,
            recruitment_setup["question_id"],
            recruitment_setup["option_ids"][0],
        ),
    )
    answer_row = conn.execute(
        "SELECT * FROM exam_answers WHERE id = ?", (answer_cursor.lastrowid,)
    ).fetchone()
    answer = ExamAnswerModel.from_row(answer_row)
    assert answer.selected_option_id == recruitment_setup["option_ids"][0]
    assert not hasattr(answer, "score")
    assert not hasattr(answer, "feedback")

    conn.execute(
        """
        UPDATE exam_sessions
        SET status = 'completed', completed_at = datetime('now')
        WHERE id = ?
        """,
        (session_id,),
    )
    conn.execute(
        """
        INSERT INTO recruitment_submissions
            (invitation_id, exam_session_id, candidate_id, company_id, exam_paper_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            invitation_id,
            session_id,
            user_ids["candidate"],
            user_ids["company"],
            recruitment_setup["paper_id"],
        ),
    )
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(
            """
            INSERT INTO recruitment_submissions
                (invitation_id, exam_session_id, candidate_id, company_id, exam_paper_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                invitation_id,
                session_id,
                user_ids["candidate"],
                user_ids["company"],
                recruitment_setup["paper_id"],
            ),
        )

    with pytest.raises(ValueError, match="only after release"):
        CandidateExamResultModel.from_row(_result_row(conn, session_id))

    conn.execute(
        """
        UPDATE exam_answers
        SET score = 10, max_score = 10, is_graded = 1, graded_by = ?,
            graded_at = datetime('now')
        WHERE exam_session_id = ?
        """,
        (user_ids["expert"], session_id),
    )
    conn.execute(
        "UPDATE exam_sessions SET total_score = 10, max_score = 10 WHERE id = ?",
        (session_id,),
    )
    conn.execute(
        "UPDATE recruitment_submissions SET status = 'grading' WHERE exam_session_id = ?",
        (session_id,),
    )
    conn.execute(
        """
        UPDATE recruitment_submissions
        SET status = 'graded', graded_at = datetime('now')
        WHERE exam_session_id = ?
        """,
        (session_id,),
    )
    with pytest.raises(ValueError, match="only after release"):
        CandidateExamResultModel.from_row(_result_row(conn, session_id))

    conn.execute(
        """
        UPDATE recruitment_submissions
        SET status = 'released', released_at = datetime('now')
        WHERE exam_session_id = ?
        """,
        (session_id,),
    )
    submission_row = conn.execute(
        "SELECT * FROM recruitment_submissions WHERE exam_session_id = ?",
        (session_id,),
    ).fetchone()
    submission = RecruitmentSubmissionModel.from_row(submission_row)
    session_row = conn.execute(
        "SELECT * FROM exam_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    session = ExamSessionModel.from_row(session_row)
    result = CandidateExamResultModel.from_row(_result_row(conn, session_id))

    assert submission.status == "released"
    assert session.status == "completed"
    assert result.score == 10
    assert result.max_score == 10


def test_foreign_keys_and_answer_option_question_relationship(recruitment_setup):
    conn = recruitment_setup["conn"]
    user_ids = recruitment_setup["user_ids"]
    with pytest.raises(sqlite3.IntegrityError, match="must be a company"):
        conn.execute(
            """
            INSERT INTO job_postings (company_id, title)
            VALUES (?, 'Candidate-owned vacancy')
            """,
            (user_ids["candidate"],),
        )

    with pytest.raises(sqlite3.IntegrityError, match="invitation requires"):
        conn.execute(
            """
            INSERT INTO recruitment_invitations
                (job_posting_id, company_id, candidate_id, exam_paper_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                recruitment_setup["job_id"],
                user_ids["company"],
                user_ids["company"],
                recruitment_setup["paper_id"],
            ),
        )

    other_company = conn.execute(
        """
        INSERT INTO users (username, email, password, full_name, role)
        VALUES (
            'other-company', 'other-company@example.test', 'test-hash',
            'Other Company', 'company'
        )
        """
    ).lastrowid

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute(
            """
            INSERT INTO recruitment_invitations
                (job_posting_id, company_id, candidate_id, exam_paper_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                recruitment_setup["job_id"],
                other_company,
                user_ids["candidate"],
                recruitment_setup["paper_id"],
            ),
        )

    invitation_id, session_id = _create_accepted_invitation(recruitment_setup)
    conn.execute(
        "UPDATE exam_sessions SET status = 'in_progress' WHERE id = ?", (session_id,)
    )
    second_question = conn.execute(
        """
        INSERT INTO question_bank
            (expert_id, title, content, question_type, difficulty, points, is_published)
        VALUES (?, 'Question 2', 'Another question', 'multiple_choice', 'easy', 1, 1)
        """,
        (user_ids["expert"],),
    ).lastrowid
    wrong_question_option = conn.execute(
        """
        INSERT INTO question_options (question_id, content, is_correct, sort_order)
        VALUES (?, 'Unrelated option', 0, 1)
        """,
        (second_question,),
    ).lastrowid

    with pytest.raises(sqlite3.IntegrityError, match="does not belong"):
        conn.execute(
            """
            INSERT INTO exam_answers (exam_session_id, question_id, selected_option_id)
            VALUES (?, ?, ?)
            """,
            (
                session_id,
                recruitment_setup["question_id"],
                wrong_question_option,
            ),
        )

    assert conn.execute(
        "SELECT status FROM recruitment_invitations WHERE id = ?", (invitation_id,)
    ).fetchone()["status"] == "accepted"


def test_mig006_upgrades_legacy_database_without_losing_users(legacy_db):
    conn = legacy_db.get_connection()
    original_users = conn.execute(
        "SELECT id, username, email FROM users ORDER BY id"
    ).fetchall()

    create_all_tables(conn)
    first_upgrade_users = conn.execute(
        "SELECT id, username, email FROM users ORDER BY id"
    ).fetchall()
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert [tuple(row) for row in first_upgrade_users] == [
        tuple(row) for row in original_users
    ]
    assert {
        "job_postings",
        "recruitment_invitations",
        "recruitment_submissions",
    } <= tables

    create_all_tables(conn)
    _mig_006_create_recruitment_workflow(conn)
    final_users = conn.execute(
        "SELECT id, username, email FROM users ORDER BY id"
    ).fetchall()
    assert [tuple(row) for row in final_users] == [
        tuple(row) for row in original_users
    ]
