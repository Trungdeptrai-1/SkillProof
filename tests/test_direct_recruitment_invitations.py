"""Direct invitations: SQLite permissions, consent, transitions and idempotent migration."""
import sqlite3
import pytest

from server.database.direct_invitation_migration import migrate_direct_invitations
from server.models.direct_invitation_repository import DirectInvitationRepository


@pytest.fixture
def invites(fresh_db):
    conn = fresh_db.get_connection()
    def user(name, role):
        cur = conn.execute(
            """INSERT INTO users(username,email,password,full_name,role,is_active)
               VALUES(?,?,?,?,?,1)""",
            (name, name + "@example.test", "not-a-real-password-hash", name, role),
        )
        return cur.lastrowid
    company = user("invite-company", "company")
    other = user("invite-other", "company")
    candidate = user("invite-candidate", "candidate")
    stranger = user("invite-stranger", "candidate")
    conn.execute(
        "INSERT INTO candidate_profiles(user_id,headline,is_discoverable) VALUES(?,?,1)",
        (candidate, "Python dev"),
    )
    conn.execute(
        "INSERT INTO candidate_profiles(user_id,headline,is_discoverable) VALUES(?,?,0)",
        (stranger, "Private dev"),
    )
    job = conn.execute(
        """INSERT INTO job_postings(company_id,title,status)
           VALUES(?,'Developer','published')""", (company,),
    ).lastrowid
    draft = conn.execute(
        """INSERT INTO job_postings(company_id,title,status)
           VALUES(?,'Private role','draft')""", (company,),
    ).lastrowid
    conn.commit()
    return conn, DirectInvitationRepository(conn), company, other, candidate, stranger, job, draft


def test_migration_idempotent_and_does_not_touch_exam_invitations(invites):
    conn, repo, company, other, candidate, stranger, job, draft = invites
    migrate_direct_invitations(conn)
    migrate_direct_invitations(conn)
    assert conn.execute("SELECT count(*) FROM direct_recruitment_invitations").fetchone()[0] == 0
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='recruitment_invitations'"
    ).fetchone() is not None


def test_consent_ownership_duplicate_and_draft_protection(invites):
    conn, repo, company, other, candidate, stranger, job, draft = invites
    assert repo.send(other, job, candidate) is None
    assert repo.send(company, draft, candidate) is None
    assert repo.send(company, job, stranger) is None
    row = repo.send(company, job, candidate, "Join our team")
    assert row and row["status"] == "pending"
    assert repo.send(company, job, candidate) is None
    assert repo.received(stranger) == []
    assert repo.sent(other) == []
    assert len(repo.received(candidate)) == 1
    assert len(repo.sent(company)) == 1
    assert conn.execute("SELECT count(*) FROM recruitment_invitations").fetchone()[0] == 0


def test_candidate_may_accept_or_decline_once_and_only_own_invite(invites):
    _, repo, company, _, candidate, stranger, job, _ = invites
    row = repo.send(company, job, candidate)
    assert row is not None
    assert not repo.respond(stranger, row["id"], True)
    assert repo.respond(candidate, row["id"], True)
    assert repo.received(candidate)[0]["status"] == "accepted"
    # Candidate is now present in the same applications pipeline as self-applicants.
    created = repo.conn.execute(
        "SELECT status FROM job_applications WHERE candidate_id=? AND job_posting_id=?",
        (candidate, job),
    ).fetchone()
    assert created is not None and created["status"] == "submitted"
    assert not repo.respond(candidate, row["id"], False)
    assert not repo.cancel(company, row["id"])


def test_company_can_cancel_pending_but_not_other_company(invites):
    _, repo, company, other, candidate, _, job, _ = invites
    row = repo.send(company, job, candidate)
    assert row is not None
    assert not repo.cancel(other, row["id"])
    assert repo.cancel(company, row["id"])
    assert repo.received(candidate)[0]["status"] == "cancelled"
    assert not repo.respond(candidate, row["id"], True)
    assert not repo.cancel(company, row["id"])


def test_sqlite_trigger_rejects_non_opt_in_candidate(invites):
    conn, _, company, _, candidate, stranger, job, _ = invites
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO direct_recruitment_invitations
               (company_id,job_posting_id,candidate_id) VALUES(?,?,?)""",
            (company, job, stranger),
        )

def test_acceptance_reuses_existing_application_without_duplicate(invites):
    conn, repo, company, _, candidate, _, job, _ = invites
    conn.execute(
        "INSERT INTO job_applications(job_posting_id,candidate_id) VALUES(?,?)",
        (job, candidate),
    )
    conn.commit()
    row = repo.send(company, job, candidate)
    assert row and repo.respond(candidate, row["id"], True)
    count = conn.execute(
        "SELECT COUNT(*) FROM job_applications WHERE job_posting_id=? AND candidate_id=?",
        (job, candidate),
    ).fetchone()[0]
    assert count == 1


def test_closed_vacancy_prevents_acceptance_without_partial_changes(invites):
    conn, repo, company, _, candidate, _, job, _ = invites
    row = repo.send(company, job, candidate)
    assert row is not None
    conn.execute("UPDATE job_postings SET status='closed' WHERE id=?", (job,))
    conn.commit()
    assert repo.respond(candidate, row["id"], True) is False
    assert repo.received(candidate)[0]["status"] == "pending"
    assert conn.execute(
        "SELECT COUNT(*) FROM job_applications WHERE candidate_id=?", (candidate,)
    ).fetchone()[0] == 0


def test_decline_does_not_create_application(invites):
    conn, repo, company, _, candidate, _, job, _ = invites
    row = repo.send(company, job, candidate)
    assert row and repo.respond(candidate, row["id"], False)
    assert repo.received(candidate)[0]["status"] == "declined"
    assert conn.execute("SELECT count(*) FROM job_applications").fetchone()[0] == 0


def test_withdrawn_application_is_not_silently_reopened_by_accepting_invite(invites):
    conn, repo, company, _, candidate, _, job, _ = invites
    conn.execute(
        "INSERT INTO job_applications(job_posting_id,candidate_id,status) VALUES(?,?,'withdrawn')",
        (job, candidate),
    )
    conn.commit()
    row = repo.send(company, job, candidate)
    assert row and not repo.respond(candidate, row["id"], True)
    assert repo.received(candidate)[0]["status"] == "pending"
    assert conn.execute(
        "SELECT status FROM job_applications WHERE candidate_id=? AND job_posting_id=?",
        (candidate, job),
    ).fetchone()["status"] == "withdrawn"
