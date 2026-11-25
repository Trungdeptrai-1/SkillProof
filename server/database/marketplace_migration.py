"""MIG-011: candidate-driven job discovery and application foundation.

Existing exam invitations are not job applications: keep their lifecycle intact.
"""
from __future__ import annotations
import sqlite3


def migrate_job_marketplace(conn: sqlite3.Connection) -> None:
    """Add the marketplace tables without modifying existing recruitment records."""
    required = ("users", "job_postings", "candidate_profiles")
    for name in required:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone():
            raise RuntimeError(f"MIG-011 requires table {name}")
    fields = {row[1] for row in conn.execute("PRAGMA table_info(candidate_profiles)")}
    if "is_discoverable" not in fields:
        conn.execute(
            "ALTER TABLE candidate_profiles ADD COLUMN is_discoverable INTEGER NOT NULL "
            "DEFAULT 0 CHECK(is_discoverable IN (0,1))"
        )
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS job_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_posting_id INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
            candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'submitted'
                CHECK(status IN ('submitted','reviewing','shortlisted','assessment',
                                 'interview','offered','rejected','withdrawn')),
            cover_letter TEXT NOT NULL DEFAULT '',
            applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(job_posting_id,candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_job_applications_candidate
            ON job_applications(candidate_id,status);
        CREATE INDEX IF NOT EXISTS idx_job_applications_position
            ON job_applications(job_posting_id,status);
        CREATE TABLE IF NOT EXISTS saved_job_postings (
            candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_posting_id INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
            saved_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            PRIMARY KEY(candidate_id,job_posting_id)
        );
        CREATE TRIGGER IF NOT EXISTS trg_job_applications_check_insert
        BEFORE INSERT ON job_applications
        BEGIN
            SELECT CASE WHEN NOT EXISTS(
                SELECT 1 FROM users WHERE id=NEW.candidate_id
                 AND role='candidate' AND is_active=1 AND COALESCE(is_deleted,0)=0
            ) THEN RAISE(ABORT,'only active candidates may apply') END;
            SELECT CASE WHEN NOT EXISTS(
                SELECT 1 FROM job_postings jp
                JOIN users u ON u.id=jp.company_id
                WHERE jp.id=NEW.job_posting_id AND jp.status='published'
                  AND u.role='company' AND u.is_active=1
                  AND COALESCE(u.is_deleted,0)=0
            ) THEN RAISE(ABORT,'job must be published by an active company') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_saved_jobs_check_insert
        BEFORE INSERT ON saved_job_postings
        BEGIN
            SELECT CASE WHEN NOT EXISTS(
                SELECT 1 FROM users WHERE id=NEW.candidate_id
                  AND role='candidate' AND is_active=1 AND COALESCE(is_deleted,0)=0
            ) THEN RAISE(ABORT,'only active candidates may save jobs') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_job_applications_immutable
        BEFORE UPDATE OF job_posting_id,candidate_id ON job_applications
        BEGIN
            SELECT RAISE(ABORT,'application identity is immutable');
        END;
    """)
    conn.commit()
