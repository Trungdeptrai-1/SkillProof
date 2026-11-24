"""Typed View contracts for recruitment APIs that are not implemented yet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class ListResult(Generic[T]):
    success: bool
    items: tuple[T, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class ActionResult:
    success: bool
    message: str = ""


@dataclass(frozen=True)
class Position:
    id: int
    title: str
    location: str
    status: str
    description: str = ""
    requirements: str = ""


@dataclass(frozen=True)
class Assessment:
    id: int
    title: str
    duration_minutes: int
    question_count: int


@dataclass(frozen=True)
class QuestionDraft:
    prompt: str
    options: tuple[str, ...]
    correct_option_index: int


@dataclass(frozen=True)
class Candidate:
    id: int
    full_name: str
    email: str


@dataclass(frozen=True)
class QuestionAuthor:
    id: int
    full_name: str
    email: str


@dataclass(frozen=True)
class AssessmentResultRow:
    candidate_name: str
    position_title: str
    assessment_title: str
    score: float | None
    max_score: float | None
    status: str
    submitted_at: str
    exam_id: int = 0
    invitation_id: int = 0


@dataclass(frozen=True)
class CandidateInvitation:
    id: int
    company_name: str
    position_title: str
    assessment_title: str
    duration_minutes: int
    status: str
    scheduled_at: str = ""


@dataclass(frozen=True)
class ExamOption:
    id: int
    text: str


@dataclass(frozen=True)
class ExamQuestion:
    id: int
    prompt: str
    options: tuple[ExamOption, ...]
    selected_option_id: int | None = None


@dataclass(frozen=True)
class ExamDetails:
    invitation_id: int
    title: str
    duration_minutes: int
    questions: tuple[ExamQuestion, ...]


@dataclass(frozen=True)
class CandidateResult:
    invitation_id: int
    score: float | None
    max_score: float | None
    status: str
    submitted_at: str = ""
    message: str = ""


@dataclass(frozen=True)
class ExamLoadResult:
    success: bool
    exam: ExamDetails | None = None
    message: str = ""


@dataclass(frozen=True)
class CandidateResultResponse:
    success: bool
    result: CandidateResult | None = None
    message: str = ""


@dataclass(frozen=True)
class SubmitResult:
    success: bool
    result: CandidateResult | None = None
    message: str = ""


class CompanyRecruitmentController(Protocol):
    """Expected API for Company hiring and assessment workflows."""

    def list_positions(self) -> ListResult[Position]: ...

    def create_position(
        self,
        title: str,
        description: str,
        requirements: str,
        location: str,
        status: str,
    ) -> ActionResult: ...

    def update_position(
        self,
        position_id: int,
        title: str,
        description: str,
        requirements: str,
        location: str,
        status: str,
    ) -> ActionResult: ...

    def list_assessments(self) -> ListResult[Assessment]: ...

    def list_contracted_experts(self) -> ListResult[QuestionAuthor]: ...

    def create_assessment(
        self,
        title: str,
        description: str,
        duration_minutes: int,
        questions: tuple[QuestionDraft, ...],
        *,
        expert_id: int,
    ) -> ActionResult: ...

    def list_candidates(self, search: str = "") -> ListResult[Candidate]: ...

    def send_invitation(
        self, position_id: int, assessment_id: int, candidate_id: int
    ) -> ActionResult: ...

    def list_results(self) -> ListResult[AssessmentResultRow]: ...

    def release_results(self, exam_id: int) -> ActionResult: ...


class CandidateAssessmentController(Protocol):
    """Expected API for Candidate invitations, exam attempts, and results."""

    def list_invitations(self) -> ListResult[CandidateInvitation]: ...

    def get_exam(self, invitation_id: int) -> ExamLoadResult: ...

    def save_answer(
        self, invitation_id: int, question_id: int, option_id: int
    ) -> ActionResult: ...

    def submit_exam(self, invitation_id: int) -> SubmitResult: ...

    def get_result(self, invitation_id: int) -> CandidateResultResponse: ...
