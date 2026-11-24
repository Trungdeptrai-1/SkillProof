"""Focused persistence tests for the final assessment and credential workflows."""

import sqlite3

import pytest

from server.database.schema import (
    _mig_008_complete_feature_persistence,
    _mig_007_complete_assessment_data,
    create_all_tables,
)
from server.models.certificate_model import CertificateModel
from server.models.recruitment_models import (
    CodingTestCaseModel,
    ExamSessionEventModel,
    InterviewEvaluationModel,
    InterviewModel,
)
from server.models.recruitment_repository import RecruitmentRepository


@pytest.fixture
def final_workflow(fresh_db):
    conn = fresh_db.get_connection()
    user_ids = {}
    for role in ("company", "candidate", "expert", "admin"):
        user_ids[role] = conn.execute(
            """
            INSERT INTO users (username, email, password, full_name, role)
            VALUES (?, ?, 'test-hash', ?, ?)
            """,
            (
                f"final-db-{role}",
                f"final-db-{role}@example.test",
                role.title(),
                role,
            ),
        ).lastrowid
    skill_id = conn.execute(
        "INSERT INTO skills (name) VALUES ('Final database skill')"
    ).lastrowid
    conn.execute(
        """
        INSERT INTO company_expert_contracts
            (company_id, expert_id, contract_code, status)
        VALUES (?, ?, 'FINAL-DB-EXPERT', 'active')
        """,
        (user_ids["company"], user_ids["expert"]),
    )
    repository = RecruitmentRepository(conn)
    position = repository.create_job_posting(
        user_ids["company"],
        title="Database engineer",
        description="",
        requirements="",
        location="Remote",
        status="published",
    )
    exam = repository.create_exam(
        user_ids["company"],
        title="Core assessment",
        description="",
        duration_min=60,
        total_points=20,
    )
    assert position is not None and exam is not None
    essay = repository.add_question(
        user_ids["company"],
        exam["id"],
        expert_id=user_ids["expert"],
        title="Explain transaction isolation",
        content="Describe one isolation level.",
        difficulty="medium",
        points=10,
        question_type="essay",
        reference_answer="Expected discussion of anomalies.",
    )
    coding = repository.add_question(
        user_ids["company"],
        exam["id"],
        expert_id=user_ids["expert"],
        title="Add two integers",
        content="Read two integers and print their sum.",
        difficulty="easy",
        points=10,
        question_type="coding",
        test_cases=(
            {"input": "2 3\n", "expected_output": "5\n", "is_hidden": False},
            {"input": "-1 4\n", "expected_output": "3\n", "is_hidden": True},
        ),
        supported_languages=("python", "javascript"),
        reference_answer="print(sum(map(int, input().split())))",
    )
    assert essay is not None and coding is not None
    assert repository.publish_exam(user_ids["company"], exam["id"]) is not None
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
    assert accepted is not None
    session_id = accepted["exam_session_id"]
    started, session = repository.start_session_once(
        session_id, user_ids["candidate"]
    )
    assert started and session is not None
    return {
        "conn": conn,
        "repository": repository,
        "user_ids": user_ids,
        "skill_id": skill_id,
        "exam_id": exam["id"],
        "essay": essay,
        "coding": coding,
        "session_id": session_id,
    }


def test_essay_and_coding_answers_and_test_cases_persist_safely(final_workflow):
    repository = final_workflow["repository"]
    ids = final_workflow["user_ids"]
    session_id = final_workflow["session_id"]
    essay_id = final_workflow["essay"]["id"]
    coding_id = final_workflow["coding"]["id"]

    essay_answer = repository.save_candidate_written_answer(
        session_id, ids["candidate"], essay_id, "Isolation prevents dirty reads."
    )
    code_answer = repository.save_candidate_written_answer(
        session_id,
        ids["candidate"],
        coding_id,
        "a, b = map(int, input().split())\nprint(a + b)",
        programming_language="python",
    )
    assert essay_answer["answer_text"] == "Isolation prevents dirty reads."
    assert essay_answer["answer_code"] is None
    assert code_answer["answer_code"].startswith("a, b")
    assert code_answer["answer_text"] is None
    assert code_answer["programming_language"] == "python"
    assert repository.save_candidate_written_answer(
        session_id,
        ids["candidate"],
        coding_id,
        "source",
        programming_language="unsupported-lang",
    ) is None

    persisted = final_workflow["conn"].execute(
        "SELECT test_cases FROM question_bank WHERE id = ?", (coding_id,)
    ).fetchone()["test_cases"]
    test_cases = CodingTestCaseModel.from_json(persisted)
    assert len(test_cases) == 2
    assert test_cases[1].is_hidden
    assert repository.list_coding_test_cases(ids["expert"], coding_id)[1][
        "expected_output"
    ] == "3\n"
    assert repository.list_coding_test_cases(ids["candidate"], coding_id) is None

    candidate_questions = repository.list_candidate_questions(session_id, ids["candidate"])
    by_id = {question["id"]: question for question in candidate_questions}
    assert by_id[essay_id]["answer_text"] == "Isolation prevents dirty reads."
    assert by_id[coding_id]["answer_code"].startswith("a, b")
    assert by_id[coding_id]["supported_languages"] == ["python", "javascript"]
    assert by_id[coding_id]["programming_language"] == "python"
    assert "reference_answer" not in by_id[coding_id]
    assert "test_cases" not in by_id[coding_id]
    assert repository.save_candidate_written_answer(
        session_id, ids["candidate"], 999999, "unrelated answer"
    ) is None


def test_essay_and_coding_submissions_wait_for_authorized_grading(final_workflow):
    repository = final_workflow["repository"]
    ids = final_workflow["user_ids"]
    session_id = final_workflow["session_id"]
    essay_id = final_workflow["essay"]["id"]
    coding_id = final_workflow["coding"]["id"]
    repository.save_candidate_written_answer(
        session_id, ids["candidate"], essay_id, "Explain transaction isolation."
    )
    repository.save_candidate_written_answer(
        session_id, ids["candidate"], coding_id, "print('solution')"
    )

    submission = repository.submit_exam_for_grading(session_id, ids["candidate"])
    assert submission["status"] == "grading"
    pending = repository.list_exam_answers_for_grading(ids["company"], session_id)
    assert {answer.question_id for answer in pending} == {essay_id, coding_id}
    assert all(not answer.is_graded for answer in pending)
    assert repository.list_exam_answers_for_grading(ids["candidate"], session_id) == []
    assert {
        answer.question_id
        for answer in repository.list_exam_answers_for_grading(
            ids["company"], session_id, requester_id=ids["expert"]
        )
    } == {essay_id, coding_id}

    essay_grade = repository.grade_exam_answer(
        ids["company"],
        ids["expert"],
        session_id,
        essay_id,
        score=8,
        feedback="Clear explanation.",
    )
    assert essay_grade.is_graded and essay_grade.score == 8
    assert essay_grade.graded_by == ids["expert"]

    coding_grade = repository.grade_exam_answer(
        ids["company"],
        ids["expert"],
        session_id,
        coding_id,
        grading_mode="automatic",
        coding_test_results=(
            {"passed": True, "actual_output": "5\n"},
            {"passed": False, "actual_output": "2\n"},
        ),
    )
    assert coding_grade.grading_mode == "automatic"
    assert coding_grade.score == 5
    assert coding_grade.test_results[1]["passed"] is False
    assert repository.get_candidate_submission(
        session_id, ids["candidate"]
    )["status"] == "graded"

    revised = repository.grade_exam_answer(
        ids["company"],
        ids["expert"],
        session_id,
        essay_id,
        score=9,
        feedback="Re-evaluated.",
        revision_reason="Clarified rubric.",
    )
    assert revised.score == 9
    assert final_workflow["conn"].execute(
        "SELECT COUNT(*) FROM exam_grade_revisions WHERE exam_answer_id = ?",
        (revised.id,),
    ).fetchone()[0] == 1


def test_session_monitoring_events_are_scoped_and_immutable(final_workflow):
    repository = final_workflow["repository"]
    ids = final_workflow["user_ids"]
    proctoring = repository.start_exam_proctoring_session(
        final_workflow["session_id"],
        ids["candidate"],
        consent_for_evidence=False,
    )
    assert proctoring.status == "active"
    assert repository.get_company_exam_proctoring_session(
        ids["company"], final_workflow["session_id"]
    ) == proctoring
    with pytest.raises(sqlite3.IntegrityError, match="without explicit consent"):
        repository.record_exam_session_event(
            final_workflow["session_id"],
            ids["candidate"],
            "camera_snapshot",
            is_violation=True,
            evidence_uri="evidence://snapshot/1",
        )
    event = repository.record_exam_session_event(
        final_workflow["session_id"],
        ids["candidate"],
        "tab_hidden",
        is_violation=True,
        details={"visibility": "hidden", "count": 1},
        occurred_at="2026-11-24T11:00:00",
    )
    assert isinstance(event, ExamSessionEventModel)
    assert event.details == {"visibility": "hidden", "count": 1}
    assert len(
        repository.list_exam_session_events(
            final_workflow["session_id"], ids["candidate"], violations_only=True
        )
    ) == 1
    assert repository.list_exam_session_events(
        final_workflow["session_id"], ids["company"]
    ) == []
    assert repository.list_company_exam_session_events(
        ids["company"], final_workflow["session_id"], violations_only=True
    ) == [event]
    assert repository.list_company_exam_session_events(
        ids["company"],
        final_workflow["session_id"],
        requester_id=ids["expert"],
        violations_only=True,
    ) == [event]
    assert repository.finish_exam_proctoring_session(
        final_workflow["session_id"], ids["candidate"]
    ).status == "flagged"
    reviewed = repository.review_exam_session_event(
        ids["company"],
        ids["company"],
        event.id,
        processing_status="reviewed",
        notes="Reviewed, violation confirmed.",
    )
    assert reviewed.processing_status == "reviewed"
    assert reviewed.processed_by == ids["company"]
    assert repository.get_exam_proctoring_session(
        final_workflow["session_id"], ids["candidate"]
    ).status == "reviewed"

    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        final_workflow["conn"].execute(
            "UPDATE exam_session_events SET event_type = 'edited' WHERE id = ?",
            (event.id,),
        )
    with pytest.raises(sqlite3.IntegrityError, match="active session"):
        final_workflow["conn"].execute(
            """
            INSERT INTO exam_session_events
                (exam_session_id, candidate_id, event_type)
            VALUES (?, ?, 'wrong-owner')
            """,
            (final_workflow["session_id"], ids["company"]),
        )


def test_proctoring_evidence_reference_requires_and_records_consent(final_workflow):
    repository = final_workflow["repository"]
    candidate_id = final_workflow["user_ids"]["candidate"]
    session_id = final_workflow["session_id"]
    repository.start_exam_proctoring_session(
        session_id, candidate_id, consent_for_evidence=True
    )
    with pytest.raises(sqlite3.IntegrityError, match="embedded media"):
        repository.record_exam_session_event(
            session_id,
            candidate_id,
            "embedded_snapshot",
            is_violation=True,
            evidence_uri="data:image/png;base64,abc",
        )
    event = repository.record_exam_session_event(
        session_id,
        candidate_id,
        "screen_evidence",
        is_violation=True,
        evidence_uri="evidence://session/42",
    )
    assert event.evidence_uri == "evidence://session/42"
    assert event.consent_for_evidence


def test_interview_scheduling_and_evaluation_persist_with_scoping(final_workflow):
    repository = final_workflow["repository"]
    ids = final_workflow["user_ids"]
    interview = repository.schedule_interview(
        ids["company"],
        ids["candidate"],
        title="Technical interview",
        scheduled_at="2030-05-01T10:00:00",
        duration_min=45,
        description="Backend role",
        interviewer_ids=(ids["expert"],),
    )
    assert isinstance(interview, InterviewModel)
    assert repository.list_candidate_interviews(ids["candidate"]) == [interview]
    assert repository.list_company_interviews(ids["company"]) == [interview]
    assert [
        participant.expert_id
        for participant in repository.list_interview_participants(
            ids["company"], interview.id
        )
    ] == [ids["expert"]]
    interview = repository.set_interview_status(
        ids["company"], interview.id, "in_progress"
    )
    assert interview.status == "in_progress"
    evaluation = repository.save_interview_evaluation(
        interview.id,
        ids["expert"],
        technical_score=5,
        communication_score=4,
        problem_solving_score=5,
        overall_rating=5,
        feedback="Strong practical reasoning.",
        recommendation="strong_hire",
    )
    assert isinstance(evaluation, InterviewEvaluationModel)
    assert repository.list_interview_evaluations(
        ids["company"], interview.id
    ) == [evaluation]
    assert repository.list_interview_evaluations(
        ids["candidate"], interview.id
    ) == []
    with pytest.raises(sqlite3.IntegrityError, match="between 1 and 5"):
        repository.save_interview_evaluation(
            interview.id,
            ids["expert"],
            technical_score=6,
            communication_score=4,
            problem_solving_score=5,
            overall_rating=5,
        )


def test_certificate_issue_verify_and_revoke(final_workflow):
    repository = final_workflow["repository"]
    ids = final_workflow["user_ids"]
    certificate = repository.issue_certificate(
        ids["candidate"],
        final_workflow["skill_id"],
        score=96.5,
        cert_code="SP-FINAL-001",
    )
    assert isinstance(certificate, CertificateModel)
    assert repository.verify_certificate("SP-FINAL-001") == certificate
    assert repository.revoke_certificate(
        certificate.id, ids["company"], "Wrongly authorized request."
    ) is None
    revoked = repository.revoke_certificate(
        certificate.id, ids["admin"], "Issued against the wrong assessment."
    )
    assert revoked is not None and revoked.status == "revoked"
    assert revoked.revoked_by == ids["admin"]
    assert revoked.revocation_reason == "Issued against the wrong assessment."
    assert repository.verify_certificate("SP-FINAL-001") is None
    assert repository.list_user_certificates(ids["candidate"]) == [revoked]
    second_skill_id = final_workflow["conn"].execute(
        "INSERT INTO skills (name) VALUES ('Second final database skill')"
    ).lastrowid
    active_certificate = repository.issue_certificate(
        ids["candidate"],
        second_skill_id,
        score=75,
        cert_code="SP-FINAL-002",
    )
    with pytest.raises(sqlite3.IntegrityError, match="actor, time, and reason"):
        final_workflow["conn"].execute(
            "UPDATE certificates SET status = 'revoked' WHERE id = ?",
            (active_certificate.id,),
        )


def test_final_migration_is_repeatable_and_keeps_certificate_data(final_workflow):
    conn = final_workflow["conn"]
    ids = final_workflow["user_ids"]
    certificate = final_workflow["repository"].issue_certificate(
        ids["candidate"],
        final_workflow["skill_id"],
        score=80,
        cert_code="SP-MIG-001",
    )
    _mig_007_complete_assessment_data(conn)
    _mig_008_complete_feature_persistence(conn)
    _mig_007_complete_assessment_data(conn)
    _mig_008_complete_feature_persistence(conn)
    row = conn.execute(
        "SELECT id, cert_code, status FROM certificates WHERE id = ?",
        (certificate.id,),
    ).fetchone()
    assert tuple(row) == (certificate.id, "SP-MIG-001", "active")
    assert conn.execute(
        "SELECT COUNT(*) FROM exam_session_events"
    ).fetchone()[0] == 0


def test_full_legacy_upgrade_preserves_certificates(legacy_db):
    conn = legacy_db.get_connection()
    skill_id = conn.execute(
        "INSERT INTO skills (name) VALUES ('Legacy certificate skill')"
    ).lastrowid
    certificate_id = conn.execute(
        """
        INSERT INTO certificates (user_id, skill_id, score, cert_code)
        VALUES (1, ?, 88, 'SP-LEGACY-001')
        """,
        (skill_id,),
    ).lastrowid

    create_all_tables(conn)

    row = conn.execute(
        "SELECT id, cert_code, status, revoked_by FROM certificates WHERE id = ?",
        (certificate_id,),
    ).fetchone()
    assert tuple(row) == (certificate_id, "SP-LEGACY-001", "active", None)
    assert conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'exam_session_events'
        """
    ).fetchone() is not None
    assert conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'exam_proctoring_sessions'
        """
    ).fetchone() is not None

