"""Controller for login and logout requests."""

from __future__ import annotations

from server.services.auth_service import AuthService, LoginResult, auth_service


class AuthController:
    """Forward authentication requests to the authentication service."""

    def __init__(self, service: AuthService | None = None) -> None:
        self._service = service if service is not None else auth_service

    def login(self, email: str, password: str) -> LoginResult:
        """Authenticate the user and return the service result unchanged."""
        return self._service.login(email, password)

    def logout(self) -> None:
        """End the current user session."""
        self._service.logout()
