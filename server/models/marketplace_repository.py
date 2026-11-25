"""Role-scoped SQLite repository for a candidate/company job marketplace."""
from __future__ import annotations

import sqlite3
from threading import RLock
from server.database.connection import db

_LOCK = RLock()
COMPANY_STATUSES = frozenset(
    {"reviewing", "shortlisted", "offered", "rejected"}
)


class MarketplaceRepository:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self.conn = connection if connection is not None else db.get_connection()
        self.conn.row_factory = sqlite3.Row

    def _role(self, user_id: int, role: str) -> bool:
        if type(user_id) is not int or user_id <= 0:
            return False
        row = self.conn.execute(
            """SELECT 1 FROM users WHERE id=? AND role=? AND is_active=1
               AND COALESCE(is_deleted,0)=0""", (user_id, role)
        ).fetchone()
        return row is not None

    @staticmethod
    def _rows(cursor) -> list[dict[str, object]]:
        return [dict(row) for row in cursor.fetchall()]

    def browse_jobs(self, candidate_id: int, search: str = "", location: str = "") -> list[dict[str, object]]:
        """Published jobs only; never reveal drafts or private company details."""
        with _LOCK:
            if not self._role(candidate_id, "candidate"):
                return []
            needle = f"%{search.strip()}%"
            place = f"%{location.strip()}%"
            return self._rows(self.conn.execute(
                """SELECT jp.id, jp.company_id, jp.title, jp.description,
                          jp.requirements, jp.location, jp.created_at,
                          COALESCE(cp.company_name,u.full_name) AS company_name,
                          cp.industry,
                          CASE WHEN sj.candidate_id IS NULL THEN 0 ELSE 1 END AS saved,
                          CASE WHEN ja.id IS NULL THEN 0 ELSE 1 END AS applied
                   FROM job_postings jp JOIN users u ON u.id=jp.company_id
                   LEFT JOIN company_profiles cp ON cp.user_id=jp.company_id
                   LEFT JOIN saved_job_postings sj
                     ON sj.job_posting_id=jp.id AND sj.candidate_id=?
                   LEFT JOIN job_applications ja
                     ON ja.job_posting_id=jp.id AND ja.candidate_id=?
                   WHERE jp.status='published' AND u.role='company'
                     AND u.is_active=1 AND COALESCE(u.is_deleted,0)=0
                     AND (jp.title LIKE ? OR jp.requirements LIKE ?
                          OR COALESCE(cp.company_name,u.full_name) LIKE ?)
                     AND COALESCE(jp.location,'') LIKE ?
                   ORDER BY jp.created_at DESC, jp.id DESC""",
                (candidate_id, candidate_id, needle, needle, needle, place),
            ))

    def apply(self, candidate_id: int, job_id: int, cover_letter: str = "") -> dict[str, object] | None:
        """One application per candidate/job. No automatic exam invitation."""
        if type(job_id) is not int or job_id <= 0 or not isinstance(cover_letter, str):
            return None
        if len(cover_letter) > 4000:
            return None
        with _LOCK:
            if not self._role(candidate_id, "candidate"):
                return None
            try:
                self.conn.execute(
                    """INSERT INTO job_applications(job_posting_id,candidate_id,cover_letter)
                       VALUES(?,?,?)""", (job_id, candidate_id, cover_letter.strip())
                )
                self.conn.commit()
            except sqlite3.IntegrityError:
                self.conn.rollback()
                return None
            row = self.conn.execute(
                "SELECT * FROM job_applications WHERE job_posting_id=? AND candidate_id=?",
                (job_id, candidate_id),
            ).fetchone()
            return dict(row) if row else None

    def my_applications(self, candidate_id: int) -> list[dict[str, object]]:
        with _LOCK:
            if not self._role(candidate_id, "candidate"):
                return []
            return self._rows(self.conn.execute(
                """SELECT ja.id,ja.job_posting_id,ja.status,ja.applied_at,
                          ja.updated_at,jp.title, jp.location,
                          COALESCE(cp.company_name,u.full_name) AS company_name
                   FROM job_applications ja
                   JOIN job_postings jp ON jp.id=ja.job_posting_id
                   JOIN users u ON u.id=jp.company_id
                   LEFT JOIN company_profiles cp ON cp.user_id=jp.company_id
                   WHERE ja.candidate_id=? ORDER BY ja.applied_at DESC,ja.id DESC""",
                (candidate_id,),
            ))

    def withdraw(self, candidate_id: int, application_id: int) -> bool:
        if type(application_id) is not int or application_id <= 0:
            return False
        with _LOCK:
            if not self._role(candidate_id, "candidate"):
                return False
            result = self.conn.execute(
                """UPDATE job_applications SET status='withdrawn',
                   updated_at=datetime('now','localtime')
                   WHERE id=? AND candidate_id=?
                     AND status IN ('submitted','reviewing','shortlisted')""",
                (application_id, candidate_id),
            )
            self.conn.commit()
            return result.rowcount == 1

    def save_job(self, candidate_id: int, job_id: int) -> bool:
        if type(job_id) is not int or job_id <= 0:
            return False
        with _LOCK:
            if not self._role(candidate_id, "candidate"):
                return False
            try:
                self.conn.execute(
                    """INSERT OR IGNORE INTO saved_job_postings(candidate_id,job_posting_id)
                       SELECT ?, jp.id FROM job_postings jp
                       JOIN users u ON u.id=jp.company_id
                       WHERE jp.id=? AND jp.status='published' AND u.role='company'
                         AND u.is_active=1 AND COALESCE(u.is_deleted,0)=0""",
                    (candidate_id, job_id),
                )
                found = self.conn.execute(
                    "SELECT 1 FROM saved_job_postings WHERE candidate_id=? AND job_posting_id=?",
                    (candidate_id, job_id),
                ).fetchone()
                self.conn.commit()
                return found is not None
            except sqlite3.IntegrityError:
                self.conn.rollback()
                return False

    def saved_jobs(self, candidate_id: int) -> list[dict[str, object]]:
        """Show only the signed-in candidate's saved jobs and publication state."""
        with _LOCK:
            if not self._role(candidate_id, "candidate"):
                return []
            return self._rows(self.conn.execute(
                """SELECT jp.id, jp.title, jp.location, jp.status,
                          COALESCE(cp.company_name,u.full_name) AS company_name,
                          sj.saved_at,
                          CASE WHEN ja.id IS NULL THEN 0 ELSE 1 END AS applied
                   FROM saved_job_postings sj
                   JOIN job_postings jp ON jp.id=sj.job_posting_id
                   JOIN users u ON u.id=jp.company_id
                   LEFT JOIN company_profiles cp ON cp.user_id=jp.company_id
                   LEFT JOIN job_applications ja
                     ON ja.job_posting_id=jp.id AND ja.candidate_id=sj.candidate_id
                   WHERE sj.candidate_id=?
                   ORDER BY sj.saved_at DESC, jp.id DESC""",
                (candidate_id,),
            ))

    def unsave_job(self, candidate_id: int, job_id: int) -> bool:
        with _LOCK:
            if not self._role(candidate_id, "candidate"):
                return False
            removed = self.conn.execute(
                "DELETE FROM saved_job_postings WHERE candidate_id=? AND job_posting_id=?",
                (candidate_id, job_id),
            )
            self.conn.commit()
            return removed.rowcount == 1

    def applicants(self, company_id: int, job_id: int) -> list[dict[str, object]]:
        """Company sees applicants only for its own position."""
        with _LOCK:
            if not self._role(company_id, "company"):
                return []
            return self._rows(self.conn.execute(
                """SELECT ja.id,ja.candidate_id,ja.status,ja.applied_at,
                          ja.cover_letter,u.full_name, cp.headline
                   FROM job_applications ja
                   JOIN job_postings jp ON jp.id=ja.job_posting_id
                   JOIN users u ON u.id=ja.candidate_id
                   LEFT JOIN candidate_profiles cp ON cp.user_id=ja.candidate_id
                   WHERE jp.company_id=? AND jp.id=? ORDER BY ja.applied_at DESC,ja.id DESC""",
                (company_id, job_id),
            ))

    def application_for_company(self, company_id: int, application_id: int) -> dict[str, object] | None:
        """Return a hiring application only when it belongs to this Company."""
        if type(application_id) is not int or application_id <= 0:
            return None
        with _LOCK:
            if not self._role(company_id, "company"):
                return None
            row = self.conn.execute(
                """SELECT ja.id, ja.job_posting_id, ja.candidate_id, ja.status,
                          jp.status AS job_status
                   FROM job_applications ja
                   JOIN job_postings jp ON jp.id=ja.job_posting_id
                   WHERE ja.id=? AND jp.company_id=?""",
                (application_id, company_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def has_released_assessment(self, company_id: int, job_id: int, candidate_id: int) -> bool:
        """Only a result released for this precise job and Candidate qualifies."""
        with _LOCK:
            if not self._role(company_id, "company"):
                return False
            return self.conn.execute(
                """SELECT 1 FROM recruitment_submissions rs
                   JOIN recruitment_invitations ri ON ri.id=rs.invitation_id
                   JOIN exam_sessions es ON es.id=rs.exam_session_id
                   WHERE ri.job_posting_id=? AND ri.company_id=?
                     AND ri.candidate_id=? AND rs.company_id=?
                     AND rs.candidate_id=? AND rs.status='released'
                     AND es.candidate_id=rs.candidate_id
                     AND es.company_id=rs.company_id
                   LIMIT 1""",
                (job_id, company_id, candidate_id, company_id, candidate_id),
            ).fetchone() is not None

    def update_application_status(
        self, company_id: int, application_id: int, status: str
    ) -> bool:
        if (
            not isinstance(status, str) or status not in COMPANY_STATUSES
            or type(application_id) is not int or application_id <= 0
        ):
            return False
        transitions = {
            "submitted": {"reviewing", "rejected"},
            "reviewing": {"shortlisted", "rejected"},
            "shortlisted": {"rejected"},
            "assessment": {"rejected"},
            "interview": {"offered", "rejected"},
        }
        with _LOCK:
            if not self._role(company_id, "company"):
                return False
            row = self.conn.execute(
                """SELECT ja.status FROM job_applications ja
                   JOIN job_postings jp ON jp.id=ja.job_posting_id
                   WHERE ja.id=? AND jp.company_id=?""",
                (application_id, company_id),
            ).fetchone()
            if row is None or status not in transitions.get(row["status"], set()):
                return False
            updated = self.conn.execute(
                """UPDATE job_applications SET status=?,
                   updated_at=datetime('now','localtime')
                   WHERE id=? AND status=? AND EXISTS (
                       SELECT 1 FROM job_postings jp
                       WHERE jp.id=job_applications.job_posting_id AND jp.company_id=?
                   )""",
                (status, application_id, row["status"], company_id),
            )
            self.conn.commit()
            return updated.rowcount == 1

    def get_discoverable(self, candidate_id: int) -> bool | None:
        """Return the persisted privacy choice, or None if no profile exists."""
        with _LOCK:
            if not self._role(candidate_id, "candidate"):
                return None
            row = self.conn.execute(
                "SELECT is_discoverable FROM candidate_profiles WHERE user_id=?",
                (candidate_id,),
            ).fetchone()
            return bool(row["is_discoverable"]) if row is not None else None

    def set_discoverable(self, candidate_id: int, visible: bool) -> bool:
        if type(visible) is not bool:
            return False
        with _LOCK:
            if not self._role(candidate_id, "candidate"):
                return False
            updated = self.conn.execute(
                "UPDATE candidate_profiles SET is_discoverable=? WHERE user_id=?",
                (int(visible), candidate_id),
            )
            self.conn.commit()
            return updated.rowcount == 1

    def discover_candidates(self, company_id: int, search: str = "") -> list[dict[str, object]]:
        """Opt-in only, never expose CV storage paths, contacts or emails."""
        with _LOCK:
            if not self._role(company_id, "company"):
                return []
            needle = f"%{search.strip()}%"
            return self._rows(self.conn.execute(
                """SELECT u.id, u.full_name, cp.headline, cp.bio,
                          cp.years_experience
                   FROM candidate_profiles cp JOIN users u ON u.id=cp.user_id
                   WHERE cp.is_discoverable=1 AND u.role='candidate'
                     AND u.is_active=1 AND COALESCE(u.is_deleted,0)=0
                     AND (u.full_name LIKE ? OR COALESCE(cp.headline,'') LIKE ?)
                   ORDER BY u.full_name,u.id""", (needle, needle),
            ))
