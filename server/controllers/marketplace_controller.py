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

    def withdraw(self, application_id: int) -> MarketplaceResult:
        return self._service.withdraw(application_id)

    def save_job(self, job_id: int) -> MarketplaceResult:
        return self._service.save_job(job_id)

    def unsave_job(self, job_id: int) -> MarketplaceResult:
        return self._service.unsave_job(job_id)

    def set_discoverable(self, visible: bool) -> MarketplaceResult:
        return self._service.set_discoverable(visible)

    # Company actions
    def discover_candidates(self, search: str = "") -> MarketplaceResult:
        return self._service.discover_candidates(search)

    def applicants(self, job_id: int) -> MarketplaceResult:
        return self._service.applicants(job_id)

    def update_application_status(self, application_id: int, status: str) -> MarketplaceResult:
        return self._service.update_application_status(application_id, status)
