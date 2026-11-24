"""Data Transfer Objects for recruitment, exams, submissions, and results."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
from collections.abc import Mapping
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
    supported_languages: tuple[str, ...] = ()

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamQuestionModel:
        languages = ()
        if "supported_languages" in row.keys() and row["supported_languages"]:
            try:
                parsed_languages = json.loads(row["supported_languages"])
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid supported coding languages.") from exc
            if not isinstance(parsed_languages, list) or any(
                not isinstance(language, str) for language in parsed_languages
            ):
                raise ValueError("Supported coding languages must be a list of text.")
            languages = tuple(parsed_languages)
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
            supported_languages=languages,
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
    programming_language: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamAnswerModel:
        return cls(
            id=row["id"],
            exam_session_id=row["exam_session_id"],
            question_id=row["question_id"],
            answer_text=row["answer_text"],
            answer_code=row["answer_code"],
            selected_option_id=row["selected_option_id"],
            programming_language=row["programming_language"],
        )


@dataclass(frozen=True, slots=True)
class ExamAnswerGradingModel:
    id: int
    exam_session_id: int
    question_id: int
    candidate_id: int
    company_id: int
    exam_paper_id: int
    answer_text: str | None
    answer_code: str | None
    selected_option_id: int | None
    programming_language: str | None
    score: float | None
    max_score: float
    feedback: str | None
    graded_by: int | None
    graded_at: str | None
    is_graded: bool
    grading_mode: str
    test_results: list[dict[str, object]] | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamAnswerGradingModel:
        raw_results = row["test_results_json"]
        test_results = None
        if raw_results is not None:
            try:
                parsed_results = json.loads(raw_results)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid stored coding test results.") from exc
            if not isinstance(parsed_results, list) or any(
                not isinstance(result, dict) for result in parsed_results
            ):
                raise ValueError("Coding test results must be a list of objects.")
            test_results = parsed_results
        return cls(
            id=row["id"],
            exam_session_id=row["exam_session_id"],
            question_id=row["question_id"],
            candidate_id=row["candidate_id"],
            company_id=row["company_id"],
            exam_paper_id=row["exam_paper_id"],
            answer_text=row["answer_text"],
            answer_code=row["answer_code"],
            selected_option_id=row["selected_option_id"],
            programming_language=row["programming_language"],
            score=(
                float(row["score"]) if row["score"] is not None else None
            ),
            max_score=float(row["max_score"]),
            feedback=row["feedback"],
            graded_by=row["graded_by"],
            graded_at=row["graded_at"],
            is_graded=bool(row["is_graded"]),
            grading_mode=row["grading_mode"],
            test_results=test_results,
        )


@dataclass(frozen=True, slots=True)
class ExamGradeRevisionModel:
    id: int
    exam_answer_id: int
    graded_by: int
    old_score: float | None
    new_score: float
    old_feedback: str | None
    new_feedback: str | None
    reason: str | None
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamGradeRevisionModel:
        return cls(
            id=row["id"],
            exam_answer_id=row["exam_answer_id"],
            graded_by=row["graded_by"],
            old_score=(
                float(row["old_score"]) if row["old_score"] is not None else None
            ),
            new_score=float(row["new_score"]),
            old_feedback=row["old_feedback"],
            new_feedback=row["new_feedback"],
            reason=row["reason"],
            created_at=row["created_at"],
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


@dataclass(frozen=True, slots=True)
class CodingTestCaseModel:
    input: str
    expected_output: str
    is_hidden: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> CodingTestCaseModel:
        input_value = value.get("input")
        expected_output = value.get("expected_output")
        is_hidden = value.get("is_hidden", False)
        if (
            not isinstance(input_value, str)
            or not isinstance(expected_output, str)
            or not isinstance(is_hidden, bool)
        ):
            raise ValueError("Invalid coding test case.")
        return cls(input_value, expected_output, is_hidden)

    @classmethod
    def from_json(cls, value: str) -> list[CodingTestCaseModel]:
        try:
            data = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid coding test cases.") from exc
        if not isinstance(data, list):
            raise ValueError("Coding test cases must be a list.")
        if any(not isinstance(item, Mapping) for item in data):
            raise ValueError("Invalid coding test case.")
        return [cls.from_mapping(item) for item in data]


@dataclass(frozen=True, slots=True)
class ExamSessionEventModel:
    id: int
    exam_session_id: int
    candidate_id: int
    proctoring_session_id: int | None
    event_type: str
    is_violation: bool
    details: dict[str, object] | None
    occurred_at: str
    processing_status: str
    processed_by: int | None
    processed_at: str | None
    processing_notes: str | None
    evidence_uri: str | None
    consent_for_evidence: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamSessionEventModel:
        raw_details = row["details_json"]
        details = None
        if raw_details is not None:
            try:
                details = json.loads(raw_details)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid exam event details.") from exc
            if not isinstance(details, dict):
                raise ValueError("Exam event details must be an object.")
        return cls(
            id=row["id"],
            exam_session_id=row["exam_session_id"],
            candidate_id=row["candidate_id"],
            proctoring_session_id=row["proctoring_session_id"],
            event_type=row["event_type"],
            is_violation=bool(row["is_violation"]),
            details=details,
            occurred_at=row["occurred_at"],
            processing_status=row["processing_status"],
            processed_by=row["processed_by"],
            processed_at=row["processed_at"],
            processing_notes=row["processing_notes"],
            evidence_uri=row["evidence_uri"],
            consent_for_evidence=bool(row["consent_for_evidence"]),
        )


@dataclass(frozen=True, slots=True)
class ExamProctoringSessionModel:
    id: int
    exam_session_id: int
    candidate_id: int
    consent_for_evidence: bool
    camera_status: str
    camera_status_changed_at: str | None
    recording_consent: bool
    recording_consent_at: str | None
    status: str
    started_at: str
    ended_at: str | None
    reviewed_by: int | None
    reviewed_at: str | None
    review_notes: str | None
    video_status: str
    video_created_at: str | None
    video_retention_until: str | None
    video_deleted_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ExamProctoringSessionModel:
        return cls(
            id=row["id"],
            exam_session_id=row["exam_session_id"],
            candidate_id=row["candidate_id"],
            consent_for_evidence=bool(row["consent_for_evidence"]),
            camera_status=row["camera_status"],
            camera_status_changed_at=row["camera_status_changed_at"],
            recording_consent=bool(row["recording_consent"]),
            recording_consent_at=row["recording_consent_at"],
            status=row["status"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            reviewed_by=row["reviewed_by"],
            reviewed_at=row["reviewed_at"],
            review_notes=row["review_notes"],
            video_status=row["video_status"],
            video_created_at=row["video_created_at"],
            video_retention_until=row["video_retention_until"],
            video_deleted_at=row["video_deleted_at"],
        )


@dataclass(frozen=True, slots=True)
class ProctoringVideoModel:
    exam_session_id: int
    candidate_id: int
    video_path: str | None
    video_created_at: str | None
    video_retention_until: str | None
    video_deleted_at: str | None
    video_status: str


@dataclass(frozen=True, slots=True)
class ExamProctoringPolicyModel:
    warning_threshold: int = 1
    termination_threshold: int = 3
    terminate_exam_on_threshold: bool = True
    camera_disconnect_timeout_seconds: int = 60
    video_retention_days: int = 30


@dataclass(frozen=True, slots=True)
class InterviewModel:
    id: int
    candidate_id: int
    company_id: int | None
    title: str
    description: str | None
    status: str
    scheduled_at: str
    duration_min: int
    meeting_url: str | None
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> InterviewModel:
        return cls(
            id=row["id"],
            candidate_id=row["candidate_id"],
            company_id=row["company_id"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            scheduled_at=row["scheduled_at"],
            duration_min=row["duration_min"],
            meeting_url=row["meeting_url"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True, slots=True)
class InterviewParticipantModel:
    id: int
    interview_id: int
    expert_id: int
    role: str
    joined_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> InterviewParticipantModel:
        return cls(
            id=row["id"],
            interview_id=row["interview_id"],
            expert_id=row["expert_id"],
            role=row["role"],
            joined_at=row["joined_at"],
        )


@dataclass(frozen=True, slots=True)
class InterviewEvaluationModel:
    id: int
    interview_id: int
    expert_id: int
    technical_score: int | None
    communication_score: int | None
    problem_solving_score: int | None
    overall_rating: int | None
    feedback: str | None
    recommendation: str | None
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> InterviewEvaluationModel:
        return cls(
            id=row["id"],
            interview_id=row["interview_id"],
            expert_id=row["expert_id"],
            technical_score=row["technical_score"],
            communication_score=row["communication_score"],
            problem_solving_score=row["problem_solving_score"],
            overall_rating=row["overall_rating"],
            feedback=row["feedback"],
            recommendation=row["recommendation"],
            created_at=row["created_at"],
        )
