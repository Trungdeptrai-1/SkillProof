"""Controller for user registration requests."""

from __future__ import annotations

from server.services.user_service import RegisterResult, UserService, user_service


class UserController:
    """Validate registration request types and delegate to the user service."""

    def __init__(self, service: UserService | None = None) -> None:
        self._service = service if service is not None else user_service

    def register(
        self,
        full_name: str,
        email: str,
        password: str,
        confirm_password: str,
    ) -> RegisterResult:
        if not all(
            isinstance(value, str)
            for value in (full_name, email, password, confirm_password)
        ):
            return RegisterResult(RegisterResult.INVALID_INPUT)
        return self._service.register(
            full_name, email, password, confirm_password
        )
