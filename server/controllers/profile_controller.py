"""Controllers for candidate, company, and expert profile use cases."""

from __future__ import annotations

from app.services.candidate_profile_service import (
    CandidateProfileModel,
    CandidateProfileResult,
    CandidateProfileService,
)
from app.services.company_profile_service import (
    CompanyProfileModel,
    CompanyProfileService,
    ProfileResult,
)
from app.services.expert_profile_service import (
    ExpertProfileModel,
    ExpertProfileResult,
    ExpertProfileService,
)


class CandidateProfileController:
    def __init__(self, service: CandidateProfileService | None = None) -> None:
        self._service = service if service is not None else CandidateProfileService()

    def get_profile(self) -> CandidateProfileResult:
        return self._service.get_profile()

    def create_profile(
        self,
        headline: str = "",
        bio: str = "",
        portfolio_url: str = "",
        years_experience: int | None = None,
    ) -> CandidateProfileResult:
        return self._service.create_profile(
            headline, bio, portfolio_url, years_experience
        )

    def update_profile(
        self,
        headline: str = "",
        bio: str = "",
        portfolio_url: str = "",
        years_experience: int | None = None,
    ) -> CandidateProfileResult:
        return self._service.update_profile(
            headline, bio, portfolio_url, years_experience
        )

    def save_cv(self, source_file_path: str) -> CandidateProfileResult:
        return self._service.save_cv(source_file_path)

    def get_cv_path(self) -> str | None:
        return self._service.get_cv_path()


class CompanyProfileController:
    def __init__(self, service: CompanyProfileService | None = None) -> None:
        self._service = service if service is not None else CompanyProfileService()

    def get_profile(self) -> ProfileResult:
        return self._service.get_profile()

    def create_profile(
        self,
        company_name: str,
        industry: str = "",
        website: str = "",
        description: str = "",
        tax_code: str = "",
        address: str = "",
    ) -> ProfileResult:
        return self._service.create_profile(
            company_name, industry, website, description, tax_code, address
        )

    def update_profile(
        self,
        company_name: str,
        industry: str = "",
        website: str = "",
        description: str = "",
        tax_code: str = "",
        address: str = "",
    ) -> ProfileResult:
        return self._service.update_profile(
            company_name, industry, website, description, tax_code, address
        )


class ExpertProfileController:
    def __init__(self, service: ExpertProfileService | None = None) -> None:
        self._service = service if service is not None else ExpertProfileService()

    def get_profile(self) -> ExpertProfileResult:
        return self._service.get_profile()

    def create_profile(
        self,
        title: str,
        bio: str = "",
        specialization: str = "",
        hourly_rate: float | None = None,
        availability: str = "available",
    ) -> ExpertProfileResult:
        return self._service.create_profile(
            title, bio, specialization, hourly_rate, availability
        )

    def update_profile(
        self,
        title: str,
        bio: str = "",
        specialization: str = "",
        hourly_rate: float | None = None,
        availability: str = "available",
    ) -> ExpertProfileResult:
        return self._service.update_profile(
            title, bio, specialization, hourly_rate, availability
        )
