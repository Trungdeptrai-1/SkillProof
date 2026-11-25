"""MIG-012: consent-based direct recruitment invitations.

These invitations are separate from assessment invitations and do not create exams.
"""
from __future__ import annotations
import sqlite3


def migrate_direct_invitations(conn: sqlite3.Connection) -> None:
    for name in ("users", "job_postings", "candidate_profiles"):
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone():
            raise RuntimeError(f"MIG-012 requires {name}")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS direct_recruitment_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_posting_id INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
            candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            message TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','accepted','declined','cancelled')),
            sent_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            responded_at TEXT,
            UNIQUE(job_posting_id, candidate_id),
            CHECK ((status='pending' AND responded_at IS NULL)
                OR (status<>'pending' AND responded_at IS NOT NULL))
        );
        CREATE INDEX IF NOT EXISTS idx_direct_invites_candidate
            ON direct_recruitment_invitations(candidate_id,status);
        CREATE INDEX IF NOT EXISTS idx_direct_invites_company
            ON direct_recruitment_invitations(company_id,status);
        CREATE TRIGGER IF NOT EXISTS trg_direct_invite_insert
        BEFORE INSERT ON direct_recruitment_invitations
        BEGIN
            SELECT CASE WHEN NOT EXISTS(
                SELECT 1 FROM users u JOIN job_postings jp ON jp.company_id=u.id
                WHERE u.id=NEW.company_id AND u.role='company'
                  AND u.is_active=1 AND COALESCE(u.is_deleted,0)=0
                  AND jp.id=NEW.job_posting_id AND jp.status='published'
            ) THEN RAISE(ABORT,'company must own published job') END;
            SELECT CASE WHEN NOT EXISTS(
                SELECT 1 FROM users u JOIN candidate_profiles cp ON cp.user_id=u.id
                WHERE u.id=NEW.candidate_id AND u.role='candidate'
                  AND u.is_active=1 AND COALESCE(u.is_deleted,0)=0
                  AND cp.is_discoverable=1
            ) THEN RAISE(ABORT,'candidate must explicitly opt in') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_direct_invite_identity
        BEFORE UPDATE OF company_id,job_posting_id,candidate_id
        ON direct_recruitment_invitations
        BEGIN
            SELECT RAISE(ABORT,'invitation identity is immutable');
        END;
    """)
    conn.commit()
