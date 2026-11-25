"""Marketplace foundation: real SQLite integration, no user data touched."""
import sqlite3
import pytest

from app.utils.helpers import hash_password
from server.database.marketplace_migration import migrate_job_marketplace
from server.models.marketplace_repository import MarketplaceRepository


def account(conn, role: str, name: str) -> int:
    c = conn.execute(
        """INSERT INTO users(username,email,password,full_name,role,is_active,is_deleted)
           VALUES(?,?,?,?,?,1,0)""",
        (name, f"{name}@example.test", hash_password("SafeDemo123"), name, role),
    )
    return int(c.lastrowid)


@pytest.fixture
def market(fresh_db):
    conn = fresh_db.get_connection()
    migrate_job_marketplace(conn)
    company = account(conn, "company", "market-company")
    other_company = account(conn, "company", "market-other-company")
    candidate = account(conn, "candidate", "market-candidate")
    second = account(conn, "candidate", "market-second")
    conn.execute(
        "INSERT INTO candidate_profiles(user_id,headline) VALUES(?,?)",
        (candidate, "Python Developer"),
    )
    published = conn.execute(
        """INSERT INTO job_postings(company_id,title,description,requirements,location,status)
           VALUES(?,'Python Engineer','Build apps','Python','Da Nang','published')""",
        (company,),
    ).lastrowid
    draft = conn.execute(
        """INSERT INTO job_postings(company_id,title,description,requirements,location,status)
           VALUES(?,'Secret Role','private','','Da Nang','draft')""",
        (company,),
    ).lastrowid
    conn.commit()
    return conn, MarketplaceRepository(conn), company, other_company, candidate, second, published, draft


def test_migration_idempotent_and_private_default(market):
    conn, _, _, _, candidate, _, _, _ = market
    migrate_job_marketplace(conn)
    migrate_job_marketplace(conn)
    row = conn.execute("SELECT is_discoverable FROM candidate_profiles WHERE user_id=?", (candidate,)).fetchone()
    assert row["is_discoverable"] == 0
    assert conn.execute("SELECT count(*) FROM job_applications").fetchone()[0] == 0


def test_browse_save_and_apply_only_to_published(market):
    _, repo, company, _, candidate, _, published, draft = market
    rows = repo.browse_jobs(candidate, "Python", "Da Nang")
    assert [row["id"] for row in rows] == [published]
    assert repo.browse_jobs(company) == []
    assert repo.apply(candidate, draft) is None
    assert repo.save_job(candidate, draft) is False
    assert repo.save_job(candidate, published)
    assert repo.save_job(candidate, published)
    assert repo.browse_jobs(candidate)[0]["saved"] == 1
    submitted = repo.apply(candidate, published, "Interested in this role")
    assert submitted and submitted["status"] == "submitted"
    assert repo.apply(candidate, published) is None
    assert repo.browse_jobs(candidate)[0]["applied"] == 1
    assert repo.unsave_job(candidate, published)


def test_company_sees_own_applicants_only_and_candidate_can_withdraw(market):
    _, repo, company, other_company, candidate, _, published, _ = market
    submitted = repo.apply(candidate, published)
    assert submitted
    assert repo.applicants(other_company, published) == []
    assert len(repo.applicants(company, published)) == 1
    assert repo.update_application_status(other_company, submitted["id"], "reviewing") is False
    assert repo.update_application_status(company, submitted["id"], "reviewing")
    assert repo.withdraw(candidate, submitted["id"])
    assert not repo.update_application_status(company, submitted["id"], "offered")
    assert repo.my_applications(candidate)[0]["status"] == "withdrawn"


def test_candidate_visibility_opt_in_never_exposes_contacts(market):
    _, repo, company, _, candidate, _, _, _ = market
    assert repo.discover_candidates(company) == []
    assert repo.set_discoverable(candidate, True)
    found = repo.discover_candidates(company, "Python")
    assert len(found) == 1 and found[0]["id"] == candidate
    assert "email" not in found[0] and "resume_path" not in found[0]
    assert repo.set_discoverable(candidate, False)
    assert repo.discover_candidates(company) == []


def test_sql_blocks_wrong_roles_and_duplicate_application(market):
    conn, _, company, _, candidate, second, published, _ = market
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO job_applications(job_posting_id,candidate_id) VALUES(?,?)",
            (published, company),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO job_applications(job_posting_id,candidate_id) VALUES(?,?)",
            (999999, second),
        )
    # The direct SQL attempt must not create an application.
    assert conn.execute("SELECT count(*) FROM job_applications").fetchone()[0] == 0

def test_saved_jobs_are_scoped_to_owner_and_include_closed_positions(market):
    conn, repo, company, other_company, candidate, second, published, _ = market
    assert repo.saved_jobs(second) == []
    assert repo.saved_jobs(company) == []
    assert repo.save_job(candidate, published)
    assert [item["id"] for item in repo.saved_jobs(candidate)] == [published]
    assert repo.saved_jobs(second) == []
    conn.execute(
        "UPDATE job_postings SET status='closed' WHERE id=? AND company_id=?",
        (published, company),
    )
    conn.commit()
    listed = repo.saved_jobs(candidate)
    assert len(listed) == 1 and listed[0]["status"] == "closed"
    assert repo.unsave_job(candidate, published)
    assert repo.saved_jobs(candidate) == []

def test_assessment_handoff_uses_real_applicant_and_changes_stage_only_on_success(market, monkeypatch):
    from types import SimpleNamespace
    from app.models.user_model import UserModel
    from app.services.auth_service import SessionManager
    from server.services.marketplace_service import MarketplaceService

    conn, repo, company, other, candidate, _, job, _ = market
    submitted = repo.apply(candidate, job)
    assert submitted
    assert repo.update_application_status(company, submitted["id"], "reviewing")
    assert repo.update_application_status(company, submitted["id"], "shortlisted")

    session = SessionManager.instance()
    session.end_session()
    session.start_session(UserModel(
        id=company, username="comp", email="company@example.test",
        full_name="Company", role="company", avatar_path=None,
        is_active=True, created_at="", updated_at="",
    ))
    calls = []
    class StubExamController:
        def __init__(self, service):
            pass

        def invite_candidate(self, job_id, exam_id, candidate_id):
            calls.append((job_id, exam_id, candidate_id))
            return SimpleNamespace(
                success=True, invitation={"id": 91}, message="OK",
            )

    monkeypatch.setattr(
        "server.controllers.exam_controller.ExamController",
        StubExamController,
    )
    try:
        service = MarketplaceService(repo)
        result = service.invite_applicant_to_exam(submitted["id"], 7)
        assert result.success
        assert calls == [(job, 7, candidate)]
        assert repo.application_for_company(company, submitted["id"])["status"] == "assessment"
        assert repo.application_for_company(other, submitted["id"]) is None
        assert not service.invite_applicant_to_exam(submitted["id"], 7).success
        assert calls == [(job, 7, candidate)]
    finally:
        session.end_session()


def test_assessment_handoff_rejects_wrong_stage_without_sending(market, monkeypatch):
    from app.models.user_model import UserModel
    from app.services.auth_service import SessionManager
    from server.services.marketplace_service import MarketplaceService
    conn, repo, company, _, candidate, _, job, _ = market
    application = repo.apply(candidate, job)
    assert application
    session = SessionManager.instance()
    session.end_session()
    session.start_session(UserModel(
        id=company, username="comp", email="company@example.test",
        full_name="Company", role="company", avatar_path=None,
        is_active=True, created_at="", updated_at="",
    ))
    try:
        result = MarketplaceService(repo).invite_applicant_to_exam(application["id"], 7)
        assert not result.success
        assert repo.application_for_company(company, application["id"])["status"] == "submitted"
    finally:
        session.end_session()


def test_interview_handoff_requires_released_result_and_company_ownership(market, monkeypatch):
    from app.models.user_model import UserModel
    from app.services.auth_service import SessionManager
    from server.services.marketplace_service import MarketplaceService

    conn, repo, company, other, candidate, _, job, _ = market
    application = repo.apply(candidate, job)
    assert application
    assert repo.update_application_status(company, application["id"], "reviewing")
    assert repo.update_application_status(company, application["id"], "shortlisted")
    conn.execute(
        "UPDATE job_applications SET status='assessment' WHERE id=?",
        (application["id"],),
    )
    conn.commit()
    session = SessionManager.instance()
    session.end_session()
    session.start_session(UserModel(
        id=company, username="company", email="company@sample.test",
        full_name="Company", role="company", avatar_path=None,
        is_active=True, created_at="", updated_at="",
    ))
    try:
        service = MarketplaceService(repo)
        result = service.schedule_application_interview(
            application["id"], "Technical interview", "2099-12-01T10:00:00"
        )
        assert not result.success
        assert repo.application_for_company(company, application["id"])["status"] == "assessment"
        assert repo.application_for_company(other, application["id"]) is None
        assert not repo.has_released_assessment(company, job, candidate)
    finally:
        session.end_session()


def test_interview_handoff_changes_stage_only_when_scheduling_succeeds(market, monkeypatch):
    from types import SimpleNamespace
    from app.models.user_model import UserModel
    from app.services.auth_service import SessionManager
    from server.services.marketplace_service import MarketplaceService

    conn, repo, company, _, candidate, _, job, _ = market
    application = repo.apply(candidate, job)
    assert application
    for new_status in ("reviewing", "shortlisted"):
        assert repo.update_application_status(company, application["id"], new_status)
    conn.execute("UPDATE job_applications SET status='assessment' WHERE id=?", (application["id"],))
    conn.commit()
    monkeypatch.setattr(repo, "has_released_assessment", lambda *_: True)
    interview_id = conn.execute(
        """INSERT INTO interviews(candidate_id,company_id,title,scheduled_at)
           VALUES(?,?,?,?)""",
        (candidate, company, "Integration test interview", "2099-12-01T10:00:00"),
    ).lastrowid
    conn.commit()
    calls = []
    class StubInterviewController:
        should_fail = True
        def __init__(self, service):
            pass
        def schedule(self, candidate_id, title, scheduled_at, **kwargs):
            calls.append((candidate_id, title, scheduled_at))
            if self.should_fail:
                return SimpleNamespace(success=False, message="Invalid date", record=None)
            return SimpleNamespace(success=True, message="OK", record={"id": interview_id})

    monkeypatch.setattr(
        "server.controllers.supplementary_workflow_controller.InterviewController",
        StubInterviewController,
    )
    session = SessionManager.instance()
    session.end_session()
    session.start_session(UserModel(
        id=company, username="company", email="company@sample.test",
        full_name="Company", role="company", avatar_path=None,
        is_active=True, created_at="", updated_at="",
    ))
    try:
        service = MarketplaceService(repo)
        args = (application["id"], "Interview", "2099-12-01T10:00:00")
        assert not service.schedule_application_interview(*args).success
        assert repo.application_for_company(company, application["id"])["status"] == "assessment"
        StubInterviewController.should_fail = False
        assert service.schedule_application_interview(*args).success
        assert repo.application_for_company(company, application["id"])["status"] == "interview"
        assert conn.execute(
            "SELECT interview_id FROM application_interviews WHERE application_id=?",
            (application["id"],)
        ).fetchone()["interview_id"] == interview_id
        assert not service.schedule_application_interview(*args).success
        assert len(calls) == 2
    finally:
        session.end_session()


def test_final_hiring_decision_requires_completed_linked_interview(market):
    from server.database.hiring_decision_migration import migrate_hiring_decisions

    conn, repo, company, other, candidate, second, job, _ = market
    migrate_hiring_decisions(conn)
    app = repo.apply(candidate, job)
    assert app is not None
    interview_id = conn.execute(
        """INSERT INTO interviews(candidate_id,company_id,title,scheduled_at,status)
           VALUES(?,?,?,'2099-12-01T10:00:00','scheduled')""",
        (candidate, company, "Interview"),
    ).lastrowid
    conn.execute(
        "INSERT INTO application_interviews(application_id,interview_id) VALUES(?,?)",
        (app["id"], interview_id),
    )
    conn.execute("UPDATE job_applications SET status='interview' WHERE id=?", (app["id"],))
    conn.commit()
    assert repo.decide_after_interview(other, app["id"], "offered") is None
    assert repo.decide_after_interview(company, app["id"], "offered") is None
    assert repo.my_applications(candidate)[0]["decision_note"] == ""
    conn.execute("UPDATE interviews SET status='completed' WHERE id=?", (interview_id,))
    conn.commit()
    result = repo.decide_after_interview(company, app["id"], "offered", "Chúc mừng, đạt yêu cầu")
    assert result and result["status"] == "offered"
    assert result["decision_note"] == "Chúc mừng, đạt yêu cầu"
    assert repo.decide_after_interview(company, app["id"], "rejected") is None
    assert repo.my_applications(candidate)[0]["decision_note"] == "Chúc mừng, đạt yêu cầu"
    assert repo.my_applications(second) == []


def test_interview_link_rejects_mismatched_candidate_and_company(market):
    conn, repo, company, other, candidate, second, job, _ = market
    app = repo.apply(candidate, job)
    assert app
    wrong_candidate_interview = conn.execute(
        """INSERT INTO interviews(candidate_id,company_id,title,scheduled_at)
           VALUES(?,?,?,?)""",
        (second, company, "Other person", "2099-12-01T10:00:00"),
    ).lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO application_interviews(application_id,interview_id) VALUES(?,?)",
            (app["id"], wrong_candidate_interview),
        )
    assert conn.execute("SELECT count(*) FROM application_interviews").fetchone()[0] == 0
