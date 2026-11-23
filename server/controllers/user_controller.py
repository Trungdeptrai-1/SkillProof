"""Controller for user registration."""

from __future__ import annotations

from app.services.user_service import RegisterResult, UserService


class UserController:
    """Forward registration requests from views to the user service."""

    def __init__(self, service: UserService | None = None) -> None:
        self._service = service if service is not None else UserService()

    def register(
        self,
        full_name: str,
        email: str,
        password: str,
        confirm_password: str,
    ) -> RegisterResult:
        return self._service.register(full_name, email, password, confirm_password)


user_controller = UserController()
