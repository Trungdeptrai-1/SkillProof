"""Controller for administrator account, skill, and statistics requests."""

from __future__ import annotations

from server.services.admin_service import AdminResult, AdminService, admin_service


class AdminController:
    """Validate request shapes and delegate all admin operations to the service."""

    def __init__(self, service: AdminService | None = None) -> None:
        self._service = service if service is not None else admin_service

    def list_users(
        self,
        search: str = "",
        role: str | None = None,
        is_active: bool | None = None,
    ) -> AdminResult:
        if not isinstance(search, str):
            return AdminResult(AdminResult.INVALID_INPUT)
        if role is not None and not isinstance(role, str):
            return AdminResult(AdminResult.INVALID_INPUT)
        if is_active is not None and not isinstance(is_active, bool):
            return AdminResult(AdminResult.INVALID_INPUT)
        return self._service.list_users(search, role, is_active)

    def set_user_active(self, user_id: int, is_active: bool) -> AdminResult:
        if (
            isinstance(user_id, bool)
            or not isinstance(user_id, int)
            or not isinstance(is_active, bool)
        ):
            return AdminResult(AdminResult.INVALID_INPUT)
        return self._service.set_user_active(user_id, is_active)

    def get_statistics(self) -> AdminResult:
        return self._service.get_statistics()

    def list_skills(
        self,
        search: str = "",
        category: str | None = None,
        level: str | None = None,
        is_active: bool | None = None,
    ) -> AdminResult:
        if not isinstance(search, str):
            return AdminResult(AdminResult.INVALID_INPUT)
        if category is not None and not isinstance(category, str):
            return AdminResult(AdminResult.INVALID_INPUT)
        if level is not None and not isinstance(level, str):
            return AdminResult(AdminResult.INVALID_INPUT)
        if is_active is not None and not isinstance(is_active, bool):
            return AdminResult(AdminResult.INVALID_INPUT)
        return self._service.list_skills(search, category, level, is_active)

    def create_skill(
        self,
        name: str,
        description: str = "",
        category: str = "",
        level: str = "beginner",
    ) -> AdminResult:
        if not all(
            isinstance(value, str)
            for value in (name, description, category, level)
        ):
            return AdminResult(AdminResult.INVALID_INPUT)
        return self._service.create_skill(name, description, category, level)

    def update_skill(
        self,
        skill_id: int,
        name: str,
        description: str = "",
        category: str = "",
        level: str = "beginner",
    ) -> AdminResult:
        if (
            isinstance(skill_id, bool)
            or not isinstance(skill_id, int)
            or not all(
                isinstance(value, str)
                for value in (name, description, category, level)
            )
        ):
            return AdminResult(AdminResult.INVALID_INPUT)
        return self._service.update_skill(
            skill_id, name, description, category, level
        )

    def set_skill_active(self, skill_id: int, is_active: bool) -> AdminResult:
        if (
            isinstance(skill_id, bool)
            or not isinstance(skill_id, int)
            or not isinstance(is_active, bool)
        ):
            return AdminResult(AdminResult.INVALID_INPUT)
        return self._service.set_skill_active(skill_id, is_active)


admin_controller = AdminController()
