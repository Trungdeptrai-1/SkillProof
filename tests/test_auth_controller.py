"""Tests for the authentication controller and its service integration."""

from unittest.mock import Mock, patch

import pytest

import app.services.auth_service as legacy_auth_module
import server.services.auth_service as server_auth_module
from app.services.auth_service import AuthService as LegacyAuthService
from app.services.auth_service import LoginResult as LegacyLoginResult
from app.services.auth_service import SessionManager as LegacySessionManager
from server.controllers.auth_controller import AuthController
from server.services.auth_service import AuthService, LoginResult, SessionManager


@pytest.fixture(autouse=True)
def reset_session():
    SessionManager._instance = None
    yield
    SessionManager._instance = None


def test_legacy_import_path_reexports_canonical_implementation():
    assert LegacyAuthService is AuthService
    assert LegacyLoginResult is LoginResult
    assert LegacySessionManager is SessionManager
    assert legacy_auth_module.auth_service is server_auth_module.auth_service


def test_controller_forwards_login_and_returns_service_result():
    expected = LoginResult(LoginResult.INVALID_EMAIL_FORMAT)
    service = Mock(spec=AuthService)
    service.login.return_value = expected

    result = AuthController(service).login("invalid", "password")

    assert result is expected
    service.login.assert_called_once_with("invalid", "password")


def test_login_success_creates_session_and_controller_logs_out(fresh_db, candidate_user):
    email, password = candidate_user
    controller = AuthController(AuthService())

    result = controller.login(email, password)

    assert result.success
    assert SessionManager.instance().current_user == result.user
    controller.logout()
    assert not SessionManager.instance().is_logged_in


def test_invalid_credentials_do_not_create_session(fresh_db, admin_user):
    email, _ = admin_user
    controller = AuthController(AuthService())

    invalid_email = controller.login("not-an-email", "password")
    wrong_password = controller.login(email, "incorrect-password")

    assert invalid_email.status == LoginResult.INVALID_EMAIL_FORMAT
    assert wrong_password.status == LoginResult.WRONG_PASSWORD
    assert not SessionManager.instance().is_logged_in


def test_service_database_error_is_returned_to_caller(fresh_db):
    controller = AuthController(AuthService())
    with patch.object(
        server_auth_module.db,
        "fetchone",
        side_effect=RuntimeError("database unavailable"),
    ):
        result = controller.login("user@example.com", "password")

    assert result.status == LoginResult.DB_ERROR
    assert not result.success


def test_controller_does_not_hide_unexpected_service_errors():
    service = Mock(spec=AuthService)
    service.login.side_effect = RuntimeError("service failed")

    with pytest.raises(RuntimeError, match="service failed"):
        AuthController(service).login("user@example.com", "password")
