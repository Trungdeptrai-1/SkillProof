"""Data Transfer Objects for recruitment, exams, submissions, and results."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Literal


JobPostingStatus = Literal["draft", "published", "closed"]
InvitationStatus = Literal[
    "pending", "accepted", "declined", "cancelled", "expired"
]
SubmissionStatus = Literal["submitted", "grading", "graded", "released"]


@dataclass(frozen=True, slots=True)
class JobPostingModel:
    id: int
    company_id: int
    title: str
    description: str | None
    requirements: str | None
    location: str | None
    status: JobPostingStatus
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> JobPostingModel:
        return cls(
            id=row["id"],
            company_id=row["company_id"],
            title=row["title"],
            description=row["description"],
            requirements=row["requirements"],
            location=row["location"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True, slots=True)
class ExamPaperModel:
    id: int
    title: str
    description: str | None
    skill_id: int | None
    created_by: int
    total_points: float
    duration_min: int
    is_published: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamPaperModel:
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            skill_id=row["skill_id"],
            created_by=row["created_by"],
            total_points=float(row["total_points"]),
            duration_min=row["duration_min"],
            is_published=bool(row["is_published"]),
        )


@dataclass(frozen=True, slots=True)
class ExamQuestionModel:
    """Candidate-safe exam question; intentionally omits answer-key fields."""

    exam_paper_id: int
    question_id: int
    skill_id: int | None
    title: str
    content: str
    question_type: str
    difficulty: str
    points: float
    sort_order: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamQuestionModel:
        return cls(
            exam_paper_id=row["exam_paper_id"],
            question_id=row["question_id"],
            skill_id=row["skill_id"],
            title=row["title"],
            content=row["content"],
            question_type=row["question_type"],
            difficulty=row["difficulty"],
            points=float(row["points"]),
            sort_order=row["sort_order"],
        )


@dataclass(frozen=True, slots=True)
class QuestionOptionModel:
    """Candidate-safe option; deliberately does not expose ``is_correct``."""

    id: int
    question_id: int
    content: str
    sort_order: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> QuestionOptionModel:
        return cls(
            id=row["id"],
            question_id=row["question_id"],
            content=row["content"],
            sort_order=row["sort_order"],
        )


@dataclass(frozen=True, slots=True)
class RecruitmentInvitationModel:
    id: int
    job_posting_id: int
    company_id: int
    candidate_id: int
    exam_paper_id: int
    exam_session_id: int | None
    status: InvitationStatus
    invited_at: str
    responded_at: str | None
    expires_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> RecruitmentInvitationModel:
        return cls(
            id=row["id"],
            job_posting_id=row["job_posting_id"],
            company_id=row["company_id"],
            candidate_id=row["candidate_id"],
            exam_paper_id=row["exam_paper_id"],
            exam_session_id=row["exam_session_id"],
            status=row["status"],
            invited_at=row["invited_at"],
            responded_at=row["responded_at"],
            expires_at=row["expires_at"],
        )


@dataclass(frozen=True, slots=True)
class ExamSessionModel:
    id: int
    exam_paper_id: int
    candidate_id: int
    company_id: int | None
    status: str
    scheduled_at: str | None
    started_at: str | None
    completed_at: str | None
    max_score: float
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamSessionModel:
        return cls(
            id=row["id"],
            exam_paper_id=row["exam_paper_id"],
            candidate_id=row["candidate_id"],
            company_id=row["company_id"],
            status=row["status"],
            scheduled_at=row["scheduled_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            max_score=float(row["max_score"]),
            created_at=row["created_at"],
        )


@dataclass(frozen=True, slots=True)
class ExamAnswerModel:
    """Candidate answer data only; scores and grader feedback are excluded."""

    id: int
    exam_session_id: int
    question_id: int
    answer_text: str | None
    answer_code: str | None
    selected_option_id: int | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamAnswerModel:
        return cls(
            id=row["id"],
            exam_session_id=row["exam_session_id"],
            question_id=row["question_id"],
            answer_text=row["answer_text"],
            answer_code=row["answer_code"],
            selected_option_id=row["selected_option_id"],
        )


@dataclass(frozen=True, slots=True)
class RecruitmentSubmissionModel:
    id: int
    invitation_id: int
    exam_session_id: int
    candidate_id: int
    company_id: int
    exam_paper_id: int
    status: SubmissionStatus
    submitted_at: str
    graded_at: str | None
    released_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> RecruitmentSubmissionModel:
        return cls(
            id=row["id"],
            invitation_id=row["invitation_id"],
            exam_session_id=row["exam_session_id"],
            candidate_id=row["candidate_id"],
            company_id=row["company_id"],
            exam_paper_id=row["exam_paper_id"],
            status=row["status"],
            submitted_at=row["submitted_at"],
            graded_at=row["graded_at"],
            released_at=row["released_at"],
        )


@dataclass(frozen=True, slots=True)
class CandidateExamResultModel:
    """Candidate-visible score, available only after explicit result release."""

    exam_session_id: int
    score: float
    max_score: float
    graded_at: str
    released_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CandidateExamResultModel:
        if row["submission_status"] != "released":
            raise ValueError("Candidate results are available only after release.")
        if row["total_score"] is None:
            raise ValueError("A released result must have a total score.")
        if row["graded_at"] is None or row["released_at"] is None:
            raise ValueError("A released result must include grading and release times.")
        return cls(
            exam_session_id=row["exam_session_id"],
            score=float(row["total_score"]),
            max_score=float(row["max_score"]),
            graded_at=row["graded_at"],
            released_at=row["released_at"],
        )
