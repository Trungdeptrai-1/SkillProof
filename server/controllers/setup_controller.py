"""Controller for first-run administrator setup."""

from __future__ import annotations

from server.services.setup_service import AdminSetupResult, AdminSetupService


class SetupController:
    def __init__(self, service: AdminSetupService | None = None) -> None:
        self._service = service if service is not None else AdminSetupService()

    def create_admin(
        self,
        full_name: str,
        email: str,
        password: str,
        confirm_password: str,
    ) -> AdminSetupResult:
        return self._service.create_admin(
            full_name, email, password, confirm_password
        )
