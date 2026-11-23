"""Tests for user registration request coordination."""

from unittest.mock import Mock

import pytest

import app.services.user_service as legacy_user_module
import server.services.user_service as user_module
from app.services.user_service import UserService
from server.controllers.user_controller import UserController
from server.services.user_service import RegisterResult


def test_legacy_import_path_uses_canonical_service():
    assert legacy_user_module.UserService is UserService
    assert legacy_user_module.user_service is user_module.user_service


def test_register_request_is_forwarded_to_service():
    expected = RegisterResult(RegisterResult.EMPTY_EMAIL)
    service = Mock(spec=UserService)
    service.register.return_value = expected

    result = UserController(service).register(
        "Candidate", "candidate@example.com", "Password1", "Password1"
    )

    assert result is expected
    service.register.assert_called_once_with(
        "Candidate", "candidate@example.com", "Password1", "Password1"
    )


def test_non_string_registration_fields_are_rejected():
    service = Mock(spec=UserService)

    result = UserController(service).register(
        None, "candidate@example.com", "Password1", "Password1"
    )

    assert result.status == RegisterResult.INVALID_INPUT
    service.register.assert_not_called()


def test_registration_uses_existing_service_validation(fresh_db):
    result = UserController(UserService()).register(
        "Candidate", "invalid-email", "Password1", "Password1"
    )

    assert result.status == RegisterResult.INVALID_EMAIL_FORMAT
    assert not result.success


def test_registration_service_errors_are_not_silenced():
    service = Mock(spec=UserService)
    service.register.side_effect = RuntimeError("service failed")

    with pytest.raises(RuntimeError, match="service failed"):
        UserController(service).register(
            "Candidate", "candidate@example.com", "Password1", "Password1"
        )
