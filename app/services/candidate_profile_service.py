"""Backward-compatible imports for candidate profile operations."""

from server.services.candidate_profile_service import (
    ALLOWED_CV_EXTENSIONS,
    MAX_CV_SIZE,
    CandidateProfileModel,
    CandidateProfileResult,
    CandidateProfileService,
    candidate_profile_service,
)

__all__ = [
    "ALLOWED_CV_EXTENSIONS",
    "MAX_CV_SIZE",
    "CandidateProfileModel",
    "CandidateProfileResult",
    "CandidateProfileService",
    "candidate_profile_service",
]
