"""SQLite persistence for recruitment and multiple-choice exam workflows."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from typing import Protocol

from server.database.connection import db


class ExamOptionLike(Protocol):
    content: str
    is_correct: bool


Record = Mapping[str, object]


class RecruitmentRepository:
    """Implements the persistence contracts consumed by recruitment Services."""

    @staticmethod
    def _record(row: sqlite3.Row | None) -> dict[str, object] | None:
        return dict(row) if row is not None else None

    @staticmethod
    def _exam_query() -> str:
        return """
            SELECT ep.*,
                   COUNT(epq.question_id) AS question_count
            FROM exam_papers ep
            LEFT JOIN exam_paper_questions epq ON epq.exam_paper_id = ep.id
        """

    @staticmethod
    def _invitation_query() -> str:
        return """
            SELECT ri.*,
                   COALESCE(cp.company_name, company.full_name) AS company_name,
                   jp.title AS position_title,
                   ep.title AS exam_title,
                   ep.duration_min,
                   es.status AS session_status,
                   es.scheduled_at
            FROM recruitment_invitations ri
            JOIN users company ON company.id = ri.company_id
            LEFT JOIN company_profiles cp ON cp.user_id = ri.company_id
            JOIN job_postings jp ON jp.id = ri.job_posting_id
            JOIN exam_papers ep ON ep.id = ri.exam_paper_id
            LEFT JOIN exam_sessions es ON es.id = ri.exam_session_id
        """

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
        cursor = db.execute(
            """
            INSERT INTO job_postings
                (company_id, title, description, requirements, location, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (company_id, title, description, requirements, location, status),
        )
        return self.get_job_posting(company_id, cursor.lastrowid)

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
        cursor = db.execute(
            """
            UPDATE job_postings
            SET title = ?, description = ?, requirements = ?, location = ?, status = ?
            WHERE id = ? AND company_id = ?
            """,
            (title, description, requirements, location, status, position_id, company_id),
        )
        if cursor.rowcount == 0:
            return None
        return self.get_job_posting(company_id, position_id)

    def get_job_posting(
        self, company_id: int, position_id: int
    ) -> Record | None:
        return self._record(
            db.fetchone(
                "SELECT * FROM job_postings WHERE id = ? AND company_id = ?",
                (position_id, company_id),
            )
        )

    def list_job_postings(self, company_id: int) -> Sequence[Record]:
        return [
            dict(row)
            for row in db.fetchall(
                """
                SELECT * FROM job_postings
                WHERE company_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (company_id,),
            )
        ]

    def list_candidates(
        self, company_id: int, search: str = ""
    ) -> Sequence[Record]:
        company = db.fetchone(
            "SELECT 1 FROM users WHERE id = ? AND role = 'company' AND is_active = 1",
            (company_id,),
        )
        if company is None:
            return ()
        needle = f"%{search.strip().casefold()}%"
        return [
            dict(row)
            for row in db.fetchall(
                """
                SELECT id, full_name, email
                FROM users
                WHERE role = 'candidate'
                  AND is_active = 1
                  AND COALESCE(is_deleted, 0) = 0
                  AND (? = '%%' OR lower(full_name) LIKE lower(?) OR lower(email) LIKE lower(?))
                ORDER BY full_name, id
                """,
                (needle, needle, needle),
            )
        ]

    def create_exam(
        self,
        company_id: int,
        *,
        title: str,
        description: str,
        duration_min: int,
        total_points: float,
    ) -> Record | None:
        cursor = db.execute(
            """
            INSERT INTO exam_papers
                (title, description, created_by, duration_min, total_points)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, description, company_id, duration_min, total_points),
        )
        return self.get_exam_for_company(company_id, cursor.lastrowid)

    def get_exam_for_company(
        self, company_id: int, exam_id: int
    ) -> Record | None:
        row = db.fetchone(
            self._exam_query()
            + " WHERE ep.id = ? AND ep.created_by = ? GROUP BY ep.id",
            (exam_id, company_id),
        )
        return self._record(row)

    def list_exams_for_company(self, company_id: int) -> Sequence[Record]:
        return [
            dict(row)
            for row in db.fetchall(
                self._exam_query()
                + """
                WHERE ep.created_by = ?
                GROUP BY ep.id
                ORDER BY ep.created_at DESC, ep.id DESC
                """,
                (company_id,),
            )
        ]

    def add_question(
        self,
        company_id: int,
        exam_id: int,
        *,
        title: str,
        content: str,
        difficulty: str,
        points: float,
        options: Sequence[ExamOptionLike],
    ) -> Record | None:
        connection = db.get_connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            exam = connection.execute(
                """
                SELECT id FROM exam_papers
                WHERE id = ? AND created_by = ? AND is_published = 0
                """,
                (exam_id, company_id),
            ).fetchone()
            if exam is None:
                connection.rollback()
                return None

            # The legacy question table stores the author user ID in expert_id.
            question_cursor = connection.execute(
                """
                INSERT INTO question_bank
                    (expert_id, question_type, title, content, difficulty, points)
                VALUES (?, 'multiple_choice', ?, ?, ?, ?)
                """,
                (company_id, title, content, difficulty, points),
            )
            question_id = question_cursor.lastrowid
            for sort_order, option in enumerate(options):
                connection.execute(
                    """
                    INSERT INTO question_options
                        (question_id, content, is_correct, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        question_id,
                        option.content,
                        int(option.is_correct),
                        sort_order,
                    ),
                )
            connection.execute(
                """
                INSERT INTO exam_paper_questions
                    (exam_paper_id, question_id, sort_order, points)
                VALUES (?, ?, ?, ?)
                """,
                (exam_id, question_id, self._question_count(exam_id), points),
            )
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise

        return self._record(
            db.fetchone(
                """
                SELECT id, title, content, difficulty, points
                FROM question_bank WHERE id = ?
                """,
                (question_id,),
            )
        )

    @staticmethod
    def _question_count(exam_id: int) -> int:
        row = db.fetchone(
            "SELECT COUNT(*) AS count FROM exam_paper_questions WHERE exam_paper_id = ?",
            (exam_id,),
        )
        return int(row["count"])

    def get_user_role(self, user_id: int) -> str | None:
        row = db.fetchone(
            """
            SELECT role FROM users
            WHERE id = ? AND is_active = 1 AND COALESCE(is_deleted, 0) = 0
            """,
            (user_id,),
        )
        return row["role"] if row is not None else None

    def publish_exam(self, company_id: int, exam_id: int) -> Record | None:
        connection = db.get_connection()
        cursor = connection.execute(
            """
            UPDATE exam_papers
            SET is_published = 1
            WHERE id = ? AND created_by = ? AND is_published = 0
              AND EXISTS (
                  SELECT 1 FROM exam_paper_questions
                  WHERE exam_paper_id = exam_papers.id
              )
            """,
            (exam_id, company_id),
        )
        connection.commit()
        if cursor.rowcount == 0:
            exam = self.get_exam_for_company(company_id, exam_id)
            if exam is None or not exam.get("is_published"):
                return None
        return self.get_exam_for_company(company_id, exam_id)

    def get_candidate_invitation(
        self, invitation_id: int, candidate_id: int
    ) -> Record | None:
        return self._record(
            db.fetchone(
                self._invitation_query()
                + " WHERE ri.id = ? AND ri.candidate_id = ?",
                (invitation_id, candidate_id),
            )
        )

    def accept_candidate_invitation(
        self, invitation_id: int, candidate_id: int
    ) -> Record | None:
        connection = db.get_connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            invitation = connection.execute(
                """
                SELECT ri.*, ep.total_points
                FROM recruitment_invitations ri
                JOIN exam_papers ep ON ep.id = ri.exam_paper_id
                WHERE ri.id = ? AND ri.candidate_id = ?
                """,
                (invitation_id, candidate_id),
            ).fetchone()
            if invitation is None:
                connection.rollback()
                return None
            if invitation["status"] == "accepted":
                connection.rollback()
                return self.get_candidate_invitation(invitation_id, candidate_id)
            if invitation["status"] != "pending":
                connection.rollback()
                return self.get_candidate_invitation(invitation_id, candidate_id)

            session_cursor = connection.execute(
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
                    invitation["total_points"],
                ),
            )
            session_id = session_cursor.lastrowid
            updated = connection.execute(
                """
                UPDATE recruitment_invitations
                SET exam_session_id = ?, status = 'accepted',
                    responded_at = datetime('now','localtime')
                WHERE id = ? AND candidate_id = ? AND status = 'pending'
                """,
                (session_id, invitation_id, candidate_id),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return None
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise
        return self.get_candidate_invitation(invitation_id, candidate_id)

    def expire_candidate_invitation(
        self, invitation_id: int, candidate_id: int
    ) -> None:
        db.execute(
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
        connection = db.get_connection()
        active = connection.execute(
            """
            SELECT 1
            FROM recruitment_invitations ri
            LEFT JOIN recruitment_submissions rs ON rs.invitation_id = ri.id
            WHERE ri.job_posting_id = ?
              AND ri.candidate_id = ?
              AND ri.exam_paper_id = ?
              AND ri.status IN ('pending', 'accepted')
              AND COALESCE(rs.status, '') <> 'released'
            LIMIT 1
            """,
            (job_posting_id, candidate_id, exam_id),
        ).fetchone()
        if active is not None:
            raise sqlite3.IntegrityError("An active invitation already exists.")
        cursor = db.execute(
            """
            INSERT INTO recruitment_invitations
                (job_posting_id, company_id, candidate_id, exam_paper_id, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_posting_id, company_id, candidate_id, exam_id, expires_at),
        )
        return self._record(
            db.fetchone(
                "SELECT * FROM recruitment_invitations WHERE id = ?",
                (cursor.lastrowid,),
            )
        )

    def list_company_submissions(
        self, company_id: int, exam_id: int
    ) -> Sequence[Record]:
        return [
            dict(row)
            for row in db.fetchall(
                """
                SELECT rs.id AS submission_id,
                       rs.invitation_id,
                       rs.exam_session_id,
                       rs.exam_paper_id AS exam_id,
                       rs.status,
                       rs.submitted_at,
                       es.total_score AS score,
                       es.max_score,
                       candidate.full_name AS candidate_name,
                       jp.title AS position_title,
                       ep.title AS assessment_title
                FROM recruitment_submissions rs
                JOIN exam_sessions es ON es.id = rs.exam_session_id
                JOIN recruitment_invitations ri ON ri.id = rs.invitation_id
                JOIN users candidate ON candidate.id = rs.candidate_id
                JOIN job_postings jp ON jp.id = ri.job_posting_id
                JOIN exam_papers ep ON ep.id = rs.exam_paper_id
                WHERE rs.company_id = ?
                  AND rs.exam_paper_id = ?
                  AND ep.created_by = ?
                ORDER BY rs.submitted_at DESC, rs.id DESC
                """,
                (company_id, exam_id, company_id),
            )
        ]

    def release_results(self, company_id: int, exam_id: int) -> Record | None:
        connection = db.get_connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            exam = connection.execute(
                "SELECT id FROM exam_papers WHERE id = ? AND created_by = ?",
                (exam_id, company_id),
            ).fetchone()
            if exam is None:
                connection.rollback()
                return None
            connection.execute(
                """
                UPDATE recruitment_submissions
                SET status = 'released', released_at = datetime('now','localtime')
                WHERE company_id = ? AND exam_paper_id = ? AND status = 'graded'
                """,
                (company_id, exam_id),
            )
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise
        return self.get_exam_for_company(company_id, exam_id)

    def list_candidate_invitations(
        self, candidate_id: int
    ) -> Sequence[Record]:
        return [
            dict(row)
            for row in db.fetchall(
                self._invitation_query()
                + """
                WHERE ri.candidate_id = ?
                ORDER BY ri.invited_at DESC, ri.id DESC
                """,
                (candidate_id,),
            )
        ]

    def get_candidate_session(
        self, session_id: int, candidate_id: int
    ) -> Record | None:
        return self._record(
            db.fetchone(
                """
                SELECT es.*, ep.duration_min, ri.id AS invitation_id
                FROM exam_sessions es
                JOIN exam_papers ep ON ep.id = es.exam_paper_id
                JOIN recruitment_invitations ri ON ri.exam_session_id = es.id
                WHERE es.id = ? AND es.candidate_id = ?
                  AND ri.candidate_id = ? AND ri.status = 'accepted'
                """,
                (session_id, candidate_id, candidate_id),
            )
        )

    def start_session_once(
        self, session_id: int, candidate_id: int
    ) -> tuple[bool, Record | None]:
        connection = db.get_connection()
        cursor = connection.execute(
            """
            UPDATE exam_sessions
            SET status = 'in_progress',
                started_at = COALESCE(started_at, datetime('now','localtime'))
            WHERE id = ? AND candidate_id = ? AND status = 'scheduled'
              AND EXISTS (
                  SELECT 1 FROM recruitment_invitations ri
                  WHERE ri.exam_session_id = exam_sessions.id
                    AND ri.candidate_id = ? AND ri.status = 'accepted'
              )
            """,
            (session_id, candidate_id, candidate_id),
        )
        connection.commit()
        session = self.get_candidate_session(session_id, candidate_id)
        return cursor.rowcount == 1, session

    def list_candidate_questions(
        self, session_id: int, candidate_id: int
    ) -> Sequence[Record]:
        session = self.get_candidate_session(session_id, candidate_id)
        if session is None or session.get("status") != "in_progress":
            return ()
        questions = db.fetchall(
            """
            SELECT qb.id,
                   qb.title,
                   qb.content,
                   qb.question_type,
                   qb.difficulty,
                   COALESCE(epq.points, qb.points) AS points,
                   epq.sort_order,
                   ea.selected_option_id
            FROM exam_sessions es
            JOIN exam_paper_questions epq ON epq.exam_paper_id = es.exam_paper_id
            JOIN question_bank qb ON qb.id = epq.question_id
            LEFT JOIN exam_answers ea
              ON ea.exam_session_id = es.id AND ea.question_id = qb.id
            WHERE es.id = ? AND es.candidate_id = ?
            ORDER BY epq.sort_order, qb.id
            """,
            (session_id, candidate_id),
        )
        result: list[dict[str, object]] = []
        for question in questions:
            options = db.fetchall(
                """
                SELECT id, content, sort_order
                FROM question_options
                WHERE question_id = ?
                ORDER BY sort_order, id
                """,
                (question["id"],),
            )
            result.append(
                {
                    **dict(question),
                    "options": [dict(option) for option in options],
                }
            )
        return result

    def save_candidate_answer(
        self,
        session_id: int,
        candidate_id: int,
        question_id: int,
        selected_option_id: int,
    ) -> Record | None:
        connection = db.get_connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            valid = connection.execute(
                """
                SELECT 1
                FROM exam_sessions es
                JOIN recruitment_invitations ri ON ri.exam_session_id = es.id
                JOIN exam_paper_questions epq ON epq.exam_paper_id = es.exam_paper_id
                JOIN question_options qo
                  ON qo.question_id = epq.question_id AND qo.id = ?
                WHERE es.id = ? AND es.candidate_id = ?
                  AND es.status = 'in_progress'
                  AND ri.candidate_id = ? AND ri.status = 'accepted'
                  AND epq.question_id = ?
                """,
                (
                    selected_option_id,
                    session_id,
                    candidate_id,
                    candidate_id,
                    question_id,
                ),
            ).fetchone()
            if valid is None:
                connection.rollback()
                return None
            existing = connection.execute(
                """
                SELECT id FROM exam_answers
                WHERE exam_session_id = ? AND question_id = ?
                """,
                (session_id, question_id),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO exam_answers
                        (exam_session_id, question_id, selected_option_id)
                    VALUES (?, ?, ?)
                    """,
                    (session_id, question_id, selected_option_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE exam_answers SET selected_option_id = ?
                    WHERE id = ?
                    """,
                    (selected_option_id, existing["id"]),
                )
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise
        return self._record(
            db.fetchone(
                """
                SELECT id, exam_session_id, question_id, selected_option_id
                FROM exam_answers
                WHERE exam_session_id = ? AND question_id = ?
                """,
                (session_id, question_id),
            )
        )

    def get_grading_questions(self, session_id: int) -> Sequence[Record]:
        questions = db.fetchall(
            """
            SELECT qb.id, COALESCE(epq.points, qb.points) AS points
            FROM exam_sessions es
            JOIN exam_paper_questions epq ON epq.exam_paper_id = es.exam_paper_id
            JOIN question_bank qb ON qb.id = epq.question_id
            WHERE es.id = ?
            ORDER BY epq.sort_order, qb.id
            """,
            (session_id,),
        )
        result: list[dict[str, object]] = []
        for question in questions:
            options = db.fetchall(
                """
                SELECT id, is_correct
                FROM question_options
                WHERE question_id = ?
                ORDER BY sort_order, id
                """,
                (question["id"],),
            )
            result.append(
                {
                    **dict(question),
                    "options": [dict(option) for option in options],
                }
            )
        return result

    def get_candidate_answers(
        self, session_id: int, candidate_id: int
    ) -> Sequence[Record]:
        return [
            dict(row)
            for row in db.fetchall(
                """
                SELECT ea.question_id, ea.selected_option_id
                FROM exam_answers ea
                JOIN exam_sessions es ON es.id = ea.exam_session_id
                JOIN recruitment_invitations ri ON ri.exam_session_id = es.id
                WHERE es.id = ? AND es.candidate_id = ?
                  AND ri.candidate_id = ? AND ri.status = 'accepted'
                """,
                (session_id, candidate_id, candidate_id),
            )
        ]

    def complete_session_once(
        self,
        session_id: int,
        candidate_id: int,
        *,
        score: float,
        max_score: float,
        question_scores: Sequence[Mapping[str, int | float]],
    ) -> tuple[bool, Record | None]:
        connection = db.get_connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            session = connection.execute(
                """
                SELECT es.*, ri.id AS invitation_id
                FROM exam_sessions es
                JOIN recruitment_invitations ri ON ri.exam_session_id = es.id
                WHERE es.id = ? AND es.candidate_id = ?
                  AND ri.candidate_id = ? AND ri.status = 'accepted'
                """,
                (session_id, candidate_id, candidate_id),
            ).fetchone()
            if session is None or session["status"] != "in_progress":
                connection.rollback()
                return False, self._record(session)

            updated = connection.execute(
                """
                UPDATE exam_sessions
                SET status = 'completed',
                    completed_at = datetime('now','localtime'),
                    total_score = ?,
                    max_score = ?
                WHERE id = ? AND candidate_id = ? AND status = 'in_progress'
                """,
                (score, max_score, session_id, candidate_id),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return False, self._record(
                    connection.execute(
                        "SELECT * FROM exam_sessions WHERE id = ?",
                        (session_id,),
                    ).fetchone()
                )

            for item in question_scores:
                question_id = item.get("question_id")
                question_score = item.get("score")
                question_max = item.get("max_score")
                if (
                    isinstance(question_id, bool)
                    or not isinstance(question_id, int)
                    or isinstance(question_score, bool)
                    or not isinstance(question_score, (int, float))
                    or isinstance(question_max, bool)
                    or not isinstance(question_max, (int, float))
                ):
                    raise sqlite3.IntegrityError("Invalid computed exam grade.")
                connection.execute(
                    """
                    UPDATE exam_answers
                    SET score = ?, max_score = ?, is_graded = 1,
                        graded_at = datetime('now','localtime')
                    WHERE exam_session_id = ? AND question_id = ?
                    """,
                    (question_score, question_max, session_id, question_id),
                )

            connection.execute(
                """
                INSERT INTO recruitment_submissions
                    (invitation_id, exam_session_id, candidate_id, company_id,
                     exam_paper_id)
                SELECT ri.id, ri.exam_session_id, ri.candidate_id, ri.company_id,
                       ri.exam_paper_id
                FROM recruitment_invitations ri
                WHERE ri.id = ? AND ri.status = 'accepted'
                """,
                (session["invitation_id"],),
            )
            connection.execute(
                """
                UPDATE recruitment_submissions
                SET status = 'grading'
                WHERE exam_session_id = ? AND candidate_id = ?
                  AND status = 'submitted'
                """,
                (session_id, candidate_id),
            )
            connection.execute(
                """
                UPDATE recruitment_submissions
                SET status = 'graded', graded_at = datetime('now','localtime')
                WHERE exam_session_id = ? AND candidate_id = ?
                  AND status = 'grading'
                """,
                (session_id, candidate_id),
            )
            submission = connection.execute(
                """
                SELECT * FROM recruitment_submissions
                WHERE exam_session_id = ? AND candidate_id = ?
                """,
                (session_id, candidate_id),
            ).fetchone()
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise
        return True, self._record(submission)

    def get_candidate_result(
        self, session_id: int, candidate_id: int
    ) -> Record | None:
        return self._record(
            db.fetchone(
                """
                SELECT es.id AS exam_session_id,
                       es.total_score,
                       es.max_score,
                       rs.status AS submission_status,
                       rs.submitted_at,
                       rs.graded_at,
                       rs.released_at
                FROM exam_sessions es
                JOIN recruitment_submissions rs ON rs.exam_session_id = es.id
                WHERE es.id = ? AND rs.candidate_id = ?
                  AND rs.status = 'released'
                """,
                (session_id, candidate_id),
            )
        )

    def get_candidate_submission(
        self, session_id: int, candidate_id: int
    ) -> Record | None:
        return self._record(
            db.fetchone(
                """
                SELECT id, invitation_id, exam_session_id, candidate_id,
                       company_id, exam_paper_id, status, submitted_at,
                       graded_at, released_at
                FROM recruitment_submissions
                WHERE exam_session_id = ? AND candidate_id = ?
                """,
                (session_id, candidate_id),
            )
        )
