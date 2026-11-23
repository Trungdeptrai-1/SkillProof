"""Tests for candidate profile request coordination."""

from unittest.mock import Mock, patch
import sqlite3

import pytest

import app.services.candidate_profile_service as legacy_profile_module
import server.services.candidate_profile_service as profile_module
from app.services.auth_service import AuthService, SessionManager
from app.services.candidate_profile_service import CandidateProfileService
from server.controllers.candidate_profile_controller import CandidateProfileController
from server.services.candidate_profile_service import CandidateProfileResult


@pytest.fixture(autouse=True)
def reset_session():
    SessionManager._instance = None
    yield
    SessionManager._instance = None


@pytest.fixture
def candidate_controller(fresh_db, candidate_user):
    email, password = candidate_user
    login_result = AuthService().login(email, password)
    assert login_result.success
    yield CandidateProfileController(CandidateProfileService())
    SessionManager.instance().end_session()


def test_legacy_import_path_uses_canonical_service():
    assert legacy_profile_module.CandidateProfileService is CandidateProfileService
    assert (
        legacy_profile_module.candidate_profile_service
        is profile_module.candidate_profile_service
    )


def test_get_and_update_candidate_profile(candidate_controller):
    created = candidate_controller.create_profile(
        "Python Developer", "Backend engineer", "https://example.com", 4
    )
    updated = candidate_controller.update_profile(
        "Senior Python Developer", "Experienced backend engineer", "", 5
    )

    assert created.success
    assert updated.success
    assert updated.profile.headline == "Senior Python Developer"
    assert updated.profile.years_experience == 5


def test_missing_profile_returns_not_found(candidate_controller):
    result = candidate_controller.get_profile()

    assert result.status == CandidateProfileResult.NOT_FOUND
    assert result.profile is None


@pytest.mark.parametrize(
    ("kwargs", "expected_status"),
    [
        ({"headline": None}, CandidateProfileResult.INVALID_INPUT),
        ({"bio": 10}, CandidateProfileResult.INVALID_INPUT),
        ({"portfolio_url": []}, CandidateProfileResult.INVALID_INPUT),
        ({"years_experience": True}, CandidateProfileResult.INVALID_INPUT),
        ({"years_experience": -1}, CandidateProfileResult.INVALID_YEARS),
    ],
)
def test_invalid_profile_input_is_rejected(candidate_controller, kwargs, expected_status):
    result = candidate_controller.update_profile(**kwargs)

    assert result.status == expected_status


def test_profile_controller_preserves_service_database_errors(candidate_controller):
    with patch.object(
        profile_module.db,
        "fetchone",
        side_effect=sqlite3.OperationalError("database unavailable"),
    ):
        result = candidate_controller.get_profile()

    assert result.status == CandidateProfileResult.DB_ERROR
    assert not result.success


def test_profile_controller_does_not_hide_unexpected_service_errors():
    service = Mock(spec=CandidateProfileService)
    service.get_profile.side_effect = RuntimeError("service failed")

    with pytest.raises(RuntimeError, match="service failed"):
        CandidateProfileController(service).get_profile()


def test_other_role_is_rejected_by_service(fresh_db, admin_user):
    email, password = admin_user
    assert AuthService().login(email, password).success

    result = CandidateProfileController(CandidateProfileService()).get_profile()

    assert result.status == CandidateProfileResult.WRONG_ROLE
