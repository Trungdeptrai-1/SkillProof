"""MIG-013: associate hiring applications with interviews and final decisions.

No modifications to legacy interviews or exam invitations; new records only.
"""
from __future__ import annotations
import sqlite3


def migrate_hiring_decisions(conn: sqlite3.Connection) -> None:
    for name in ("job_applications", "interviews", "job_postings"):
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is None:
            raise RuntimeError(f"MIG-013 requires {name}")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS application_interviews (
            application_id INTEGER PRIMARY KEY
                REFERENCES job_applications(id) ON DELETE CASCADE,
            interview_id INTEGER NOT NULL UNIQUE
                REFERENCES interviews(id) ON DELETE CASCADE,
            linked_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            decision TEXT CHECK(decision IN ('offered','rejected')),
            decision_note TEXT NOT NULL DEFAULT '',
            decided_at TEXT,
            CHECK (
                (decision IS NULL AND decided_at IS NULL)
                OR (decision IS NOT NULL AND decided_at IS NOT NULL)
            )
        );
        CREATE TRIGGER IF NOT EXISTS trg_application_interview_match
        BEFORE INSERT ON application_interviews
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1
                FROM job_applications ja
                JOIN job_postings jp ON jp.id=ja.job_posting_id
                JOIN interviews i ON i.id=NEW.interview_id
                WHERE ja.id=NEW.application_id AND ja.candidate_id=i.candidate_id
                  AND jp.company_id=i.company_id
            ) THEN RAISE(ABORT,'interview candidate/company mismatch') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_application_interview_identity
        BEFORE UPDATE OF application_id,interview_id ON application_interviews
        BEGIN
            SELECT RAISE(ABORT,'interview link identity is immutable');
        END;
    """)
    conn.commit()
