"""PySide6-facing Controller for two-way job marketplace workflows."""
from __future__ import annotations

from server.services.marketplace_service import MarketplaceResult, MarketplaceService


class MarketplaceController:
    def __init__(self, service: MarketplaceService | None = None) -> None:
        self._service = service if service is not None else MarketplaceService()

    # Candidate actions
    def browse_jobs(self, search: str = "", location: str = "") -> MarketplaceResult:
        return self._service.browse_jobs(search, location)

    def apply(self, job_id: int, cover_letter: str = "") -> MarketplaceResult:
        return self._service.apply(job_id, cover_letter)

    def my_applications(self) -> MarketplaceResult:
        return self._service.my_applications()

    def saved_jobs(self) -> MarketplaceResult:
        return self._service.saved_jobs()

    def withdraw(self, application_id: int) -> MarketplaceResult:
        return self._service.withdraw(application_id)

    def save_job(self, job_id: int) -> MarketplaceResult:
        return self._service.save_job(job_id)

    def unsave_job(self, job_id: int) -> MarketplaceResult:
        return self._service.unsave_job(job_id)

    def get_discoverable(self) -> MarketplaceResult:
        return self._service.get_discoverable()

    def set_discoverable(self, visible: bool) -> MarketplaceResult:
        return self._service.set_discoverable(visible)

    # Company actions
    def discover_candidates(self, search: str = "") -> MarketplaceResult:
        return self._service.discover_candidates(search)

    def applicants(self, job_id: int) -> MarketplaceResult:
        return self._service.applicants(job_id)

    def update_application_status(self, application_id: int, status: str) -> MarketplaceResult:
        return self._service.update_application_status(application_id, status)

    def list_assessment_exams(self) -> MarketplaceResult:
        return self._service.list_assessment_exams()

    def invite_applicant_to_exam(self, application_id: int, exam_id: int) -> MarketplaceResult:
        return self._service.invite_applicant_to_exam(application_id, exam_id)

    def schedule_application_interview(
        self, application_id: int, title: str, scheduled_at: str,
        description: str = "", duration_min: int = 60,
        meeting_url: str | None = None,
    ) -> MarketplaceResult:
        return self._service.schedule_application_interview(
            application_id, title, scheduled_at, description, duration_min, meeting_url
        )

    def decide_after_interview(
        self, application_id: int, decision: str, note: str = ""
    ) -> MarketplaceResult:
        return self._service.decide_after_interview(application_id, decision, note)
