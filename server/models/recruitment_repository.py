"""SQLite persistence for recruitment positions, exams, and submissions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta
import json
import math
import sqlite3
from threading import RLock
from typing import Protocol
from uuid import uuid4

from server.database.connection import db
from server.models.certificate_model import CertificateModel
from server.models.recruitment_models import (
    ExamAnswerGradingModel,
    ExamGradeRevisionModel,
    ExamProctoringPolicyModel,
    ExamProctoringSessionModel,
    ExamSessionEventModel,
    InterviewEvaluationModel,
    InterviewModel,
    InterviewParticipantModel,
    ProctoringVideoModel,
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

    @staticmethod
    def _reviewer_has_company_access(
        conn: sqlite3.Connection, company_id: int, reviewer_id: int
    ) -> bool:
        company = conn.execute(
            "SELECT role FROM users WHERE id = ?", (company_id,)
        ).fetchone()
        reviewer = conn.execute(
            "SELECT role FROM users WHERE id = ?", (reviewer_id,)
        ).fetchone()
        if (
            company is None
            or company["role"] != "company"
            or reviewer is None
        ):
            return False
        if reviewer["role"] == "admin":
            return True
        if reviewer["role"] == "company":
            return reviewer_id == company_id
        if reviewer["role"] == "expert":
            return conn.execute(
                """
                SELECT 1 FROM company_expert_contracts
                WHERE company_id = ? AND expert_id = ? AND status = 'active'
                """,
                (company_id, reviewer_id),
            ).fetchone() is not None
        return False

    @classmethod
    def _can_access_proctoring(
        cls,
        conn: sqlite3.Connection,
        session_id: int,
        actor_id: int,
        *,
        allow_experts: bool = True,
    ) -> bool:
        context = conn.execute(
            """
            SELECT es.candidate_id, es.company_id, ep.created_by
            FROM exam_proctoring_sessions AS ps
            JOIN exam_sessions AS es ON es.id = ps.exam_session_id
            JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
            WHERE es.id = ?
            """,
            (session_id,),
        ).fetchone()
        actor = conn.execute(
            """
            SELECT role FROM users
            WHERE id = ? AND is_active = 1 AND COALESCE(is_deleted, 0) = 0
            """,
            (actor_id,),
        ).fetchone()
        if context is None or actor is None:
            return False
        if actor["role"] == "admin":
            return True
        if actor["role"] == "candidate":
            return actor_id == context["candidate_id"]
        if (
            actor["role"] == "company"
            and context["company_id"] == actor_id
            and context["created_by"] == actor_id
        ):
            return True
        return (
            allow_experts
            and actor["role"] == "expert"
            and context["company_id"] is not None
            and cls._reviewer_has_company_access(
                conn, context["company_id"], actor_id
            )
        )

    @staticmethod
    def _can_manage_proctoring_recording(
        conn: sqlite3.Connection, session_id: int, actor_id: int
    ) -> bool:
        row = conn.execute(
            """
            SELECT es.company_id, ep.created_by, actor.role
            FROM exam_proctoring_sessions AS ps
            JOIN exam_sessions AS es ON es.id = ps.exam_session_id
            JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
            JOIN users AS actor
              ON actor.id = ? AND actor.is_active = 1
             AND COALESCE(actor.is_deleted, 0) = 0
            WHERE es.id = ?
            """,
            (actor_id, session_id),
        ).fetchone()
        if row is None:
            return False
        return row["role"] == "admin" or (
            row["role"] == "company"
            and row["company_id"] == actor_id
            and row["created_by"] == actor_id
        )

    @staticmethod
    def _validate_proctoring_policy(
        policy: ExamProctoringPolicyModel,
    ) -> ExamProctoringPolicyModel:
        numeric_values = (
            policy.warning_threshold,
            policy.termination_threshold,
            policy.camera_disconnect_timeout_seconds,
            policy.video_retention_days,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in numeric_values
        ):
            raise sqlite3.IntegrityError("Proctoring policy thresholds are invalid.")
        if policy.termination_threshold < policy.warning_threshold:
            raise sqlite3.IntegrityError(
                "Termination threshold cannot be below warning threshold."
            )
        if not isinstance(policy.terminate_exam_on_threshold, bool):
            raise sqlite3.IntegrityError(
                "Proctoring termination policy must be boolean."
            )
        return policy

    @classmethod
    def _decode_proctoring_policy(cls, value: str) -> ExamProctoringPolicyModel:
        try:
            raw = json.loads(value)
            if not isinstance(raw, dict):
                raise ValueError
            policy = ExamProctoringPolicyModel(**raw)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise sqlite3.IntegrityError(
                "Stored proctoring policy is invalid."
            ) from exc
        return cls._validate_proctoring_policy(policy)

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
        skill_id: int | None = None,
    ) -> Record | None:
        with self._transaction() as conn:
            if not self._company_role(conn, company_id):
                return None
            cursor = conn.execute(
                """
                INSERT INTO exam_papers
                    (title, description, skill_id, created_by, duration_min,
                     total_points, is_published)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    title,
                    description,
                    skill_id,
                    company_id,
                    duration_min,
                    total_points,
                ),
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

    def list_active_skills(self) -> list[Record]:
        return self._many(
            "SELECT id, name FROM skills WHERE is_active = 1 ORDER BY name, id"
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
        supported_languages: Sequence[str] | None = None,
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
        stored_languages: str | None = None
        normalized_languages: list[str] = []
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
            normalized_languages = self._normalize_supported_languages(
                supported_languages if supported_languages is not None else ("python",)
            )
            stored_languages = json.dumps(
                normalized_languages, ensure_ascii=False, separators=(",", ":")
            )
        elif test_cases:
            raise sqlite3.IntegrityError(
                "Test cases are only supported for coding questions."
            )
        elif supported_languages is not None:
            raise sqlite3.IntegrityError(
                "Supported languages are only valid for coding questions."
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
                     reference_answer, test_cases, supported_languages, is_published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    expert_id, question_type, title, content, difficulty, points,
                    reference_answer, stored_test_cases, stored_languages,
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
            question["supported_languages"] = (
                normalized_languages if question_type == "coding" else []
            )
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

    @staticmethod
    def _normalize_supported_languages(
        languages: Sequence[str],
    ) -> list[str]:
        if isinstance(languages, (str, bytes)):
            raise sqlite3.IntegrityError("Supported coding languages are invalid.")
        normalized: list[str] = []
        for language in languages:
            if not isinstance(language, str) or not language.strip():
                raise sqlite3.IntegrityError(
                    "Supported coding languages are invalid."
                )
            value = language.strip().lower()
            if value not in normalized:
                normalized.append(value)
        if not normalized:
            raise sqlite3.IntegrityError(
                "At least one coding language must be supported."
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

    def list_public_coding_test_cases(
        self, session_id: int, candidate_id: int, question_id: int
    ) -> list[Record] | None:
        question = self._one(
            """
            SELECT qb.test_cases
            FROM exam_sessions AS es
            JOIN exam_paper_questions AS epq
              ON epq.exam_paper_id = es.exam_paper_id
            JOIN question_bank AS qb ON qb.id = epq.question_id
            WHERE es.id = ? AND es.candidate_id = ?
              AND es.status = 'in_progress'
              AND epq.question_id = ? AND qb.question_type = 'coding'
            """,
            (session_id, candidate_id, question_id),
        )
        if question is None:
            return None
        raw_test_cases = question["test_cases"]
        if not isinstance(raw_test_cases, str):
            return []
        try:
            parsed = json.loads(raw_test_cases)
        except json.JSONDecodeError as exc:
            raise sqlite3.IntegrityError(
                "Stored coding test cases are invalid."
            ) from exc
        if not isinstance(parsed, list):
            raise sqlite3.IntegrityError("Stored coding test cases are invalid.")
        cases = self._normalize_coding_test_cases(parsed)
        return [
            {"input": case["input"], "expected_output": case["expected_output"]}
            for case in cases
            if not case["is_hidden"]
        ]

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
                SELECT rs.id, rs.exam_session_id, rs.candidate_id, rs.company_id,
                       es.total_score, es.max_score, ep.skill_id, ep.title
                FROM recruitment_submissions AS rs
                JOIN exam_sessions AS es ON es.id = rs.exam_session_id
                JOIN exam_papers AS ep ON ep.id = rs.exam_paper_id
                WHERE rs.company_id = ? AND rs.exam_paper_id = ?
                  AND es.company_id = ? AND rs.status = 'graded'
                """,
                (company_id, exam_id, company_id),
            ).fetchall()
            for row in submissions:
                changed = conn.execute(
                    """
                    UPDATE recruitment_submissions
                    SET status = 'released', released_at = datetime('now','localtime')
                    WHERE id = ? AND status = 'graded'
                    """,
                    (row["id"],),
                )
                if changed.rowcount == 1:
                    self._create_approved_assessment(
                        conn,
                        candidate_id=row["candidate_id"],
                        company_id=row["company_id"],
                        session_id=row["exam_session_id"],
                        skill_id=row["skill_id"],
                        exam_title=row["title"],
                        score=row["total_score"],
                        max_score=row["max_score"],
                    )
            result = dict(exam)
            result["status"] = "released"
            result["released_count"] = len(submissions)
            return result

    @staticmethod
    def _create_approved_assessment(
        conn: sqlite3.Connection,
        *,
        candidate_id: int,
        company_id: int,
        session_id: int,
        skill_id: int | None,
        exam_title: str,
        score: float | None,
        max_score: float | None,
    ) -> None:
        if (
            skill_id is None
            or score is None
            or max_score is None
            or not math.isfinite(float(score))
            or not math.isfinite(float(max_score))
            or float(max_score) <= 0
        ):
            return
        percentage = min(100.0, max(0.0, float(score) / float(max_score) * 100))
        conn.execute(
            """
            INSERT OR IGNORE INTO assessments
                (user_id, skill_id, score, max_score, notes, status, approved_by,
                 approved_at, source_exam_session_id)
            VALUES (?, ?, ?, 100, ?, 'approved', ?,
                    datetime('now','localtime'), ?)
            """,
            (
                candidate_id,
                skill_id,
                percentage,
                f"Released exam result: {exam_title}",
                company_id,
                session_id,
            ),
        )

    def release_submission_once(
        self, company_id: int, session_id: int
    ) -> Record | None:
        with self._transaction() as conn:
            row = conn.execute(
                """
                SELECT rs.id, rs.exam_session_id, rs.candidate_id, rs.company_id,
                       rs.status, es.total_score, es.max_score, ep.skill_id,
                       ep.title
                FROM recruitment_submissions AS rs
                JOIN exam_sessions AS es ON es.id = rs.exam_session_id
                JOIN exam_papers AS ep ON ep.id = rs.exam_paper_id
                WHERE rs.exam_session_id = ? AND rs.company_id = ?
                  AND ep.created_by = ? AND rs.status = 'graded'
                """,
                (session_id, company_id, company_id),
            ).fetchone()
            if row is None:
                return None
            updated = conn.execute(
                """
                UPDATE recruitment_submissions
                SET status = 'released', released_at = datetime('now','localtime')
                WHERE id = ? AND status = 'graded'
                """,
                (row["id"],),
            )
            if updated.rowcount != 1:
                return None
            self._create_approved_assessment(
                conn,
                candidate_id=row["candidate_id"],
                company_id=row["company_id"],
                session_id=row["exam_session_id"],
                skill_id=row["skill_id"],
                exam_title=row["title"],
                score=row["total_score"],
                max_score=row["max_score"],
            )
            released = conn.execute(
                "SELECT * FROM recruitment_submissions WHERE id = ?",
                (row["id"],),
            ).fetchone()
            return self._as_record(released)

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
                       qb.question_type, qb.difficulty, qb.supported_languages,
                       COALESCE(epq.points, qb.points) AS points, epq.sort_order,
                       ea.selected_option_id, ea.answer_text, ea.answer_code,
                       ea.programming_language
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
                raw_languages = question.pop("supported_languages")
                question["supported_languages"] = (
                    json.loads(raw_languages) if raw_languages else []
                )
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

    def list_candidate_question_summaries(
        self, session_id: int, candidate_id: int
    ) -> list[Record]:
        session = self._candidate_session(session_id, candidate_id)
        if session is None:
            return []
        return self._many(
            """
            SELECT qb.id, qb.title, qb.content, qb.question_type, qb.difficulty,
                   qb.supported_languages,
                   COALESCE(epq.points, qb.points) AS points,
                   ea.answer_text, ea.answer_code, ea.programming_language
            FROM exam_paper_questions AS epq
            JOIN question_bank AS qb ON qb.id = epq.question_id
            LEFT JOIN exam_answers AS ea
              ON ea.exam_session_id = ? AND ea.question_id = qb.id
            WHERE epq.exam_paper_id = ?
            ORDER BY epq.sort_order, epq.id
            """,
            (session_id, session["exam_paper_id"]),
        )

    def get_exam_session_context(self, session_id: int) -> Record | None:
        return self._one(
            """
            SELECT es.id, es.candidate_id, es.company_id, es.exam_paper_id,
                   es.status AS session_status, ep.title AS exam_title
            FROM exam_sessions AS es
            JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
            WHERE es.id = ?
            """,
            (session_id,),
        )

    def list_reviewer_submissions(
        self, reviewer_id: int, role: str
    ) -> list[Record]:
        if role not in {"company", "expert"}:
            return []
        with _DATABASE_LOCK:
            rows = self._connection.execute(
                """
                SELECT rs.id, rs.exam_session_id, rs.company_id, rs.candidate_id,
                       rs.exam_paper_id, rs.status, rs.submitted_at,
                       rs.graded_at, rs.released_at,
                       es.total_score AS score, es.max_score,
                       u.full_name AS candidate_name, ep.title AS exam_title
                FROM recruitment_submissions AS rs
                JOIN exam_sessions AS es ON es.id = rs.exam_session_id
                JOIN exam_papers AS ep ON ep.id = rs.exam_paper_id
                JOIN users AS u ON u.id = rs.candidate_id
                WHERE rs.status IN ('grading','graded')
                ORDER BY rs.submitted_at, rs.id
                """
            ).fetchall()
            return [
                dict(row)
                for row in rows
                if self._reviewer_has_company_access(
                    self._connection, row["company_id"], reviewer_id
                )
            ]

    def list_manual_grading_items(
        self, company_id: int, session_id: int, requester_id: int
    ) -> list[Record]:
        with _DATABASE_LOCK:
            if not self._reviewer_has_company_access(
                self._connection, company_id, requester_id
            ):
                return []
            return [
                dict(row)
                for row in self._connection.execute(
                    """
                    SELECT ea.id AS answer_id, ea.exam_session_id, ea.question_id,
                           ea.answer_text, ea.answer_code,
                           ea.programming_language, ea.score, ea.max_score,
                           ea.feedback, ea.is_graded, ea.graded_by, ea.graded_at,
                           qb.title AS question_title, qb.content AS question_content,
                           qb.question_type, u.full_name AS candidate_name,
                           ep.title AS exam_title, rs.status AS submission_status
                    FROM exam_answers AS ea
                    JOIN exam_sessions AS es ON es.id = ea.exam_session_id
                    JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
                    JOIN exam_paper_questions AS epq
                      ON epq.exam_paper_id = es.exam_paper_id
                     AND epq.question_id = ea.question_id
                    JOIN question_bank AS qb ON qb.id = ea.question_id
                    JOIN recruitment_submissions AS rs
                      ON rs.exam_session_id = es.id
                    JOIN users AS u ON u.id = es.candidate_id
                    WHERE es.id = ? AND es.company_id = ?
                      AND rs.status IN ('grading','graded')
                      AND qb.question_type IN ('essay','coding')
                    ORDER BY epq.sort_order, epq.id
                    """,
                    (session_id, company_id),
                ).fetchall()
            ]

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
        *,
        programming_language: str | None = None,
    ) -> Record | None:
        if not isinstance(answer, str):
            raise sqlite3.IntegrityError("Written exam answers must be text.")
        with self._transaction() as conn:
            session = self._candidate_session(session_id, candidate_id, conn=conn)
            if session is None or session["status"] != "in_progress":
                return None
            question = conn.execute(
                """
                SELECT qb.question_type, qb.supported_languages
                FROM exam_paper_questions AS epq
                JOIN question_bank AS qb ON qb.id = epq.question_id
                WHERE epq.exam_paper_id = ? AND qb.id = ?
                """,
                (session["exam_paper_id"], question_id),
            ).fetchone()
            if question is None or question["question_type"] not in {"essay", "coding"}:
                return None
            if question["question_type"] == "essay":
                if programming_language is not None:
                    raise sqlite3.IntegrityError(
                        "Essay answers cannot specify a programming language."
                    )
                conn.execute(
                    """
                    INSERT INTO exam_answers
                        (exam_session_id, question_id, answer_text)
                    VALUES (?, ?, ?)
                    ON CONFLICT(exam_session_id, question_id)
                    DO UPDATE SET answer_text = excluded.answer_text
                    """,
                    (session_id, question_id, answer),
                )
            else:
                try:
                    allowed_languages = json.loads(question["supported_languages"])
                except (TypeError, json.JSONDecodeError) as exc:
                    raise sqlite3.IntegrityError(
                        "Stored supported coding languages are invalid."
                    ) from exc
                if not isinstance(allowed_languages, list) or not allowed_languages:
                    raise sqlite3.IntegrityError(
                        "Coding question has no supported languages."
                    )
                if programming_language is not None and not isinstance(
                    programming_language, str
                ):
                    raise sqlite3.IntegrityError(
                        "Programming language must be text."
                    )
                language = (
                    programming_language.strip().lower()
                    if programming_language is not None
                    else allowed_languages[0]
                )
                if language not in allowed_languages:
                    return None
                conn.execute(
                    """
                    INSERT INTO exam_answers
                        (exam_session_id, question_id, answer_code,
                         programming_language)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(exam_session_id, question_id)
                    DO UPDATE SET answer_code = excluded.answer_code,
                                  programming_language = excluded.programming_language
                    """,
                    (session_id, question_id, answer, language),
                )
            return self._as_record(
                conn.execute(
                    """
                    SELECT id, exam_session_id, question_id, answer_text, answer_code,
                           programming_language
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
            SELECT ea.question_id, ea.selected_option_id, ea.programming_language,
                   ea.answer_text, ea.answer_code
            FROM exam_answers AS ea
            WHERE ea.exam_session_id = ?
            ORDER BY ea.question_id
            """,
            (session_id,),
        )

    def submit_exam_for_grading(
        self, session_id: int, candidate_id: int
    ) -> Record | None:
        """Complete a mixed exam and leave essay/coding responses pending review."""
        with self._transaction() as conn:
            session = conn.execute(
                """
                SELECT es.id, es.exam_paper_id, es.candidate_id, es.company_id,
                       ri.id AS invitation_id
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
                return None

            questions = conn.execute(
                """
                SELECT epq.question_id, qb.question_type,
                       COALESCE(epq.points, qb.points) AS points
                FROM exam_paper_questions AS epq
                JOIN question_bank AS qb ON qb.id = epq.question_id
                WHERE epq.exam_paper_id = ?
                ORDER BY epq.sort_order, epq.id
                """,
                (session["exam_paper_id"],),
            ).fetchall()
            if not questions:
                raise sqlite3.IntegrityError("An exam must contain a question.")

            objective_score = 0.0
            max_score = 0.0
            has_pending_answers = False
            for question in questions:
                question_id = question["question_id"]
                points = float(question["points"])
                if not math.isfinite(points) or points <= 0:
                    raise sqlite3.IntegrityError("Exam question points are invalid.")
                max_score += points
                answer = conn.execute(
                    """
                    SELECT id, selected_option_id
                    FROM exam_answers
                    WHERE exam_session_id = ? AND question_id = ?
                    """,
                    (session_id, question_id),
                ).fetchone()
                if question["question_type"] == "multiple_choice":
                    options = conn.execute(
                        """
                        SELECT id, is_correct FROM question_options
                        WHERE question_id = ?
                        """,
                        (question_id,),
                    ).fetchall()
                    correct_options = [
                        option["id"] for option in options if option["is_correct"] == 1
                    ]
                    if len(correct_options) != 1 or len(options) < 2:
                        raise sqlite3.IntegrityError(
                            "Exam question must have exactly one correct option."
                        )
                    selected_option_id = (
                        answer["selected_option_id"] if answer is not None else None
                    )
                    points_awarded = (
                        points if selected_option_id == correct_options[0] else 0.0
                    )
                    if answer is None:
                        cursor = conn.execute(
                            """
                            INSERT INTO exam_answers
                                (exam_session_id, question_id, max_score)
                            VALUES (?, ?, ?)
                            """,
                            (session_id, question_id, points),
                        )
                        answer_id = cursor.lastrowid
                    else:
                        answer_id = answer["id"]
                    conn.execute(
                        """
                        UPDATE exam_answers
                        SET score = ?, max_score = ?, is_graded = 1,
                            grading_mode = 'automatic',
                            graded_at = datetime('now','localtime')
                        WHERE id = ?
                        """,
                        (points_awarded, points, answer_id),
                    )
                    objective_score += points_awarded
                else:
                    has_pending_answers = True
                    if answer is None:
                        conn.execute(
                            """
                            INSERT INTO exam_answers
                                (exam_session_id, question_id, max_score)
                            VALUES (?, ?, ?)
                            """,
                            (session_id, question_id, points),
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE exam_answers
                            SET max_score = ?, is_graded = 0, score = NULL,
                                graded_by = NULL, graded_at = NULL
                            WHERE id = ?
                            """,
                            (points, answer["id"]),
                        )

            conn.execute(
                """
                UPDATE exam_sessions
                SET status = 'completed', total_score = ?, max_score = ?,
                    completed_at = datetime('now','localtime')
                WHERE id = ? AND status = 'in_progress'
                """,
                (
                    None if has_pending_answers else objective_score,
                    max_score,
                    session_id,
                ),
            )
            submission = conn.execute(
                """
                INSERT INTO recruitment_submissions
                    (invitation_id, exam_session_id, candidate_id,
                     company_id, exam_paper_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["invitation_id"],
                    session_id,
                    candidate_id,
                    session["company_id"],
                    session["exam_paper_id"],
                ),
            )
            conn.execute(
                """
                UPDATE recruitment_submissions SET status = 'grading'
                WHERE id = ? AND status = 'submitted'
                """,
                (submission.lastrowid,),
            )
            if not has_pending_answers:
                conn.execute(
                    """
                    UPDATE recruitment_submissions
                    SET status = 'graded', graded_at = datetime('now','localtime')
                    WHERE id = ? AND status = 'grading'
                    """,
                    (submission.lastrowid,),
                )
            return self._as_record(
                conn.execute(
                    """
                    SELECT rs.*, es.total_score AS score, es.max_score
                    FROM recruitment_submissions AS rs
                    JOIN exam_sessions AS es ON es.id = rs.exam_session_id
                    WHERE rs.id = ?
                    """,
                    (submission.lastrowid,),
                ).fetchone()
            )

    def list_exam_answers_for_grading(
        self,
        company_id: int,
        session_id: int,
        *,
        requester_id: int | None = None,
    ) -> list[ExamAnswerGradingModel]:
        with _DATABASE_LOCK:
            company = self._connection.execute(
                """
                SELECT 1
                FROM users AS u
                JOIN exam_sessions AS es ON es.company_id = u.id
                JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
                WHERE u.id = ? AND u.role = 'company'
                  AND es.id = ? AND ep.created_by = u.id
                """,
                (company_id, session_id),
            ).fetchone()
            actor_id = company_id if requester_id is None else requester_id
            if company is None or not self._reviewer_has_company_access(
                self._connection, company_id, actor_id
            ):
                return []
            rows = self._connection.execute(
                """
                SELECT ea.*, es.candidate_id, es.company_id, es.exam_paper_id
                FROM exam_answers AS ea
                JOIN exam_sessions AS es ON es.id = ea.exam_session_id
                WHERE es.id = ?
                ORDER BY ea.question_id
                """,
                (session_id,),
            ).fetchall()
            return [ExamAnswerGradingModel.from_row(row) for row in rows]

    @staticmethod
    def _normalize_coding_results(
        test_results: Sequence[Mapping[str, object]],
        expected_count: int,
    ) -> list[dict[str, object]]:
        if isinstance(test_results, (str, bytes)) or len(test_results) != expected_count:
            raise sqlite3.IntegrityError("Coding results do not match test cases.")
        normalized: list[dict[str, object]] = []
        for result in test_results:
            if not isinstance(result, Mapping) or not isinstance(
                result.get("passed"), bool
            ):
                raise sqlite3.IntegrityError("Coding test result is invalid.")
            normalized_result: dict[str, object] = {
                "passed": result["passed"],
            }
            for key in ("actual_output", "error"):
                value = result.get(key)
                if value is not None:
                    if not isinstance(value, str):
                        raise sqlite3.IntegrityError("Coding test result is invalid.")
                    normalized_result[key] = value
            normalized.append(normalized_result)
        return normalized

    def grade_exam_answer(
        self,
        company_id: int,
        grader_id: int,
        session_id: int,
        question_id: int,
        *,
        score: float | None = None,
        feedback: str | None = None,
        grading_mode: str = "manual",
        coding_test_results: Sequence[Mapping[str, object]] | None = None,
        revision_reason: str | None = None,
    ) -> ExamAnswerGradingModel | None:
        if grading_mode not in {"manual", "automatic"}:
            raise sqlite3.IntegrityError("Unsupported grading mode.")
        if feedback is not None and not isinstance(feedback, str):
            raise sqlite3.IntegrityError("Grading feedback must be text.")
        if grading_mode == "manual" and (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or score < 0
        ):
            raise sqlite3.IntegrityError("Manual grading requires a valid score.")
        if revision_reason is not None and not isinstance(revision_reason, str):
            raise sqlite3.IntegrityError("Grade revision reason must be text.")

        with self._transaction() as conn:
            answer = conn.execute(
                """
                SELECT ea.*, es.candidate_id, es.company_id, es.exam_paper_id,
                       epq.points AS question_points, qb.question_type,
                       qb.test_cases, rs.status AS submission_status
                FROM exam_answers AS ea
                JOIN exam_sessions AS es ON es.id = ea.exam_session_id
                JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
                JOIN exam_paper_questions AS epq
                  ON epq.exam_paper_id = es.exam_paper_id
                 AND epq.question_id = ea.question_id
                JOIN question_bank AS qb ON qb.id = ea.question_id
                JOIN recruitment_submissions AS rs
                  ON rs.exam_session_id = es.id
                WHERE es.id = ? AND ea.question_id = ?
                  AND es.company_id = ? AND ep.created_by = ?
                  AND es.status = 'completed'
                  AND rs.status IN ('grading', 'graded')
                """,
                (session_id, question_id, company_id, company_id),
            ).fetchone()
            if answer is None or answer["question_type"] not in {"essay", "coding"}:
                return None

            if not self._reviewer_has_company_access(conn, company_id, grader_id):
                return None
            if grading_mode == "automatic":
                if answer["question_type"] != "coding" or coding_test_results is None:
                    raise sqlite3.IntegrityError(
                        "Automatic grading requires coding test results."
                    )
                try:
                    test_cases = json.loads(answer["test_cases"])
                except (TypeError, json.JSONDecodeError) as exc:
                    raise sqlite3.IntegrityError(
                        "Stored coding test cases are invalid."
                    ) from exc
                if not isinstance(test_cases, list) or not test_cases:
                    raise sqlite3.IntegrityError("Coding test cases are required.")
                normalized_results = self._normalize_coding_results(
                    coding_test_results, len(test_cases)
                )
                score = float(answer["max_score"]) * sum(
                    result["passed"] for result in normalized_results
                ) / len(normalized_results)
                results_json = json.dumps(
                    normalized_results, ensure_ascii=False, separators=(",", ":")
                )
            else:
                if score is None:
                    raise sqlite3.IntegrityError("A manual grade score is required.")
                if coding_test_results is not None:
                    if answer["question_type"] != "coding":
                        raise sqlite3.IntegrityError(
                            "Test results are only valid for coding questions."
                        )
                    try:
                        test_cases = json.loads(answer["test_cases"])
                    except (TypeError, json.JSONDecodeError) as exc:
                        raise sqlite3.IntegrityError(
                            "Stored coding test cases are invalid."
                        ) from exc
                    if not isinstance(test_cases, list) or not test_cases:
                        raise sqlite3.IntegrityError("Coding test cases are required.")
                    normalized_results = self._normalize_coding_results(
                        coding_test_results, len(test_cases)
                    )
                    results_json = json.dumps(
                        normalized_results,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                else:
                    results_json = None
            max_score = float(answer["max_score"])
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
                or score < 0
                or score > max_score
            ):
                raise sqlite3.IntegrityError("Exam answer score is invalid.")
            if answer["is_graded"]:
                conn.execute(
                    """
                    INSERT INTO exam_grade_revisions
                        (exam_answer_id, graded_by, old_score, new_score,
                         old_feedback, new_feedback, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        answer["id"],
                        grader_id,
                        answer["score"],
                        score,
                        answer["feedback"],
                        feedback,
                        revision_reason,
                    ),
                )
            conn.execute(
                """
                UPDATE exam_answers
                SET score = ?, feedback = ?, graded_by = ?,
                    graded_at = datetime('now','localtime'), is_graded = 1,
                    grading_mode = ?, test_results_json = ?
                WHERE id = ?
                """,
                (
                    score,
                    feedback,
                    grader_id,
                    grading_mode,
                    results_json,
                    answer["id"],
                ),
            )
            totals = conn.execute(
                """
                SELECT COUNT(*) AS answer_count,
                       SUM(CASE WHEN is_graded = 0 THEN 1 ELSE 0 END) AS pending_count,
                       SUM(score) AS total_score, SUM(max_score) AS max_score
                FROM exam_answers
                WHERE exam_session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if totals["answer_count"] and not totals["pending_count"]:
                conn.execute(
                    """
                    UPDATE exam_sessions SET total_score = ?, max_score = ?
                    WHERE id = ?
                    """,
                    (totals["total_score"], totals["max_score"], session_id),
                )
                conn.execute(
                    """
                    UPDATE recruitment_submissions
                    SET status = 'graded', graded_at = datetime('now','localtime')
                    WHERE exam_session_id = ? AND status = 'grading'
                    """,
                    (session_id,),
                )
            row = conn.execute(
                """
                SELECT ea.*, es.candidate_id, es.company_id, es.exam_paper_id
                FROM exam_answers AS ea
                JOIN exam_sessions AS es ON es.id = ea.exam_session_id
                WHERE ea.id = ?
                """,
                (answer["id"],),
            ).fetchone()
            return ExamAnswerGradingModel.from_row(row)

    def list_exam_grade_revisions(
        self,
        company_id: int,
        requester_id: int,
        session_id: int,
        *,
        question_id: int | None = None,
    ) -> list[ExamGradeRevisionModel]:
        if question_id is not None and (
            isinstance(question_id, bool) or not isinstance(question_id, int)
        ):
            raise sqlite3.IntegrityError("Question id is invalid.")
        query = """
            SELECT egr.*
            FROM exam_grade_revisions AS egr
            JOIN exam_answers AS ea ON ea.id = egr.exam_answer_id
            JOIN exam_sessions AS es ON es.id = ea.exam_session_id
            JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
            WHERE es.id = ? AND es.company_id = ? AND ep.created_by = ?
        """
        params: tuple[object, ...] = (session_id, company_id, company_id)
        if question_id is not None:
            query += " AND ea.question_id = ?"
            params += (question_id,)
        query += " ORDER BY egr.created_at, egr.id"
        with _DATABASE_LOCK:
            if not self._reviewer_has_company_access(
                self._connection, company_id, requester_id
            ):
                return []
            rows = self._connection.execute(query, params).fetchall()
            return [ExamGradeRevisionModel.from_row(row) for row in rows]

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
                        graded_at = datetime('now','localtime'),
                        grading_mode = 'automatic'
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

    def get_exam_proctoring_policy(self) -> ExamProctoringPolicyModel:
        row = self._one(
            "SELECT value FROM app_settings WHERE key = ?",
            ("exam_proctoring.policy.v1",),
        )
        if row is None:
            return ExamProctoringPolicyModel()
        value = row.get("value")
        if not isinstance(value, str):
            raise sqlite3.IntegrityError("Stored proctoring policy is invalid.")
        return self._decode_proctoring_policy(value)

    def save_exam_proctoring_policy(
        self,
        admin_id: int,
        policy: ExamProctoringPolicyModel | Mapping[str, object],
    ) -> ExamProctoringPolicyModel | None:
        if isinstance(policy, Mapping):
            try:
                policy = ExamProctoringPolicyModel(**policy)
            except TypeError as exc:
                raise sqlite3.IntegrityError(
                    "Proctoring policy fields are invalid."
                ) from exc
        if not isinstance(policy, ExamProctoringPolicyModel):
            raise sqlite3.IntegrityError("Proctoring policy is invalid.")
        policy = self._validate_proctoring_policy(policy)
        with self._transaction() as conn:
            admin = conn.execute(
                """
                SELECT 1 FROM users
                WHERE id = ? AND role = 'admin' AND is_active = 1
                  AND COALESCE(is_deleted, 0) = 0
                """,
                (admin_id,),
            ).fetchone()
            if admin is None:
                return None
            conn.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = datetime('now','localtime')
                """,
                (
                    "exam_proctoring.policy.v1",
                    json.dumps(asdict(policy), sort_keys=True, separators=(",", ":")),
                ),
            )
            return policy

    def set_exam_recording_consent(
        self, session_id: int, candidate_id: int, *, consented: bool
    ) -> ExamProctoringSessionModel | None:
        if not isinstance(consented, bool):
            raise sqlite3.IntegrityError("Recording consent must be boolean.")
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._transaction() as conn:
            session = conn.execute(
                """
                SELECT * FROM exam_proctoring_sessions
                WHERE exam_session_id = ? AND candidate_id = ? AND status = 'active'
                """,
                (session_id, candidate_id),
            ).fetchone()
            if session is None:
                return None
            if bool(session["recording_consent"]) == consented:
                return ExamProctoringSessionModel.from_row(session)
            if session["video_status"] != "not_recorded":
                raise sqlite3.IntegrityError(
                    "Recording consent cannot change after recording metadata exists."
                )
            conn.execute(
                """
                UPDATE exam_proctoring_sessions
                SET recording_consent = ?, recording_consent_at = ?
                WHERE id = ?
                """,
                (int(consented), now if consented else None, session["id"]),
            )
            conn.execute(
                """
                INSERT INTO exam_session_events
                    (exam_session_id, candidate_id, proctoring_session_id,
                     event_type, is_violation, details_json, occurred_at,
                     consent_for_evidence)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    session_id,
                    candidate_id,
                    session["id"],
                    "recording_consent_granted"
                    if consented
                    else "recording_consent_withdrawn",
                    json.dumps(
                        {"recording_consent": consented},
                        separators=(",", ":"),
                    ),
                    now,
                    int(bool(session["consent_for_evidence"])),
                ),
            )
            row = conn.execute(
                "SELECT * FROM exam_proctoring_sessions WHERE id = ?",
                (session["id"],),
            ).fetchone()
            return ExamProctoringSessionModel.from_row(row)

    def update_exam_camera_status(
        self, session_id: int, candidate_id: int, *, camera_status: str
    ) -> ExamProctoringSessionModel | None:
        statuses = {
            "active",
            "disconnected",
            "permission_denied",
            "off",
            "not_started",
        }
        if not isinstance(camera_status, str) or camera_status not in statuses:
            raise sqlite3.IntegrityError("Unsupported camera status.")
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        event_types = {
            "active": "camera_connected",
            "disconnected": "camera_disconnected",
            "permission_denied": "camera_permission_denied",
            "off": "camera_off",
            "not_started": "camera_not_started",
        }
        with self._transaction() as conn:
            session = conn.execute(
                """
                SELECT * FROM exam_proctoring_sessions
                WHERE exam_session_id = ? AND candidate_id = ? AND status = 'active'
                """,
                (session_id, candidate_id),
            ).fetchone()
            if session is None:
                return None
            if session["camera_status"] == camera_status:
                return ExamProctoringSessionModel.from_row(session)
            conn.execute(
                """
                UPDATE exam_proctoring_sessions
                SET camera_status = ?, camera_status_changed_at = ?
                WHERE id = ?
                """,
                (camera_status, now, session["id"]),
            )
            conn.execute(
                """
                INSERT INTO exam_session_events
                    (exam_session_id, candidate_id, proctoring_session_id,
                     event_type, is_violation, details_json, occurred_at,
                     consent_for_evidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    candidate_id,
                    session["id"],
                    event_types[camera_status],
                    int(camera_status == "disconnected"),
                    json.dumps(
                        {"camera_status": camera_status},
                        separators=(",", ":"),
                    ),
                    now,
                    int(bool(session["consent_for_evidence"])),
                ),
            )
            row = conn.execute(
                "SELECT * FROM exam_proctoring_sessions WHERE id = ?",
                (session["id"],),
            ).fetchone()
            return ExamProctoringSessionModel.from_row(row)

    def start_exam_proctoring_session(
        self,
        session_id: int,
        candidate_id: int,
        *,
        consent_for_evidence: bool = False,
        recording_consent: bool = False,
    ) -> ExamProctoringSessionModel | None:
        if not isinstance(consent_for_evidence, bool):
            raise sqlite3.IntegrityError("Evidence consent must be boolean.")
        if not isinstance(recording_consent, bool):
            raise sqlite3.IntegrityError("Recording consent must be boolean.")
        with self._transaction() as conn:
            exam = conn.execute(
                """
                SELECT id FROM exam_sessions
                WHERE id = ? AND candidate_id = ? AND status = 'in_progress'
                """,
                (session_id, candidate_id),
            ).fetchone()
            if exam is None:
                return None
            existing = conn.execute(
                """
                SELECT * FROM exam_proctoring_sessions
                WHERE exam_session_id = ? AND candidate_id = ?
                """,
                (session_id, candidate_id),
            ).fetchone()
            if existing is not None:
                return ExamProctoringSessionModel.from_row(existing)
            cursor = conn.execute(
                """
                INSERT INTO exam_proctoring_sessions
                    (exam_session_id, candidate_id, consent_for_evidence,
                     recording_consent, recording_consent_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    candidate_id,
                    int(consent_for_evidence),
                    int(recording_consent),
                    (
                        datetime.now().astimezone().isoformat(timespec="seconds")
                        if recording_consent
                        else None
                    ),
                ),
            )
            row = conn.execute(
                "SELECT * FROM exam_proctoring_sessions WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return ExamProctoringSessionModel.from_row(row)

    def get_exam_proctoring_session(
        self, session_id: int, candidate_id: int
    ) -> ExamProctoringSessionModel | None:
        with _DATABASE_LOCK:
            row = self._connection.execute(
                """
                SELECT * FROM exam_proctoring_sessions
                WHERE exam_session_id = ? AND candidate_id = ?
                """,
                (session_id, candidate_id),
            ).fetchone()
            return (
                ExamProctoringSessionModel.from_row(row) if row is not None else None
            )

    def get_company_exam_proctoring_session(
        self,
        company_id: int,
        session_id: int,
        *,
        requester_id: int | None = None,
    ) -> ExamProctoringSessionModel | None:
        with _DATABASE_LOCK:
            owner = self._connection.execute(
                """
                SELECT 1
                FROM exam_sessions AS es
                JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
                WHERE es.id = ? AND es.company_id = ? AND ep.created_by = ?
                """,
                (session_id, company_id, company_id),
            ).fetchone()
            actor_id = company_id if requester_id is None else requester_id
            if owner is None or not self._reviewer_has_company_access(
                self._connection, company_id, actor_id
            ):
                return None
            row = self._connection.execute(
                """
                SELECT * FROM exam_proctoring_sessions WHERE exam_session_id = ?
                """,
                (session_id,),
            ).fetchone()
            return (
                ExamProctoringSessionModel.from_row(row) if row is not None else None
            )

    def list_proctoring_violation_history(
        self,
        session_id: int,
        viewer_id: int,
        *,
        processing_status: str | None = None,
    ) -> list[ExamSessionEventModel]:
        if processing_status not in {
            None, "pending", "reviewed", "dismissed", "escalated"
        }:
            raise sqlite3.IntegrityError("Unsupported event processing status.")
        with _DATABASE_LOCK:
            if not self._can_access_proctoring(
                self._connection, session_id, viewer_id
            ):
                return []
            rows = self._connection.execute(
                """
                SELECT * FROM exam_session_events
                WHERE exam_session_id = ? AND is_violation = 1
                  AND (? IS NULL OR processing_status = ?)
                ORDER BY julianday(occurred_at), id
                """,
                (session_id, processing_status, processing_status),
            ).fetchall()
            return [ExamSessionEventModel.from_row(row) for row in rows]

    def attach_proctoring_video(
        self,
        session_id: int,
        actor_id: int,
        video_path: str,
        *,
        created_at: str | None = None,
        retention_days: int | None = None,
    ) -> ProctoringVideoModel | None:
        if (
            not isinstance(video_path, str)
            or not video_path.strip()
            or video_path.strip().lower().startswith("data:")
        ):
            raise sqlite3.IntegrityError(
                "Video must be stored externally as a path or URI."
            )
        video_path = video_path.strip()
        if created_at is None:
            created = datetime.now().astimezone()
        else:
            if not isinstance(created_at, str):
                raise sqlite3.IntegrityError("Video creation time is invalid.")
            try:
                created = datetime.fromisoformat(created_at)
            except ValueError as exc:
                raise sqlite3.IntegrityError(
                    "Video creation time is invalid."
                ) from exc
        if retention_days is not None and (
            isinstance(retention_days, bool)
            or not isinstance(retention_days, int)
            or retention_days < 1
        ):
            raise sqlite3.IntegrityError("Video retention period is invalid.")

        with self._transaction() as conn:
            if not self._can_manage_proctoring_recording(
                conn, session_id, actor_id
            ):
                return None
            session = conn.execute(
                """
                SELECT * FROM exam_proctoring_sessions
                WHERE exam_session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if session is None:
                return None
            if not session["recording_consent"] or not session[
                "recording_consent_at"
            ]:
                raise sqlite3.IntegrityError(
                    "Recording cannot be attached without explicit consent."
                )
            if session["video_status"] != "not_recorded":
                raise sqlite3.IntegrityError(
                    "A recording already exists for this exam session."
                )
            if retention_days is None:
                setting = conn.execute(
                    "SELECT value FROM app_settings WHERE key = ?",
                    ("exam_proctoring.policy.v1",),
                ).fetchone()
                policy = (
                    self._decode_proctoring_policy(setting["value"])
                    if setting is not None
                    else ExamProctoringPolicyModel()
                )
                retention_days = policy.video_retention_days
            retention_until = created + timedelta(days=retention_days)
            created_value = created.isoformat(timespec="seconds")
            retention_value = retention_until.isoformat(timespec="seconds")
            conn.execute(
                """
                UPDATE exam_proctoring_sessions
                SET video_path = ?, video_created_at = ?,
                    video_retention_until = ?, video_status = 'available'
                WHERE id = ?
                """,
                (video_path, created_value, retention_value, session["id"]),
            )
            return ProctoringVideoModel(
                exam_session_id=session_id,
                candidate_id=session["candidate_id"],
                video_path=video_path,
                video_created_at=created_value,
                video_retention_until=retention_value,
                video_deleted_at=None,
                video_status="available",
            )

    def get_proctoring_video_for_session(
        self, session_id: int, viewer_id: int
    ) -> ProctoringVideoModel | None:
        with self._transaction() as conn:
            if not self._can_access_proctoring(conn, session_id, viewer_id):
                return None
            session = conn.execute(
                """
                SELECT ps.* FROM exam_proctoring_sessions AS ps
                WHERE ps.exam_session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if session is None:
                return None
            status = session["video_status"]
            if status == "available" and self._is_expired(
                session["video_retention_until"]
            ):
                conn.execute(
                    """
                    UPDATE exam_proctoring_sessions SET video_status = 'expired'
                    WHERE id = ? AND video_status = 'available'
                    """,
                    (session["id"],),
                )
                status = "expired"
            return ProctoringVideoModel(
                exam_session_id=session_id,
                candidate_id=session["candidate_id"],
                video_path=session["video_path"] if status == "available" else None,
                video_created_at=session["video_created_at"],
                video_retention_until=session["video_retention_until"],
                video_deleted_at=session["video_deleted_at"],
                video_status=status,
            )

    def list_expired_proctoring_videos(
        self, admin_id: int
    ) -> list[ProctoringVideoModel]:
        with self._transaction() as conn:
            admin = conn.execute(
                """
                SELECT 1 FROM users
                WHERE id = ? AND role = 'admin' AND is_active = 1
                  AND COALESCE(is_deleted, 0) = 0
                """,
                (admin_id,),
            ).fetchone()
            if admin is None:
                return []
            candidates = conn.execute(
                """
                SELECT * FROM exam_proctoring_sessions
                WHERE video_status = 'available'
                """
            ).fetchall()
            for session in candidates:
                if self._is_expired(session["video_retention_until"]):
                    conn.execute(
                        """
                        UPDATE exam_proctoring_sessions
                        SET video_status = 'expired'
                        WHERE id = ? AND video_status = 'available'
                        """,
                        (session["id"],),
                    )
            rows = conn.execute(
                """
                SELECT exam_session_id, candidate_id, video_path,
                       video_created_at, video_retention_until,
                       video_deleted_at, video_status
                FROM exam_proctoring_sessions
                WHERE video_status = 'expired'
                ORDER BY video_retention_until, exam_session_id
                """
            ).fetchall()
            return [
                ProctoringVideoModel(
                    exam_session_id=row["exam_session_id"],
                    candidate_id=row["candidate_id"],
                    video_path=row["video_path"],
                    video_created_at=row["video_created_at"],
                    video_retention_until=row["video_retention_until"],
                    video_deleted_at=row["video_deleted_at"],
                    video_status=row["video_status"],
                )
                for row in rows
            ]

    def record_proctoring_video_deleted(
        self, session_id: int, actor_id: int
    ) -> ProctoringVideoModel | None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._transaction() as conn:
            if not self._can_manage_proctoring_recording(
                conn, session_id, actor_id
            ):
                return None
            session = conn.execute(
                """
                SELECT * FROM exam_proctoring_sessions
                WHERE exam_session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if session is None or session["video_status"] == "not_recorded":
                return None
            if session["video_status"] != "deleted":
                conn.execute(
                    """
                    UPDATE exam_proctoring_sessions
                    SET video_path = NULL, video_status = 'deleted',
                        video_deleted_at = ?
                    WHERE id = ? AND video_status IN ('available','expired')
                    """,
                    (now, session["id"]),
                )
                session = conn.execute(
                    "SELECT * FROM exam_proctoring_sessions WHERE id = ?",
                    (session["id"],),
                ).fetchone()
            return ProctoringVideoModel(
                exam_session_id=session_id,
                candidate_id=session["candidate_id"],
                video_path=None,
                video_created_at=session["video_created_at"],
                video_retention_until=session["video_retention_until"],
                video_deleted_at=session["video_deleted_at"],
                video_status=session["video_status"],
            )

    def finish_exam_proctoring_session(
        self, session_id: int, candidate_id: int
    ) -> ExamProctoringSessionModel | None:
        with self._transaction() as conn:
            session = conn.execute(
                """
                SELECT * FROM exam_proctoring_sessions
                WHERE exam_session_id = ? AND candidate_id = ? AND status = 'active'
                """,
                (session_id, candidate_id),
            ).fetchone()
            if session is None:
                return None
            violation = conn.execute(
                """
                SELECT 1 FROM exam_session_events
                WHERE proctoring_session_id = ? AND is_violation = 1
                  AND processing_status = 'pending'
                LIMIT 1
                """,
                (session["id"],),
            ).fetchone()
            status = "flagged" if violation is not None else "completed"
            conn.execute(
                """
                UPDATE exam_proctoring_sessions
                SET status = ?, ended_at = datetime('now','localtime')
                WHERE id = ? AND status = 'active'
                """,
                (status, session["id"]),
            )
            updated = conn.execute(
                "SELECT * FROM exam_proctoring_sessions WHERE id = ?",
                (session["id"],),
            ).fetchone()
            return ExamProctoringSessionModel.from_row(updated)

    def record_exam_session_event(
        self,
        session_id: int,
        candidate_id: int,
        event_type: str,
        *,
        is_violation: bool = False,
        details: Mapping[str, object] | None = None,
        occurred_at: str | None = None,
        evidence_uri: str | None = None,
    ) -> ExamSessionEventModel:
        if not isinstance(event_type, str) or not event_type.strip():
            raise sqlite3.IntegrityError("Exam event type is required.")
        if not isinstance(is_violation, bool):
            raise sqlite3.IntegrityError("Exam event violation flag is invalid.")
        if details is not None and not isinstance(details, Mapping):
            raise sqlite3.IntegrityError("Exam event details must be an object.")
        if details is not None and any(not isinstance(key, str) for key in details):
            raise sqlite3.IntegrityError("Exam event detail keys must be text.")
        if evidence_uri is not None and (
            not isinstance(evidence_uri, str) or not evidence_uri.strip()
        ):
            raise sqlite3.IntegrityError("Evidence reference is invalid.")
        if evidence_uri is not None and evidence_uri.strip().lower().startswith("data:"):
            raise sqlite3.IntegrityError(
                "Evidence must be a reference, not embedded media."
            )
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
            proctoring = conn.execute(
                """
                SELECT * FROM exam_proctoring_sessions
                WHERE exam_session_id = ? AND candidate_id = ? AND status = 'active'
                """,
                (session_id, candidate_id),
            ).fetchone()
            if proctoring is None:
                raise sqlite3.IntegrityError(
                    "Exam event requires an active proctoring session."
                )
            if evidence_uri is not None and not proctoring["consent_for_evidence"]:
                raise sqlite3.IntegrityError(
                    "Evidence cannot be stored without explicit consent."
                )
            cursor = conn.execute(
                """
                INSERT INTO exam_session_events
                    (exam_session_id, candidate_id, proctoring_session_id,
                     event_type, is_violation, details_json, occurred_at,
                     evidence_uri, consent_for_evidence)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now','localtime')),
                        ?, ?)
                """,
                (
                    session_id,
                    candidate_id,
                    proctoring["id"],
                    event_type.strip(),
                    int(is_violation),
                    details_json,
                    occurred_at,
                    evidence_uri.strip() if evidence_uri else None,
                    int(bool(proctoring["consent_for_evidence"])),
                ),
            )
            row = conn.execute(
                "SELECT * FROM exam_session_events WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return ExamSessionEventModel.from_row(row)

    def list_company_exam_session_events(
        self,
        company_id: int,
        session_id: int,
        *,
        requester_id: int | None = None,
        violations_only: bool = False,
        processing_status: str | None = None,
    ) -> list[ExamSessionEventModel]:
        if processing_status not in {
            None, "pending", "reviewed", "dismissed", "escalated"
        }:
            raise sqlite3.IntegrityError("Unsupported event processing status.")
        with _DATABASE_LOCK:
            company = self._connection.execute(
                """
                SELECT 1
                FROM exam_sessions AS es
                JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
                JOIN users AS u ON u.id = es.company_id
                WHERE es.id = ? AND es.company_id = ?
                  AND ep.created_by = u.id AND u.role = 'company'
                """,
                (session_id, company_id),
            ).fetchone()
            actor_id = company_id if requester_id is None else requester_id
            if company is None or not self._reviewer_has_company_access(
                self._connection, company_id, actor_id
            ):
                return []
            rows = self._connection.execute(
                """
                SELECT * FROM exam_session_events
                WHERE exam_session_id = ?
                  AND (? = 0 OR is_violation = 1)
                  AND (? IS NULL OR processing_status = ?)
                ORDER BY occurred_at, id
                """,
                (
                    session_id,
                    int(violations_only),
                    processing_status,
                    processing_status,
                ),
            ).fetchall()
            return [ExamSessionEventModel.from_row(row) for row in rows]

    def review_exam_session_event(
        self,
        company_id: int,
        reviewer_id: int,
        event_id: int,
        *,
        processing_status: str,
        notes: str | None = None,
    ) -> ExamSessionEventModel | None:
        if processing_status not in {"reviewed", "dismissed", "escalated"}:
            raise sqlite3.IntegrityError("Unsupported event processing outcome.")
        if notes is not None and not isinstance(notes, str):
            raise sqlite3.IntegrityError("Event review notes must be text.")
        with self._transaction() as conn:
            event = conn.execute(
                """
                SELECT ese.*, es.company_id
                FROM exam_session_events AS ese
                JOIN exam_sessions AS es ON es.id = ese.exam_session_id
                JOIN exam_papers AS ep ON ep.id = es.exam_paper_id
                WHERE ese.id = ? AND es.company_id = ? AND ep.created_by = ?
                """,
                (event_id, company_id, company_id),
            ).fetchone()
            if event is None or event["processing_status"] != "pending":
                return None
            if not self._reviewer_has_company_access(
                conn, company_id, reviewer_id
            ):
                return None
            updated = conn.execute(
                """
                UPDATE exam_session_events
                SET processing_status = ?, processed_by = ?,
                    processed_at = datetime('now','localtime'),
                    processing_notes = ?
                WHERE id = ? AND processing_status = 'pending'
                """,
                (processing_status, reviewer_id, notes, event_id),
            )
            if updated.rowcount != 1:
                return None
            proctoring_id = event["proctoring_session_id"]
            if proctoring_id is not None:
                pending = conn.execute(
                    """
                    SELECT 1 FROM exam_session_events
                    WHERE proctoring_session_id = ?
                      AND processing_status = 'pending'
                    LIMIT 1
                    """,
                    (proctoring_id,),
                ).fetchone()
                if pending is None:
                    conn.execute(
                        """
                        UPDATE exam_proctoring_sessions
                        SET status = 'reviewed', reviewed_by = ?,
                            reviewed_at = datetime('now','localtime'),
                            review_notes = ?
                        WHERE id = ? AND status IN ('completed','flagged')
                        """,
                        (reviewer_id, notes, proctoring_id),
                    )
            row = conn.execute(
                "SELECT * FROM exam_session_events WHERE id = ?", (event_id,)
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

    def list_expert_interviews(self, expert_id: int) -> list[Record]:
        return self._many(
            """
            SELECT i.*, candidate.full_name AS candidate_name
            FROM interviews AS i
            JOIN interview_participants AS ip ON ip.interview_id = i.id
            JOIN users AS candidate ON candidate.id = i.candidate_id
            WHERE ip.expert_id = ? AND ip.role = 'interviewer'
            ORDER BY i.scheduled_at, i.id
            """,
            (expert_id,),
        )

    def list_user_interview_records(
        self, user_id: int, role: str
    ) -> list[Record]:
        if role == "company":
            clause = "i.company_id = ?"
        elif role == "candidate":
            clause = "i.candidate_id = ?"
        elif role == "expert":
            clause = """
                EXISTS (
                    SELECT 1 FROM interview_participants AS ip
                    WHERE ip.interview_id = i.id AND ip.expert_id = ?
                      AND ip.role = 'interviewer'
                )
            """
        else:
            return []
        return self._many(
            f"""
            SELECT i.*, candidate.full_name AS candidate_name,
                   company.full_name AS company_name
            FROM interviews AS i
            JOIN users AS candidate ON candidate.id = i.candidate_id
            LEFT JOIN users AS company ON company.id = i.company_id
            WHERE {clause}
            ORDER BY i.scheduled_at, i.id
            """,
            (user_id,),
        )

    def can_evaluate_interview(self, interview_id: int, expert_id: int) -> bool:
        row = self._one(
            """
            SELECT 1
            FROM interview_participants AS ip
            JOIN interviews AS i ON i.id = ip.interview_id
            JOIN users AS u ON u.id = ip.expert_id
            WHERE ip.interview_id = ? AND ip.expert_id = ?
              AND ip.role = 'interviewer' AND u.role = 'expert'
              AND i.status IN ('in_progress','completed')
            """,
            (interview_id, expert_id),
        )
        return row is not None

    def list_expert_interview_evaluations(
        self, expert_id: int, interview_id: int
    ) -> list[InterviewEvaluationModel]:
        with _DATABASE_LOCK:
            if not self.can_evaluate_interview(interview_id, expert_id):
                return []
            rows = self._connection.execute(
                """
                SELECT * FROM interview_evaluations
                WHERE interview_id = ? AND expert_id = ?
                ORDER BY created_at, id
                """,
                (interview_id, expert_id),
            ).fetchall()
            return [InterviewEvaluationModel.from_row(row) for row in rows]

    def list_interview_participants(
        self, company_id: int, interview_id: int
    ) -> list[InterviewParticipantModel]:
        with _DATABASE_LOCK:
            rows = self._connection.execute(
                """
                SELECT ip.*
                FROM interview_participants AS ip
                JOIN interviews AS i ON i.id = ip.interview_id
                WHERE i.id = ? AND i.company_id = ?
                ORDER BY ip.id
                """,
                (interview_id, company_id),
            ).fetchall()
            return [InterviewParticipantModel.from_row(row) for row in rows]

    def set_interview_status(
        self, company_id: int, interview_id: int, status: str
    ) -> InterviewModel | None:
        if status not in {"in_progress", "completed", "cancelled", "no_show"}:
            raise sqlite3.IntegrityError("Unsupported interview status transition.")
        with self._transaction() as conn:
            interview = conn.execute(
                """
                SELECT i.* FROM interviews AS i
                JOIN users AS company ON company.id = i.company_id
                WHERE i.id = ? AND i.company_id = ? AND company.role = 'company'
                """,
                (interview_id, company_id),
            ).fetchone()
            if interview is None:
                return None
            current_status = interview["status"]
            if status == current_status:
                return InterviewModel.from_row(interview)
            allowed = {
                "scheduled": {"in_progress", "completed", "cancelled", "no_show"},
                "in_progress": {"completed", "cancelled", "no_show"},
            }
            if status not in allowed.get(current_status, set()):
                return None
            conn.execute(
                "UPDATE interviews SET status = ? WHERE id = ?",
                (status, interview_id),
            )
            updated = conn.execute(
                "SELECT * FROM interviews WHERE id = ?", (interview_id,)
            ).fetchone()
            return InterviewModel.from_row(updated)

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
                  AND i.status IN ('in_progress', 'completed')
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

    def get_account_role(self, user_id: int) -> str | None:
        row = self._one("SELECT role FROM users WHERE id = ?", (user_id,))
        return str(row["role"]) if row is not None else None

    def is_active_candidate(self, candidate_id: int) -> bool:
        row = self._one(
            """
            SELECT 1 FROM users
            WHERE id = ? AND role = 'candidate' AND is_active = 1
              AND COALESCE(is_deleted, 0) = 0
            """,
            (candidate_id,),
        )
        return row is not None

    def get_approved_assessment(
        self, candidate_id: int, skill_id: int
    ) -> Record | None:
        return self._one(
            """
            SELECT id, user_id, skill_id, score, max_score, taken_at, notes,
                   status, approved_by, approved_at, source_exam_session_id
            FROM assessments
            WHERE user_id = ? AND skill_id = ? AND status = 'approved'
            ORDER BY approved_at DESC, id DESC
            LIMIT 1
            """,
            (candidate_id, skill_id),
        )

    def get_certificate_for_candidate(
        self, candidate_id: int, skill_id: int
    ) -> Record | None:
        return self._certificate_record(
            """
            SELECT c.*, u.full_name AS subject_name, s.name AS skill_name
            FROM certificates AS c
            JOIN users AS u ON u.id = c.user_id
            JOIN skills AS s ON s.id = c.skill_id
            WHERE c.user_id = ? AND c.skill_id = ?
            """,
            (candidate_id, skill_id),
        )

    def get_certificate_by_code(self, cert_code: str) -> Record | None:
        return self._certificate_record(
            """
            SELECT c.*, u.full_name AS subject_name, s.name AS skill_name
            FROM certificates AS c
            JOIN users AS u ON u.id = c.user_id
            JOIN skills AS s ON s.id = c.skill_id
            WHERE c.cert_code = ?
            """,
            (cert_code,),
        )

    def get_certificate_by_id(self, certificate_id: int) -> Record | None:
        return self._certificate_record(
            """
            SELECT c.*, u.full_name AS subject_name, s.name AS skill_name
            FROM certificates AS c
            JOIN users AS u ON u.id = c.user_id
            JOIN skills AS s ON s.id = c.skill_id
            WHERE c.id = ?
            """,
            (certificate_id,),
        )

    def _certificate_record(
        self, sql: str, params: tuple[object, ...]
    ) -> Record | None:
        return self._one(sql, params)

    def can_view_certificate(
        self, certificate_id: int, viewer_id: int, role: str
    ) -> bool:
        with _DATABASE_LOCK:
            row = self._connection.execute(
                "SELECT user_id FROM certificates WHERE id = ?",
                (certificate_id,),
            ).fetchone()
            if row is None:
                return False
            if role == "admin":
                return True
            if role == "candidate":
                return row["user_id"] == viewer_id
            if role in {"company", "expert"}:
                account = self._connection.execute(
                    "SELECT 1 FROM users WHERE id = ? AND role = ? AND is_active = 1",
                    (viewer_id, role),
                ).fetchone()
                return account is not None
            return False

    def list_certificates_for_viewer(
        self, viewer_id: int, role: str
    ) -> list[Record]:
        if role == "admin":
            where = ""
            params: tuple[object, ...] = ()
        elif role == "candidate":
            where = "WHERE c.user_id = ?"
            params = (viewer_id,)
        else:
            return []
        return self._many(
            f"""
            SELECT c.*, u.full_name AS subject_name, s.name AS skill_name
            FROM certificates AS c
            JOIN users AS u ON u.id = c.user_id
            JOIN skills AS s ON s.id = c.skill_id
            {where}
            ORDER BY c.issued_at DESC, c.id DESC
            """,
            params,
        )

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
            if actor is None or actor["role"] != "admin":
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
