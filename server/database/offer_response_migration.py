"""MIG-014: candidate's response to an employer's final hiring offer.

The company decision remains immutable; the candidate's reply is recorded
separately, only for an offered application.
"""
from __future__ import annotations
import sqlite3


def migrate_offer_responses(conn: sqlite3.Connection) -> None:
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='application_interviews'"
    ).fetchone() is None:
        raise RuntimeError("MIG-014 requires application_interviews (MIG-013)")
    columns = {
        item[1] for item in conn.execute("PRAGMA table_info(application_interviews)")
    }
    if "offer_response" not in columns:
        conn.execute(
            "ALTER TABLE application_interviews ADD COLUMN offer_response TEXT "
            "CHECK(offer_response IN ('accepted','declined'))"
        )
    if "offer_responded_at" not in columns:
        conn.execute(
            "ALTER TABLE application_interviews ADD COLUMN offer_responded_at TEXT"
        )
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS trg_offer_reply_validate_insert
        BEFORE INSERT ON application_interviews
        WHEN NEW.offer_response IS NOT NULL OR NEW.offer_responded_at IS NOT NULL
        BEGIN
            SELECT CASE WHEN NEW.decision IS NOT 'offered'
                OR NEW.offer_response IS NULL OR NEW.offer_responded_at IS NULL
                THEN RAISE(ABORT,'invalid candidate offer response') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_offer_reply_validate_update
        BEFORE UPDATE OF offer_response,offer_responded_at,decision
        ON application_interviews
        BEGIN
            SELECT CASE WHEN
                (NEW.offer_response IS NULL) != (NEW.offer_responded_at IS NULL)
                OR (NEW.offer_response IS NOT NULL AND NEW.decision IS NOT 'offered')
                THEN RAISE(ABORT,'invalid candidate offer response') END;
            SELECT CASE WHEN OLD.offer_response IS NOT NULL
                AND (NEW.offer_response IS NOT OLD.offer_response
                     OR NEW.offer_responded_at IS NOT OLD.offer_responded_at)
                THEN RAISE(ABORT,'candidate response is final') END;
        END;
    """)
    conn.commit()
