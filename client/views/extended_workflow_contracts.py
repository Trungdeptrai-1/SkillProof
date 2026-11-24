"""Typed View contracts for workflows awaiting real backend Controllers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class WorkflowListResult(Generic[T]):
    success: bool
    items: tuple[T, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class WorkflowActionResult:
    success: bool
    message: str = ""
    status: str = ""


@dataclass(frozen=True)
class CandidateSpecializedAssessment:
    id: int
    title: str
    kind: Literal["essay", "coding"]
    prompt: str
    status: str
    duration_minutes: int = 0
    input_description: str = ""
    output_description: str = ""
    public_test_cases: tuple[str, ...] = ()
    supported_languages: tuple[str, ...] = ()
    saved_answer: str = ""
    saved_language: str = ""


@dataclass(frozen=True)
class CandidatePublishedResult:
    success: bool
    released: bool = False
    score: float | None = None
    max_score: float | None = None
    feedback: str = ""
    message: str = ""


class CandidateSpecializedAssessmentController(Protocol):
    """Candidate-safe essay/coding API; must not return hidden test cases."""

    def list_assignments(self) -> WorkflowListResult[CandidateSpecializedAssessment]: ...

    def save_answer(
        self, assignment_id: int, answer: str, language: str
    ) -> WorkflowActionResult: ...

    def submit_answer(
        self, assignment_id: int, answer: str, language: str
    ) -> WorkflowActionResult: ...

    def get_result(self, assignment_id: int) -> CandidatePublishedResult: ...


@dataclass(frozen=True)
class PendingGradingSubmission:
    id: int
    candidate_name: str
    assessment_title: str
    kind: Literal["essay", "coding"]
    prompt: str
    submitted_answer: str
    status: str
    max_score: float
    language: str = ""
    feedback: str = ""
    score: float | None = None


class ManualGradingController(Protocol):
    """Include submitted items and graded items awaiting result release."""

    def list_submissions_for_grading(
        self,
    ) -> WorkflowListResult[PendingGradingSubmission]: ...

    def save_grade(
        self, submission_id: int, score: float, feedback: str
    ) -> WorkflowActionResult: ...

    def release_result(self, submission_id: int) -> WorkflowActionResult: ...


@dataclass(frozen=True)
class ActiveExamSession:
    id: int
    title: str
    status: str
    remaining_seconds: int


class ExamMonitorController(Protocol):
    """API to resolve the authenticated user's active exam session."""

    def get_active_session(self) -> ActiveExamSession | None: ...


@dataclass(frozen=True)
class InterviewEntry:
    id: int
    title: str
    candidate_name: str
    scheduled_at: str
    status: str
    meeting_url: str = ""
    evaluation_notes: str = ""


class InterviewController(Protocol):
    """Role-scope records; do not expose unpublished evaluation notes to candidates."""

    def list_interviews(self) -> WorkflowListResult[InterviewEntry]: ...

    def save_evaluation(
        self, interview_id: int, notes: str
    ) -> WorkflowActionResult: ...


@dataclass(frozen=True)
class CertificateEntry:
    id: int
    cert_code: str
    subject_name: str
    skill_name: str
    status: str
    issued_at: str
    expires_at: str = ""
    score: float | None = None


@dataclass(frozen=True)
class CertificateVerification:
    success: bool
    certificate: CertificateEntry | None = None
    message: str = ""


@dataclass(frozen=True)
class CertificatePermissions:
    can_issue: bool = False
    can_verify: bool = False


class CertificateController(Protocol):
    """Scope listing to the authenticated user and derive action permissions server-side."""

    def get_permissions(self) -> CertificatePermissions: ...

    def list_certificates(self) -> WorkflowListResult[CertificateEntry]: ...

    def issue_certificate(
        self, user_id: int, skill_id: int, score: float | None
    ) -> WorkflowActionResult: ...

    def verify_certificate(self, cert_code: str) -> CertificateVerification: ...
