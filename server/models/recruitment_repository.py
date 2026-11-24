"""SQLite persistence for recruitment positions, exams, and submissions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
import json
import math
import sqlite3
from threading import RLock
from typing import Protocol
from uuid import uuid4

from server.database.connection import db
from server.models.certificate_model import CertificateModel
from server.models.recruitment_models import (
    ExamSessionEventModel,
    InterviewEvaluationModel,
    InterviewModel,
)


Record = dict[str, object]
QuestionScores = Sequence[Mapping[str, int | float]]
_DATABASE_LOCK = RLock()


class QuestionOptionInput(Protocol):
    content: str
    is_correct: bool


class RecruitmentRepository:
    """Implements the persistence contracts consumed by both recruitment services.

    Production instances use the application's SQLite singleton. Tests may pass
    a connection to an isolated temporary database.
    """

    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self._connection = connection if connection is not None else db.get_connection()
        self._connection.row_factory = sqlite3.Row

    @contextmanager
    def _transaction(self):
        with _DATABASE_LOCK:
            conn = self._connection
            nested = conn.in_transaction
            savepoint = "recruitment_repository"
            try:
                if nested:
                    conn.execute(f"SAVEPOINT {savepoint}")
                else:
                    conn.execute("BEGIN IMMEDIATE")
                yield conn
            except BaseException:
                if nested:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                else:
                    conn.rollback()
                raise
            else:
                if nested:
                    conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                else:
                    conn.commit()

    @staticmethod
    def _as_record(row: sqlite3.Row | None) -> Record | None:
        return dict(row) if row is not None else None

    def _one(self, sql: str, params: tuple[object, ...] = ()) -> Record | None:
        with _DATABASE_LOCK:
            return self._as_record(self._connection.execute(sql, params).fetchone())

    def _many(self, sql: str, params: tuple[object, ...] = ()) -> list[Record]:
        with _DATABASE_LOCK:
            return [
                dict(row)
                for row in self._connection.execute(sql, params).fetchall()
            ]

    @staticmethod
    def _is_expired(value: object) -> bool:
        if value is None or value == "":
            return False
        if not isinstance(value, str):
            raise sqlite3.IntegrityError("Invalid invitation expiration value.")
        try:
            expiration = datetime.fromisoformat(value)
        except ValueError as exc:
            raise sqlite3.IntegrityError(
                "Invalid invitation expiration value."
            ) from exc
        now = datetime.now(expiration.tzinfo) if expiration.tzinfo else datetime.now()
        return now >= expiration

    def _candidate_session(
        self,
        session_id: int,
        candidate_id: int,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> Record | None:
        sql = """
            SELECT es.id, es.id AS exam_session_id, es.exam_paper_id,
                   es.candidate_id, es.company_id, es.status, es.scheduled_at,
                   es.started_at, es.completed_at, es.created_at,
                   ep.duration_min, ep.title AS exam_title,
                   ri.id AS invitation_id, ri.status AS invitation_status,
                   ri.expires_at, jp.id AS job_posting_id,
                   jp.title AS job_title
            FROM exam_sessions AS es
            JOIN recruitment_invitations AS ri
              ON ri.exam_session_id = es.id
             AND ri.candidate_id = es.candidate_id
             AND ri.company_id = es.company_id
             AND ri.exam_paper_id = es.exam_paper_id
            JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
            JOIN job_postings AS jp
              ON jp.id = ri.job_posting_id AND jp.company_id = ri.company_id
            WHERE es.id = ? AND es.candidate_id = ?
              AND ri.status IN ('accepted','cancelled','expired')
        """
        with _DATABASE_LOCK:
            active_conn = conn or self._connection
            return self._as_record(
                active_conn.execute(sql, (session_id, candidate_id)).fetchone()
            )

    @staticmethod
    def _company_role(conn: sqlite3.Connection, company_id: int) -> bool:
        row = conn.execute(
            "SELECT role FROM users WHERE id = ?", (company_id,)
        ).fetchone()
        return row is not None and row["role"] == "company"

    # RecruitmentModel contract
    def create_job_posting(
        self,
        company_id: int,
        *,
        title: str,
        description: str,
        requirements: str,
        location: str,
        status: str,
    ) -> Record | None:
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO job_postings
                    (company_id, title, description, requirements, location, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (company_id, title, description, requirements, location, status),
            )
            return self._as_record(
                conn.execute(
                    "SELECT * FROM job_postings WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
            )

    def update_job_posting(
        self,
        company_id: int,
        position_id: int,
        *,
        title: str,
        description: str,
        requirements: str,
        location: str,
        status: str,
    ) -> Record | None:
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE job_postings
                SET title = ?, description = ?, requirements = ?, location = ?,
                    status = ?
                WHERE id = ? AND company_id = ?
                """,
                (
                    title, description, requirements, location, status,
                    position_id, company_id,
                ),
            )
            if cursor.rowcount != 1:
                return None
            return self._as_record(
                conn.execute(
                    "SELECT * FROM job_postings WHERE id = ? AND company_id = ?",
                    (position_id, company_id),
                ).fetchone()
            )

    def get_job_posting(
        self, company_id: int, position_id: int
    ) -> Record | None:
        return self._one(
            "SELECT * FROM job_postings WHERE company_id = ? AND id = ?",
            (company_id, position_id),
        )

    def list_job_postings(self, company_id: int) -> list[Record]:
        return self._many(
            """
            SELECT * FROM job_postings
            WHERE company_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (company_id,),
        )

    def list_candidates(
        self, company_id: int, search: str = ""
    ) -> list[Record]:
        with _DATABASE_LOCK:
            if not self._company_role(self._connection, company_id):
                return []
            needle = f"%{search.strip().casefold()}%"
            return [
                dict(row)
                for row in self._connection.execute(
                    """
                    SELECT id, full_name, email
                    FROM users
                    WHERE role = 'candidate'
                      AND is_active = 1
                      AND COALESCE(is_deleted, 0) = 0
                      AND (? = '%%' OR lower(full_name) LIKE lower(?)
                           OR lower(email) LIKE lower(?))
                    ORDER BY full_name, id
                    """,
                    (needle, needle, needle),
                ).fetchall()
            ]

    # ExamModel contract
    def create_exam(
        self,
        company_id: int,
        *,
        title: str,
        description: str,
        duration_min: int,
        total_points: float,
    ) -> Record | None:
        with self._transaction() as conn:
            if not self._company_role(conn, company_id):
                return None
            cursor = conn.execute(
                """
                INSERT INTO exam_papers
                    (title, description, created_by, duration_min,
                     total_points, is_published)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (title, description, company_id, duration_min, total_points),
            )
            return self._as_record(
                conn.execute(
                    "SELECT * FROM exam_papers WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
            )

    def get_exam_for_company(
        self, company_id: int, exam_id: int
    ) -> Record | None:
        return self._one(
            "SELECT * FROM exam_papers WHERE id = ? AND created_by = ?",
            (exam_id, company_id),
        )

    def list_exams_for_company(self, company_id: int) -> list[Record]:
        return self._many(
            """
            SELECT ep.*, COUNT(epq.question_id) AS question_count
            FROM exam_papers AS ep
            LEFT JOIN exam_paper_questions AS epq ON epq.exam_paper_id = ep.id
            WHERE ep.created_by = ?
            GROUP BY ep.id
            ORDER BY ep.created_at DESC, ep.id DESC
            """,
            (company_id,),
        )

    def add_question(
        self,
        company_id: int,
        exam_id: int,
        *,
        title: str,
        content: str,
        difficulty: str,
        points: float,
        options: Sequence[QuestionOptionInput] = (),
        expert_id: int | None = None,
        question_type: str = "multiple_choice",
        test_cases: Sequence[Mapping[str, object]] = (),
        reference_answer: str | None = None,
    ) -> Record | None:
        if expert_id is None:
            raise sqlite3.IntegrityError(
                "Question ownership is unresolved: provide the active contracted "
                "expert's user id as expert_id."
            )
        if not isinstance(question_type, str) or question_type not in {
            "multiple_choice", "coding", "essay"
        }:
            raise sqlite3.IntegrityError("Unsupported question type.")
        option_data: list[tuple[str, bool]] = []
        stored_test_cases: str | None = None
        if question_type == "multiple_choice":
            if any(
                not isinstance(option.content, str)
                or not isinstance(option.is_correct, bool)
                for option in options
            ):
                raise sqlite3.IntegrityError("Question options are invalid.")
            option_data = [
                (option.content.strip(), option.is_correct) for option in options
            ]
            if (
                len(option_data) < 2
                or any(not content for content, _ in option_data)
                or sum(is_correct for _, is_correct in option_data) != 1
            ):
                raise sqlite3.IntegrityError("Question options are invalid.")
        elif options:
            raise sqlite3.IntegrityError(
                "Only multiple-choice questions may include options."
            )
        if question_type == "coding":
            normalized_cases = self._normalize_coding_test_cases(test_cases)
            if not normalized_cases:
                raise sqlite3.IntegrityError(
                    "Coding questions require at least one test case."
                )
            stored_test_cases = json.dumps(
                normalized_cases, ensure_ascii=False, separators=(",", ":")
            )
        elif test_cases:
            raise sqlite3.IntegrityError(
                "Test cases are only supported for coding questions."
            )
        if reference_answer is not None and not isinstance(reference_answer, str):
            raise sqlite3.IntegrityError("Reference answer must be text.")

        with self._transaction() as conn:
            paper = conn.execute(
                """
                SELECT id, is_published FROM exam_papers
                WHERE id = ? AND created_by = ?
                """,
                (exam_id, company_id),
            ).fetchone()
            if paper is None or paper["is_published"]:
                return None

            expert = conn.execute(
                """
                SELECT 1
                FROM users AS u
                JOIN company_expert_contracts AS c ON c.expert_id = u.id
                WHERE u.id = ? AND u.role = 'expert'
                  AND c.company_id = ? AND c.status = 'active'
                LIMIT 1
                """,
                (expert_id, company_id),
            ).fetchone()
            if expert is None:
                raise sqlite3.IntegrityError(
                    "Question owner must be an expert with an active company contract."
                )

            question_cursor = conn.execute(
                """
                INSERT INTO question_bank
                    (expert_id, question_type, title, content, difficulty, points,
                     reference_answer, test_cases, is_published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    expert_id, question_type, title, content, difficulty, points,
                    reference_answer, stored_test_cases,
                ),
            )
            question_id = question_cursor.lastrowid
            sort_order = conn.execute(
                """
                SELECT COALESCE(MAX(sort_order), 0) + 1
                FROM exam_paper_questions WHERE exam_paper_id = ?
                """,
                (exam_id,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO exam_paper_questions
                    (exam_paper_id, question_id, sort_order, points)
                VALUES (?, ?, ?, ?)
                """,
                (exam_id, question_id, sort_order, points),
            )
            for index, (option_content, is_correct) in enumerate(option_data, 1):
                conn.execute(
                    """
                    INSERT INTO question_options
                        (question_id, content, is_correct, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (question_id, option_content, int(is_correct), index),
                )

            question = self._as_record(
                conn.execute(
                    """
                    SELECT id, expert_id, title, content, difficulty, points,
                           question_type
                    FROM question_bank WHERE id = ?
                    """,
                    (question_id,),
                ).fetchone()
            )
            if question is None:
                return None
            question["options"] = [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "is_correct": bool(row["is_correct"]),
                }
                for row in conn.execute(
                    """
                    SELECT id, content, is_correct
                    FROM question_options WHERE question_id = ?
                    ORDER BY sort_order, id
                    """,
                    (question_id,),
                ).fetchall()
            ]
            return question

    @staticmethod
    def _normalize_coding_test_cases(
        test_cases: Sequence[Mapping[str, object]],
    ) -> list[dict[str, object]]:
        if isinstance(test_cases, (str, bytes)):
            raise sqlite3.IntegrityError("Coding test cases are invalid.")
        normalized: list[dict[str, object]] = []
        for case in test_cases:
            if not isinstance(case, Mapping):
                raise sqlite3.IntegrityError("Coding test cases are invalid.")
            input_value = case.get("input")
            expected_output = case.get("expected_output")
            is_hidden = case.get("is_hidden", False)
            if (
                not isinstance(input_value, str)
                or not isinstance(expected_output, str)
                or not isinstance(is_hidden, bool)
            ):
                raise sqlite3.IntegrityError("Coding test cases are invalid.")
            normalized.append(
                {
                    "input": input_value,
                    "expected_output": expected_output,
                    "is_hidden": is_hidden,
                }
            )
        return normalized

    def list_coding_test_cases(
        self, expert_id: int, question_id: int
    ) -> list[Record] | None:
        question = self._one(
            """
            SELECT test_cases FROM question_bank
            WHERE id = ? AND expert_id = ? AND question_type = 'coding'
            """,
            (question_id, expert_id),
        )
        if question is None:
            return None
        raw_test_cases = question["test_cases"]
        if not isinstance(raw_test_cases, str):
            return []
        try:
            test_cases = json.loads(raw_test_cases)
        except json.JSONDecodeError as exc:
            raise sqlite3.IntegrityError("Stored coding test cases are invalid.") from exc
        if not isinstance(test_cases, list):
            raise sqlite3.IntegrityError("Stored coding test cases are invalid.")
        if any(not isinstance(case, Mapping) for case in test_cases):
            raise sqlite3.IntegrityError("Stored coding test cases are invalid.")
        return [dict(case) for case in test_cases]

    def get_user_role(self, user_id: int) -> str | None:
        row = self._one("SELECT role FROM users WHERE id = ?", (user_id,))
        role = row.get("role") if row else None
        return role if isinstance(role, str) else None

    def list_contracted_experts(self, company_id: int) -> list[Record]:
        with _DATABASE_LOCK:
            if not self._company_role(self._connection, company_id):
                return []
            return [
                dict(row)
                for row in self._connection.execute(
                    """
                    SELECT u.id, u.full_name, u.email
                    FROM users AS u
                    JOIN company_expert_contracts AS c ON c.expert_id = u.id
                    WHERE c.company_id = ? AND c.status = 'active'
                      AND u.role = 'expert' AND u.is_active = 1
                      AND COALESCE(u.is_deleted, 0) = 0
                    ORDER BY u.full_name, u.id
                    """,
                    (company_id,),
                ).fetchall()
            ]

    def publish_exam(self, company_id: int, exam_id: int) -> Record | None:
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE exam_papers SET is_published = 1
                WHERE id = ? AND created_by = ?
                """,
                (exam_id, company_id),
            )
            if cursor.rowcount != 1:
                return None
            return self._as_record(
                conn.execute(
                    "SELECT * FROM exam_papers WHERE id = ? AND created_by = ?",
                    (exam_id, company_id),
                ).fetchone()
            )

    def get_candidate_invitation(
        self, invitation_id: int, candidate_id: int
    ) -> Record | None:
        return self._one(
            """
            SELECT ri.*, COALESCE(cp.company_name, company.full_name) AS company_name,
                   jp.title AS position_title, ep.title AS exam_title,
                   ep.duration_min, es.status AS session_status,
                   es.scheduled_at, es.started_at
            FROM recruitment_invitations AS ri
            JOIN users AS company ON company.id = ri.company_id
            LEFT JOIN company_profiles AS cp ON cp.user_id = ri.company_id
            JOIN job_postings AS jp ON jp.id = ri.job_posting_id
            JOIN exam_papers AS ep ON ep.id = ri.exam_paper_id
            LEFT JOIN exam_sessions AS es ON es.id = ri.exam_session_id
            WHERE ri.id = ? AND ri.candidate_id = ?
            """,
            (invitation_id, candidate_id),
        )

    def accept_candidate_invitation(
        self, invitation_id: int, candidate_id: int
    ) -> Record | None:
        with self._transaction() as conn:
            invitation = conn.execute(
                """
                SELECT * FROM recruitment_invitations
                WHERE id = ? AND candidate_id = ?
                """,
                (invitation_id, candidate_id),
            ).fetchone()
            if invitation is None:
                return None
            if invitation["status"] != "pending":
                return self.get_candidate_invitation(invitation_id, candidate_id)
            if self._is_expired(invitation["expires_at"]):
                expired = conn.execute(
                    """
                    UPDATE recruitment_invitations
                    SET status = 'expired', responded_at = datetime('now','localtime')
                    WHERE id = ? AND candidate_id = ? AND status = 'pending'
                    """,
                    (invitation_id, candidate_id),
                )
                if expired.rowcount != 1:
                    raise sqlite3.IntegrityError(
                        "Pending invitation changed while it was expiring."
                    )
                return self.get_candidate_invitation(invitation_id, candidate_id)

            paper = conn.execute(
                """
                SELECT duration_min, total_points
                FROM exam_papers WHERE id = ?
                """,
                (invitation["exam_paper_id"],),
            ).fetchone()
            if paper is None:
                return None
            session_cursor = conn.execute(
                """
                INSERT INTO exam_sessions
                    (exam_paper_id, candidate_id, company_id, status,
                     scheduled_at, max_score)
                VALUES (?, ?, ?, 'scheduled', datetime('now','localtime'), ?)
                """,
                (
                    invitation["exam_paper_id"],
                    candidate_id,
                    invitation["company_id"],
                    paper["total_points"],
                ),
            )
            session_id = session_cursor.lastrowid
            accepted = conn.execute(
                """
                UPDATE recruitment_invitations
                SET status = 'accepted', exam_session_id = ?,
                    responded_at = datetime('now','localtime')
                WHERE id = ? AND candidate_id = ? AND status = 'pending'
                """,
                (session_id, invitation_id, candidate_id),
            )
            if accepted.rowcount != 1:
                raise sqlite3.IntegrityError(
                    "Pending invitation changed while it was being accepted."
                )
            return self.get_candidate_invitation(invitation_id, candidate_id)

    def expire_candidate_invitation(
        self, invitation_id: int, candidate_id: int
    ) -> None:
        with self._transaction() as conn:
            row = conn.execute(
                """
                SELECT expires_at FROM recruitment_invitations
                WHERE id = ? AND candidate_id = ? AND status = 'pending'
                """,
                (invitation_id, candidate_id),
            ).fetchone()
            if row is None or not self._is_expired(row["expires_at"]):
                return
            conn.execute(
                """
                UPDATE recruitment_invitations
                SET status = 'expired', responded_at = datetime('now','localtime')
                WHERE id = ? AND candidate_id = ? AND status = 'pending'
                """,
                (invitation_id, candidate_id),
            )

    def invite_candidate(
        self,
        company_id: int,
        job_posting_id: int,
        exam_id: int,
        candidate_id: int,
        expires_at: str | None,
    ) -> Record | None:
        with self._transaction() as conn:
            if not self._company_role(conn, company_id):
                return None
            eligible = conn.execute(
                """
                SELECT 1
                FROM job_postings AS jp
                JOIN exam_papers AS ep ON ep.id = ?
                JOIN users AS candidate ON candidate.id = ?
                WHERE jp.id = ? AND jp.company_id = ? AND jp.status = 'published'
                  AND ep.created_by = ? AND ep.is_published = 1
                  AND candidate.role = 'candidate'
                """,
                (exam_id, candidate_id, job_posting_id, company_id, company_id),
            ).fetchone()
            if eligible is None:
                return None

            existing = conn.execute(
                """
                SELECT * FROM recruitment_invitations
                WHERE job_posting_id = ? AND exam_paper_id = ?
                  AND candidate_id = ? AND company_id = ?
                  AND status IN ('pending','accepted')
                ORDER BY id DESC LIMIT 1
                """,
                (job_posting_id, exam_id, candidate_id, company_id),
            ).fetchone()
            if existing is not None:
                if (
                    existing["status"] != "pending"
                    or not self._is_expired(existing["expires_at"])
                ):
                    return self._as_record(existing)
                conn.execute(
                    """
                    UPDATE recruitment_invitations
                    SET status = 'expired', responded_at = datetime('now','localtime')
                    WHERE id = ? AND status = 'pending'
                    """,
                    (existing["id"],),
                )

            cursor = conn.execute(
                """
                INSERT INTO recruitment_invitations
                    (job_posting_id, company_id, candidate_id, exam_paper_id,
                     expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_posting_id, company_id, candidate_id, exam_id, expires_at),
            )
            return self._as_record(
                conn.execute(
                    "SELECT * FROM recruitment_invitations WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
            )

    def list_company_submissions(
        self, company_id: int, exam_id: int
    ) -> list[Record]:
        return self._many(
            """
            SELECT rs.id, rs.invitation_id, rs.exam_session_id, rs.candidate_id,
                   rs.company_id, rs.exam_paper_id, rs.status,
                   rs.submitted_at, rs.graded_at, rs.released_at,
                   es.total_score AS score, es.max_score,
                   u.full_name AS candidate_name, u.email AS candidate_email,
                   jp.title AS job_title, ep.title AS exam_title
            FROM recruitment_submissions AS rs
            JOIN exam_sessions AS es ON es.id = rs.exam_session_id
            JOIN exam_papers AS ep ON ep.id = rs.exam_paper_id
            JOIN recruitment_invitations AS ri ON ri.id = rs.invitation_id
            JOIN job_postings AS jp ON jp.id = ri.job_posting_id
            JOIN users AS u ON u.id = rs.candidate_id
            WHERE rs.company_id = ? AND ep.created_by = ? AND ep.id = ?
            ORDER BY rs.submitted_at DESC, rs.id DESC
            """,
            (company_id, company_id, exam_id),
        )

    def release_results(self, company_id: int, exam_id: int) -> Record | None:
        with self._transaction() as conn:
            exam = conn.execute(
                "SELECT * FROM exam_papers WHERE id = ? AND created_by = ?",
                (exam_id, company_id),
            ).fetchone()
            if exam is None:
                return None
            submissions = conn.execute(
                """
                SELECT rs.id FROM recruitment_submissions AS rs
                JOIN exam_sessions AS es ON es.id = rs.exam_session_id
                WHERE rs.company_id = ? AND rs.exam_paper_id = ?
                  AND es.company_id = ? AND rs.status = 'graded'
                """,
                (company_id, exam_id, company_id),
            ).fetchall()
            for row in submissions:
                conn.execute(
                    """
                    UPDATE recruitment_submissions
                    SET status = 'released', released_at = datetime('now','localtime')
                    WHERE id = ? AND status = 'graded'
                    """,
                    (row["id"],),
                )
            result = dict(exam)
            result["status"] = "released"
            result["released_count"] = len(submissions)
            return result

    def list_candidate_invitations(self, candidate_id: int) -> list[Record]:
        return self._many(
            """
            SELECT ri.id, ri.job_posting_id, ri.company_id, ri.candidate_id,
                   ri.exam_paper_id, ri.exam_session_id, ri.status,
                   ri.invited_at, ri.responded_at, ri.expires_at,
                   COALESCE(cp.company_name, company.full_name) AS company_name,
                   jp.title AS position_title, ep.title AS exam_title,
                   ep.duration_min, es.status AS session_status,
                   es.scheduled_at, es.started_at
            FROM recruitment_invitations AS ri
            JOIN job_postings AS jp ON jp.id = ri.job_posting_id
            JOIN exam_papers AS ep ON ep.id = ri.exam_paper_id
            JOIN users AS company ON company.id = ri.company_id
            LEFT JOIN company_profiles AS cp ON cp.user_id = ri.company_id
            LEFT JOIN exam_sessions AS es ON es.id = ri.exam_session_id
            WHERE ri.candidate_id = ?
            ORDER BY ri.invited_at DESC, ri.id DESC
            """,
            (candidate_id,),
        )

    def get_candidate_session(
        self, session_id: int, candidate_id: int
    ) -> Record | None:
        return self._candidate_session(session_id, candidate_id)

    def start_session_once(
        self, session_id: int, candidate_id: int
    ) -> tuple[bool, Record | None]:
        with self._transaction() as conn:
            session = self._candidate_session(session_id, candidate_id, conn=conn)
            if session is None or session["status"] != "scheduled":
                return False, session
            cursor = conn.execute(
                """
                UPDATE exam_sessions SET status = 'in_progress',
                    started_at = datetime('now','localtime')
                WHERE id = ? AND candidate_id = ? AND status = 'scheduled'
                  AND EXISTS (
                      SELECT 1 FROM recruitment_invitations AS ri
                      WHERE ri.exam_session_id = exam_sessions.id
                        AND ri.candidate_id = ? AND ri.status = 'accepted'
                  )
                """,
                (session_id, candidate_id, candidate_id),
            )
            if cursor.rowcount != 1:
                return False, self._candidate_session(
                    session_id, candidate_id, conn=conn
                )
            return True, self._candidate_session(session_id, candidate_id, conn=conn)

    def list_candidate_questions(
        self, session_id: int, candidate_id: int
    ) -> list[Record]:
        session = self._candidate_session(session_id, candidate_id)
        if session is None or session["status"] != "in_progress":
            return []
        with _DATABASE_LOCK:
            rows = self._connection.execute(
                """
                SELECT epq.exam_paper_id, qb.id, qb.skill_id, qb.title, qb.content,
                       qb.question_type, qb.difficulty,
                       COALESCE(epq.points, qb.points) AS points, epq.sort_order,
                       ea.selected_option_id, ea.answer_text, ea.answer_code
                FROM exam_paper_questions AS epq
                JOIN question_bank AS qb ON qb.id = epq.question_id
                LEFT JOIN exam_answers AS ea
                  ON ea.exam_session_id = ? AND ea.question_id = qb.id
                WHERE epq.exam_paper_id = ?
                ORDER BY epq.sort_order, epq.id
                """,
                (session_id, session["exam_paper_id"]),
            ).fetchall()
            questions: list[Record] = []
            for row in rows:
                question = dict(row)
                question["options"] = [
                    dict(option)
                    for option in self._connection.execute(
                        """
                        SELECT id, content
                        FROM question_options WHERE question_id = ?
                        ORDER BY sort_order, id
                        """,
                        (question["id"],),
                    ).fetchall()
                ]
                questions.append(question)
            return questions

    def save_candidate_answer(
        self,
        session_id: int,
        candidate_id: int,
        question_id: int,
        selected_option_id: int,
    ) -> Record | None:
        with self._transaction() as conn:
            session = self._candidate_session(session_id, candidate_id, conn=conn)
            if session is None or session["status"] != "in_progress":
                return None
            valid_option = conn.execute(
                """
                SELECT 1
                FROM exam_paper_questions AS epq
                JOIN question_options AS qo ON qo.question_id = epq.question_id
                WHERE epq.exam_paper_id = ? AND epq.question_id = ?
                  AND qo.id = ?
                """,
                (session["exam_paper_id"], question_id, selected_option_id),
            ).fetchone()
            if valid_option is None:
                return None
            conn.execute(
                """
                INSERT INTO exam_answers
                    (exam_session_id, question_id, selected_option_id)
                VALUES (?, ?, ?)
                ON CONFLICT(exam_session_id, question_id)
                DO UPDATE SET selected_option_id = excluded.selected_option_id
                """,
                (session_id, question_id, selected_option_id),
            )
            return self._as_record(
                conn.execute(
                    """
                    SELECT id, exam_session_id, question_id, selected_option_id,
                           answer_text, answer_code
                    FROM exam_answers
                    WHERE exam_session_id = ? AND question_id = ?
                    """,
                    (session_id, question_id),
                ).fetchone()
            )

    def save_candidate_written_answer(
        self,
        session_id: int,
        candidate_id: int,
        question_id: int,
        answer: str,
    ) -> Record | None:
        if not isinstance(answer, str):
            raise sqlite3.IntegrityError("Written exam answers must be text.")
        with self._transaction() as conn:
            session = self._candidate_session(session_id, candidate_id, conn=conn)
            if session is None or session["status"] != "in_progress":
                return None
            question = conn.execute(
                """
                SELECT qb.question_type
                FROM exam_paper_questions AS epq
                JOIN question_bank AS qb ON qb.id = epq.question_id
                WHERE epq.exam_paper_id = ? AND qb.id = ?
                """,
                (session["exam_paper_id"], question_id),
            ).fetchone()
            if question is None or question["question_type"] not in {"essay", "coding"}:
                return None
            answer_column = (
                "answer_text"
                if question["question_type"] == "essay"
                else "answer_code"
            )
            conn.execute(
                f"""
                INSERT INTO exam_answers
                    (exam_session_id, question_id, {answer_column})
                VALUES (?, ?, ?)
                ON CONFLICT(exam_session_id, question_id)
                DO UPDATE SET {answer_column} = excluded.{answer_column}
                """,
                (session_id, question_id, answer),
            )
            return self._as_record(
                conn.execute(
                    """
                    SELECT id, exam_session_id, question_id, answer_text, answer_code
                    FROM exam_answers
                    WHERE exam_session_id = ? AND question_id = ?
                    """,
                    (session_id, question_id),
                ).fetchone()
            )

    def get_grading_questions(self, session_id: int) -> list[Record]:
        session = self._one(
            """
            SELECT es.exam_paper_id
            FROM exam_sessions AS es
            JOIN recruitment_invitations AS ri
              ON ri.exam_session_id = es.id AND ri.status = 'accepted'
            WHERE es.id = ? AND es.status = 'in_progress'
            """,
            (session_id,),
        )
        if session is None:
            return []
        with _DATABASE_LOCK:
            rows = self._connection.execute(
                """
                SELECT epq.question_id AS id,
                       COALESCE(epq.points, qb.points) AS points
                FROM exam_paper_questions AS epq
                JOIN question_bank AS qb ON qb.id = epq.question_id
                WHERE epq.exam_paper_id = ?
                ORDER BY epq.sort_order, epq.id
                """,
                (session["exam_paper_id"],),
            ).fetchall()
            questions: list[Record] = []
            for row in rows:
                question = dict(row)
                question["options"] = [
                    dict(option)
                    for option in self._connection.execute(
                        """
                        SELECT id, is_correct FROM question_options
                        WHERE question_id = ? ORDER BY sort_order, id
                        """,
                        (question["id"],),
                    ).fetchall()
                ]
                questions.append(question)
            return questions

    def get_candidate_answers(
        self, session_id: int, candidate_id: int
    ) -> list[Record]:
        session = self._candidate_session(session_id, candidate_id)
        if session is None or session["status"] != "in_progress":
            return []
        return self._many(
            """
            SELECT ea.question_id, ea.selected_option_id,
                   ea.answer_text, ea.answer_code
            FROM exam_answers AS ea
            WHERE ea.exam_session_id = ?
            ORDER BY ea.question_id
            """,
            (session_id,),
        )

    def complete_session_once(
        self,
        session_id: int,
        candidate_id: int,
        *,
        score: float,
        max_score: float,
        question_scores: QuestionScores,
    ) -> tuple[bool, Record | None]:
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or isinstance(max_score, bool)
            or not isinstance(max_score, (int, float))
            or not math.isfinite(score)
            or not math.isfinite(max_score)
            or score < 0
            or max_score <= 0
            or score > max_score
        ):
            raise sqlite3.IntegrityError("Invalid exam score.")
        score_by_question: dict[int, tuple[float, float]] = {}
        for item in question_scores:
            if not isinstance(item, Mapping):
                raise sqlite3.IntegrityError("Invalid per-question grade data.")
            question_id = item.get("question_id")
            question_score = item.get("score")
            question_max = item.get("max_score")
            if (
                isinstance(question_id, bool)
                or not isinstance(question_id, int)
                or question_id <= 0
                or isinstance(question_score, bool)
                or not isinstance(question_score, (int, float))
                or isinstance(question_max, bool)
                or not isinstance(question_max, (int, float))
                or not math.isfinite(question_score)
                or not math.isfinite(question_max)
                or question_score < 0
                or question_max <= 0
                or question_score > question_max
                or question_id in score_by_question
            ):
                raise sqlite3.IntegrityError("Invalid per-question grade data.")
            score_by_question[question_id] = (
                float(question_score),
                float(question_max),
            )
        if (
            not score_by_question
            or not math.isclose(
                sum(value[0] for value in score_by_question.values()),
                score,
            )
            or not math.isclose(
                sum(value[1] for value in score_by_question.values()),
                max_score,
            )
        ):
            raise sqlite3.IntegrityError("Exam grades do not match the session total.")

        with self._transaction() as conn:
            session = conn.execute(
                """
                SELECT es.id, es.exam_paper_id, es.candidate_id, es.company_id,
                       es.status, ri.id AS invitation_id
                FROM exam_sessions AS es
                JOIN recruitment_invitations AS ri
                  ON ri.exam_session_id = es.id
                 AND ri.candidate_id = es.candidate_id
                 AND ri.company_id = es.company_id
                 AND ri.exam_paper_id = es.exam_paper_id
                WHERE es.id = ? AND es.candidate_id = ?
                  AND es.status = 'in_progress' AND ri.status = 'accepted'
                """,
                (session_id, candidate_id),
            ).fetchone()
            if session is None:
                return False, None

            paper_question_ids = {
                row["question_id"]
                for row in conn.execute(
                    """
                    SELECT question_id FROM exam_paper_questions
                    WHERE exam_paper_id = ?
                    """,
                    (session["exam_paper_id"],),
                ).fetchall()
            }
            if paper_question_ids != set(score_by_question):
                raise sqlite3.IntegrityError(
                    "Per-question grades do not match the exam paper."
                )

            answer_rows = conn.execute(
                """
                SELECT id, question_id, selected_option_id FROM exam_answers
                WHERE exam_session_id = ?
                """,
                (session_id,),
            ).fetchall()
            answer_by_question = {
                answer["question_id"]: answer for answer in answer_rows
            }
            expected_score = 0.0
            for question_row in conn.execute(
                """
                SELECT epq.question_id, COALESCE(epq.points, qb.points) AS points
                FROM exam_paper_questions AS epq
                JOIN question_bank AS qb ON qb.id = epq.question_id
                WHERE epq.exam_paper_id = ?
                """,
                (session["exam_paper_id"],),
            ).fetchall():
                options = conn.execute(
                    """
                    SELECT id, is_correct FROM question_options
                    WHERE question_id = ?
                    """,
                    (question_row["question_id"],),
                ).fetchall()
                correct_options = [
                    option["id"] for option in options if option["is_correct"] == 1
                ]
                if len(correct_options) != 1 or len(options) < 2:
                    raise sqlite3.IntegrityError(
                        "Exam question must have exactly one correct option."
                    )
                answer = answer_by_question.get(question_row["question_id"])
                selected_option_id = (
                    answer["selected_option_id"] if answer is not None else None
                )
                points = float(question_row["points"])
                question_score = (
                    points if selected_option_id == correct_options[0] else 0.0
                )
                stored_score = score_by_question[question_row["question_id"]]
                if (
                    not math.isclose(stored_score[0], question_score)
                    or not math.isclose(stored_score[1], points)
                ):
                    raise sqlite3.IntegrityError(
                        "Exam grades do not match persisted candidate answers."
                    )
                expected_score += question_score
            if not math.isclose(expected_score, score):
                raise sqlite3.IntegrityError(
                    "Exam score does not match persisted candidate answers."
                )

            for answer in answer_rows:
                grade = score_by_question.get(answer["question_id"])
                if grade is None:
                    raise sqlite3.IntegrityError(
                        "Saved answer does not belong to the exam paper."
                    )
                answer_update = conn.execute(
                    """
                    UPDATE exam_answers
                    SET score = ?, max_score = ?, is_graded = 1,
                        graded_at = datetime('now','localtime')
                    WHERE id = ? AND exam_session_id = ?
                    """,
                    (grade[0], grade[1], answer["id"], session_id),
                )
                if answer_update.rowcount != 1:
                    raise sqlite3.IntegrityError(
                        "Saved exam answer changed while grading."
                    )

            completed = conn.execute(
                """
                UPDATE exam_sessions
                SET status = 'completed', total_score = ?, max_score = ?,
                    completed_at = datetime('now','localtime')
                WHERE id = ? AND candidate_id = ? AND status = 'in_progress'
                """,
                (score, max_score, session_id, candidate_id),
            )
            if completed.rowcount != 1:
                raise sqlite3.IntegrityError(
                    "Exam session changed while it was being submitted."
                )

            cursor = conn.execute(
                """
                INSERT INTO recruitment_submissions
                    (invitation_id, exam_session_id, candidate_id,
                     company_id, exam_paper_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["invitation_id"], session_id, candidate_id,
                    session["company_id"], session["exam_paper_id"],
                ),
            )
            submission_id = cursor.lastrowid
            grading = conn.execute(
                """
                UPDATE recruitment_submissions SET status = 'grading'
                WHERE id = ? AND status = 'submitted'
                """,
                (submission_id,),
            )
            if grading.rowcount != 1:
                raise sqlite3.IntegrityError(
                    "Submission could not enter grading state."
                )
            graded = conn.execute(
                """
                UPDATE recruitment_submissions
                SET status = 'graded', graded_at = datetime('now','localtime')
                WHERE id = ? AND status = 'grading'
                """,
                (submission_id,),
            )
            if graded.rowcount != 1:
                raise sqlite3.IntegrityError(
                    "Submission could not enter graded state."
                )
            submission = self._as_record(
                conn.execute(
                    "SELECT * FROM recruitment_submissions WHERE id = ?",
                    (submission_id,),
                ).fetchone()
            )
            if submission is not None:
                submission["score"] = score
                submission["max_score"] = max_score
            return True, submission

    def get_candidate_result(
        self, session_id: int, candidate_id: int
    ) -> Record | None:
        return self._one(
            """
            SELECT es.id AS exam_session_id, es.total_score AS score,
                   es.max_score, rs.graded_at, rs.released_at,
                   rs.status AS submission_status
            FROM exam_sessions AS es
            JOIN recruitment_submissions AS rs ON rs.exam_session_id = es.id
            WHERE es.id = ? AND es.status = 'completed'
              AND rs.candidate_id = ? AND rs.status = 'released'
            """,
            (session_id, candidate_id),
        )

    def get_candidate_submission(
        self, session_id: int, candidate_id: int
    ) -> Record | None:
        return self._one(
            """
            SELECT id, invitation_id, exam_session_id, candidate_id, company_id,
                   exam_paper_id, status, submitted_at, graded_at, released_at
            FROM recruitment_submissions
            WHERE exam_session_id = ? AND candidate_id = ?
            """,
            (session_id, candidate_id),
        )

    def record_exam_session_event(
        self,
        session_id: int,
        candidate_id: int,
        event_type: str,
        *,
        is_violation: bool = False,
        details: Mapping[str, object] | None = None,
        occurred_at: str | None = None,
    ) -> ExamSessionEventModel:
        if not isinstance(event_type, str) or not event_type.strip():
            raise sqlite3.IntegrityError("Exam event type is required.")
        if not isinstance(is_violation, bool):
            raise sqlite3.IntegrityError("Exam event violation flag is invalid.")
        if details is not None and not isinstance(details, Mapping):
            raise sqlite3.IntegrityError("Exam event details must be an object.")
        if details is not None and any(not isinstance(key, str) for key in details):
            raise sqlite3.IntegrityError("Exam event detail keys must be text.")
        if occurred_at is not None:
            if not isinstance(occurred_at, str):
                raise sqlite3.IntegrityError("Exam event time is invalid.")
            try:
                datetime.fromisoformat(occurred_at)
            except ValueError as exc:
                raise sqlite3.IntegrityError("Exam event time is invalid.") from exc
        details_json = (
            json.dumps(dict(details), ensure_ascii=False, separators=(",", ":"))
            if details is not None
            else None
        )
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO exam_session_events
                    (exam_session_id, candidate_id, event_type, is_violation,
                     details_json, occurred_at)
                VALUES (?, ?, ?, ?, ?, COALESCE(?, datetime('now','localtime')))
                """,
                (
                    session_id,
                    candidate_id,
                    event_type.strip(),
                    int(is_violation),
                    details_json,
                    occurred_at,
                ),
            )
            row = conn.execute(
                "SELECT * FROM exam_session_events WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return ExamSessionEventModel.from_row(row)

    def list_exam_session_events(
        self,
        session_id: int,
        candidate_id: int,
        *,
        violations_only: bool = False,
    ) -> list[ExamSessionEventModel]:
        with _DATABASE_LOCK:
            rows = self._connection.execute(
                """
                SELECT ese.*
                FROM exam_session_events AS ese
                JOIN exam_sessions AS es ON es.id = ese.exam_session_id
                WHERE ese.exam_session_id = ? AND es.candidate_id = ?
                  AND (? = 0 OR ese.is_violation = 1)
                ORDER BY ese.occurred_at, ese.id
                """,
                (session_id, candidate_id, int(violations_only)),
            ).fetchall()
            return [ExamSessionEventModel.from_row(row) for row in rows]

    def schedule_interview(
        self,
        company_id: int,
        candidate_id: int,
        *,
        title: str,
        scheduled_at: str,
        duration_min: int = 60,
        description: str | None = None,
        meeting_url: str | None = None,
        interviewer_ids: Sequence[int] = (),
    ) -> InterviewModel | None:
        if not isinstance(title, str) or not title.strip():
            raise sqlite3.IntegrityError("Interview title is required.")
        if not isinstance(scheduled_at, str):
            raise sqlite3.IntegrityError("Interview time is required.")
        try:
            datetime.fromisoformat(scheduled_at)
        except ValueError as exc:
            raise sqlite3.IntegrityError("Interview time is invalid.") from exc
        if (
            isinstance(duration_min, bool)
            or not isinstance(duration_min, int)
            or duration_min <= 0
        ):
            raise sqlite3.IntegrityError("Interview duration must be positive.")
        if isinstance(interviewer_ids, (str, bytes)):
            raise sqlite3.IntegrityError("Interviewers are invalid.")
        requested_interviewers = list(interviewer_ids)
        if any(
            isinstance(expert_id, bool)
            or not isinstance(expert_id, int)
            or expert_id <= 0
            for expert_id in requested_interviewers
        ):
            raise sqlite3.IntegrityError("Interviewers are invalid.")
        unique_interviewers = list(dict.fromkeys(requested_interviewers))
        with self._transaction() as conn:
            roles = conn.execute(
                """
                SELECT id, role FROM users
                WHERE id IN (?, ?)
                """,
                (company_id, candidate_id),
            ).fetchall()
            role_by_id = {row["id"]: row["role"] for row in roles}
            if (
                role_by_id.get(company_id) != "company"
                or role_by_id.get(candidate_id) != "candidate"
            ):
                return None
            for expert_id in unique_interviewers:
                eligible = conn.execute(
                    """
                    SELECT 1
                    FROM users AS u
                    JOIN company_expert_contracts AS c ON c.expert_id = u.id
                    WHERE u.id = ? AND u.role = 'expert'
                      AND c.company_id = ? AND c.status = 'active'
                    LIMIT 1
                    """,
                    (expert_id, company_id),
                ).fetchone()
                if eligible is None:
                    return None
            cursor = conn.execute(
                """
                INSERT INTO interviews
                    (candidate_id, company_id, title, description, scheduled_at,
                     duration_min, meeting_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    company_id,
                    title.strip(),
                    description,
                    scheduled_at,
                    duration_min,
                    meeting_url,
                ),
            )
            interview_id = cursor.lastrowid
            conn.executemany(
                """
                INSERT INTO interview_participants
                    (interview_id, expert_id, role)
                VALUES (?, ?, 'interviewer')
                """,
                ((interview_id, expert_id) for expert_id in unique_interviewers),
            )
            row = conn.execute(
                "SELECT * FROM interviews WHERE id = ?", (interview_id,)
            ).fetchone()
            return InterviewModel.from_row(row)

    def list_company_interviews(self, company_id: int) -> list[InterviewModel]:
        with _DATABASE_LOCK:
            rows = self._connection.execute(
                """
                SELECT * FROM interviews
                WHERE company_id = ?
                ORDER BY scheduled_at, id
                """,
                (company_id,),
            ).fetchall()
            return [InterviewModel.from_row(row) for row in rows]

    def list_candidate_interviews(self, candidate_id: int) -> list[InterviewModel]:
        with _DATABASE_LOCK:
            rows = self._connection.execute(
                """
                SELECT * FROM interviews
                WHERE candidate_id = ?
                ORDER BY scheduled_at, id
                """,
                (candidate_id,),
            ).fetchall()
            return [InterviewModel.from_row(row) for row in rows]

    def save_interview_evaluation(
        self,
        interview_id: int,
        expert_id: int,
        *,
        technical_score: int,
        communication_score: int,
        problem_solving_score: int,
        overall_rating: int,
        feedback: str | None = None,
        recommendation: str | None = None,
    ) -> InterviewEvaluationModel | None:
        scores = (
            technical_score,
            communication_score,
            problem_solving_score,
            overall_rating,
        )
        if any(
            isinstance(score, bool)
            or not isinstance(score, int)
            or score < 1
            or score > 5
            for score in scores
        ):
            raise sqlite3.IntegrityError("Interview scores must be between 1 and 5.")
        if recommendation not in {
            None, "strong_hire", "hire", "no_hire", "strong_no_hire"
        }:
            raise sqlite3.IntegrityError("Interview recommendation is invalid.")
        if feedback is not None and not isinstance(feedback, str):
            raise sqlite3.IntegrityError("Interview feedback must be text.")
        with self._transaction() as conn:
            eligible = conn.execute(
                """
                SELECT 1
                FROM interview_participants AS ip
                JOIN users AS u ON u.id = ip.expert_id
                JOIN interviews AS i ON i.id = ip.interview_id
                WHERE ip.interview_id = ? AND ip.expert_id = ?
                  AND ip.role = 'interviewer' AND u.role = 'expert'
                  AND i.status NOT IN ('cancelled', 'no_show')
                """,
                (interview_id, expert_id),
            ).fetchone()
            if eligible is None:
                return None
            conn.execute(
                """
                INSERT INTO interview_evaluations
                    (interview_id, expert_id, technical_score,
                     communication_score, problem_solving_score, overall_rating,
                     feedback, recommendation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(interview_id, expert_id)
                DO UPDATE SET technical_score = excluded.technical_score,
                    communication_score = excluded.communication_score,
                    problem_solving_score = excluded.problem_solving_score,
                    overall_rating = excluded.overall_rating,
                    feedback = excluded.feedback,
                    recommendation = excluded.recommendation
                """,
                (
                    interview_id,
                    expert_id,
                    technical_score,
                    communication_score,
                    problem_solving_score,
                    overall_rating,
                    feedback,
                    recommendation,
                ),
            )
            row = conn.execute(
                """
                SELECT * FROM interview_evaluations
                WHERE interview_id = ? AND expert_id = ?
                """,
                (interview_id, expert_id),
            ).fetchone()
            return InterviewEvaluationModel.from_row(row)

    def list_interview_evaluations(
        self, company_id: int, interview_id: int
    ) -> list[InterviewEvaluationModel]:
        with _DATABASE_LOCK:
            rows = self._connection.execute(
                """
                SELECT ie.*
                FROM interview_evaluations AS ie
                JOIN interviews AS i ON i.id = ie.interview_id
                WHERE i.id = ? AND i.company_id = ?
                ORDER BY ie.created_at, ie.id
                """,
                (interview_id, company_id),
            ).fetchall()
            return [InterviewEvaluationModel.from_row(row) for row in rows]

    def issue_certificate(
        self,
        user_id: int,
        skill_id: int,
        *,
        score: float | None = None,
        cert_code: str | None = None,
        expires_at: str | None = None,
    ) -> CertificateModel | None:
        if score is not None and (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or score < 0
        ):
            raise sqlite3.IntegrityError("Certificate score is invalid.")
        if expires_at is not None:
            if not isinstance(expires_at, str):
                raise sqlite3.IntegrityError("Certificate expiration is invalid.")
            try:
                datetime.fromisoformat(expires_at)
            except ValueError as exc:
                raise sqlite3.IntegrityError(
                    "Certificate expiration is invalid."
                ) from exc
        if cert_code is None:
            cert_code = f"SP-{uuid4().hex.upper()}"
        if not isinstance(cert_code, str) or not cert_code.strip():
            raise sqlite3.IntegrityError("Certificate code is required.")
        with self._transaction() as conn:
            user = conn.execute(
                "SELECT role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if user is None or user["role"] != "candidate":
                return None
            cursor = conn.execute(
                """
                INSERT INTO certificates
                    (user_id, skill_id, score, cert_code, expires_at, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (user_id, skill_id, score, cert_code.strip(), expires_at),
            )
            row = conn.execute(
                "SELECT * FROM certificates WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return CertificateModel.from_row(row)

    def verify_certificate(self, cert_code: str) -> CertificateModel | None:
        if not isinstance(cert_code, str) or not cert_code.strip():
            return None
        with _DATABASE_LOCK:
            row = self._connection.execute(
                "SELECT * FROM certificates WHERE cert_code = ?",
                (cert_code.strip(),),
            ).fetchone()
            if row is None:
                return None
            certificate = CertificateModel.from_row(row)
            return certificate if certificate.is_valid_at() else None

    def list_user_certificates(self, user_id: int) -> list[CertificateModel]:
        with _DATABASE_LOCK:
            rows = self._connection.execute(
                """
                SELECT * FROM certificates
                WHERE user_id = ?
                ORDER BY issued_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
            return [CertificateModel.from_row(row) for row in rows]

    def revoke_certificate(
        self,
        certificate_id: int,
        revoked_by: int,
        reason: str,
    ) -> CertificateModel | None:
        if not isinstance(reason, str) or not reason.strip():
            raise sqlite3.IntegrityError("Certificate revocation reason is required.")
        with self._transaction() as conn:
            actor = conn.execute(
                "SELECT role FROM users WHERE id = ?", (revoked_by,)
            ).fetchone()
            if actor is None or actor["role"] not in {"admin", "company", "expert"}:
                return None
            cursor = conn.execute(
                """
                UPDATE certificates
                SET status = 'revoked', revoked_at = datetime('now','localtime'),
                    revoked_by = ?, revocation_reason = ?
                WHERE id = ? AND status = 'active'
                """,
                (revoked_by, reason.strip(), certificate_id),
            )
            if cursor.rowcount != 1:
                return None
            row = conn.execute(
                "SELECT * FROM certificates WHERE id = ?", (certificate_id,)
            ).fetchone()
            return CertificateModel.from_row(row)
