"""Direct recruiting invitation persistence, separate from assessment invitations."""
from __future__ import annotations
import sqlite3
from threading import RLock
from server.database.connection import db

_LOCK = RLock()


class DirectInvitationRepository:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self.conn = connection if connection is not None else db.get_connection()
        self.conn.row_factory = sqlite3.Row

    def _active(self, user_id: int, role: str) -> bool:
        if type(user_id) is not int or user_id <= 0:
            return False
        return self.conn.execute(
            "SELECT 1 FROM users WHERE id=? AND role=? AND is_active=1 AND COALESCE(is_deleted,0)=0",
            (user_id, role),
        ).fetchone() is not None

    @staticmethod
    def _all(cursor) -> list[dict]:
        return [dict(row) for row in cursor.fetchall()]

    def send(self, company_id: int, job_id: int, candidate_id: int, message: str = "") -> dict | None:
        if (not isinstance(message, str) or len(message) > 2000 or type(job_id) is not int
                or type(candidate_id) is not int or job_id <= 0 or candidate_id <= 0):
            return None
        with _LOCK:
            if not self._active(company_id, "company"):
                return None
            try:
                cur = self.conn.execute(
                    """INSERT INTO direct_recruitment_invitations
                       (company_id,job_posting_id,candidate_id,message)
                       VALUES(?,?,?,?)""",
                    (company_id, job_id, candidate_id, message.strip()),
                )
                self.conn.commit()
                row = self.conn.execute(
                    "SELECT * FROM direct_recruitment_invitations WHERE id=?",
                    (cur.lastrowid,),
                ).fetchone()
                return dict(row) if row else None
            except sqlite3.IntegrityError:
                self.conn.rollback()
                return None

    def received(self, candidate_id: int) -> list[dict]:
        with _LOCK:
            if not self._active(candidate_id, "candidate"):
                return []
            return self._all(self.conn.execute(
                """SELECT di.id,di.job_posting_id,di.status,di.message,di.sent_at,
                          di.responded_at,jp.title AS job_title,
                          COALESCE(cp.company_name,u.full_name) AS company_name
                   FROM direct_recruitment_invitations di
                   JOIN job_postings jp ON jp.id=di.job_posting_id
                   JOIN users u ON u.id=di.company_id
                   LEFT JOIN company_profiles cp ON cp.user_id=di.company_id
                   WHERE di.candidate_id=?
                   ORDER BY di.sent_at DESC,di.id DESC""",
                (candidate_id,),
            ))

    def sent(self, company_id: int) -> list[dict]:
        with _LOCK:
            if not self._active(company_id, "company"):
                return []
            return self._all(self.conn.execute(
                """SELECT di.id,di.job_posting_id,di.candidate_id,di.status,
                          di.message,di.sent_at,di.responded_at,
                          jp.title AS job_title,u.full_name AS candidate_name
                   FROM direct_recruitment_invitations di
                   JOIN job_postings jp ON jp.id=di.job_posting_id
                   JOIN users u ON u.id=di.candidate_id
                   WHERE di.company_id=?
                   ORDER BY di.sent_at DESC,di.id DESC""",
                (company_id,),
            ))

    def respond(self, candidate_id: int, invitation_id: int, accepted: bool) -> bool:
        if type(invitation_id) is not int or invitation_id <= 0 or type(accepted) is not bool:
            return False
        with _LOCK:
            if not self._active(candidate_id, "candidate"):
                return False
            result = self.conn.execute(
                """UPDATE direct_recruitment_invitations
                   SET status=?, responded_at=datetime('now','localtime')
                   WHERE id=? AND candidate_id=? AND status='pending'""",
                ("accepted" if accepted else "declined", invitation_id, candidate_id),
            )
            self.conn.commit()
            return result.rowcount == 1

    def cancel(self, company_id: int, invitation_id: int) -> bool:
        if type(invitation_id) is not int or invitation_id <= 0:
            return False
        with _LOCK:
            if not self._active(company_id, "company"):
                return False
            result = self.conn.execute(
                """UPDATE direct_recruitment_invitations
                   SET status='cancelled',responded_at=datetime('now','localtime')
                   WHERE id=? AND company_id=? AND status='pending'""",
                (invitation_id, company_id),
            )
            self.conn.commit()
            return result.rowcount == 1
