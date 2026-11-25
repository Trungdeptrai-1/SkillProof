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
