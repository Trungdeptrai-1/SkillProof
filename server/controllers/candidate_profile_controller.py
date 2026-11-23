"""Controller for the signed-in candidate's profile."""

from __future__ import annotations

from server.services.candidate_profile_service import (
    CandidateProfileResult,
    CandidateProfileService,
    candidate_profile_service,
)


class CandidateProfileController:
    """Validate profile request shapes and delegate business rules to service."""

    def __init__(self, service: CandidateProfileService | None = None) -> None:
        self._service = service if service is not None else candidate_profile_service

    def get_profile(self) -> CandidateProfileResult:
        return self._service.get_profile()

    def create_profile(
        self,
        headline: str = "",
        bio: str = "",
        portfolio_url: str = "",
        years_experience: int | None = None,
    ) -> CandidateProfileResult:
        invalid = self._validate_profile_input(
            headline, bio, portfolio_url, years_experience
        )
        if invalid is not None:
            return invalid
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
        invalid = self._validate_profile_input(
            headline, bio, portfolio_url, years_experience
        )
        if invalid is not None:
            return invalid
        return self._service.update_profile(
            headline, bio, portfolio_url, years_experience
        )

    def save_cv(self, source_file_path: str) -> CandidateProfileResult:
        if not isinstance(source_file_path, str) or not source_file_path.strip():
            return CandidateProfileResult(CandidateProfileResult.INVALID_INPUT)
        return self._service.save_cv(source_file_path)

    def get_cv_path(self) -> str | None:
        return self._service.get_cv_path()

    @staticmethod
    def _validate_profile_input(
        headline: str,
        bio: str,
        portfolio_url: str,
        years_experience: int | None,
    ) -> CandidateProfileResult | None:
        if not all(
            isinstance(value, str)
            for value in (headline, bio, portfolio_url)
        ):
            return CandidateProfileResult(CandidateProfileResult.INVALID_INPUT)
        if years_experience is not None and (
            isinstance(years_experience, bool)
            or not isinstance(years_experience, int)
        ):
            return CandidateProfileResult(CandidateProfileResult.INVALID_INPUT)
        if years_experience is not None and years_experience < 0:
            return CandidateProfileResult(CandidateProfileResult.INVALID_YEARS)
        return None
