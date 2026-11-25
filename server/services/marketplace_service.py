"""Authenticated marketplace actions. Never accept a caller-supplied actor ID."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from app.services.auth_service import SessionManager
from server.models.marketplace_repository import MarketplaceRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MarketplaceResult:
    status: str
    data: Any = None
    message: str = field(init=False)
    success: bool = field(init=False)

    MESSAGES = {
        "success": "Thao tác thành công.",
        "not_logged_in": "Vui lòng đăng nhập.",
        "wrong_role": "Tài khoản không có quyền thực hiện thao tác.",
        "invalid_input": "Thông tin nhập không hợp lệ.",
        "not_found": "Không tìm thấy dữ liệu hoặc không được phép thao tác.",
        "db_error": "Lỗi cơ sở dữ liệu, vui lòng thử lại.",
    }

    def __post_init__(self) -> None:
        self.success = self.status == "success"
        self.message = self.MESSAGES.get(self.status, "Đã có lỗi xảy ra.")


class MarketplaceService:
    def __init__(self, repository: MarketplaceRepository | None = None) -> None:
        self._repo = repository if repository is not None else MarketplaceRepository()

    @staticmethod
    def _actor(required_role: str) -> int | MarketplaceResult:
        session = SessionManager.instance()
        user = session.current_user
        if not session.is_logged_in or user is None:
            return MarketplaceResult("not_logged_in")
        if user.role != required_role:
            return MarketplaceResult("wrong_role")
        return user.id

    @staticmethod
    def _valid_id(value: object) -> bool:
        return type(value) is int and value > 0

    def _invoke(self, action, *args: object) -> MarketplaceResult:
        try:
            data = action(*args)
            if data is None or data is False:
                return MarketplaceResult("not_found")
            return MarketplaceResult("success", data)
        except sqlite3.Error:
            logger.exception("Marketplace database action failed")
            return MarketplaceResult("db_error")

    def browse_jobs(self, search: str = "", location: str = "") -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not isinstance(search, str) or not isinstance(location, str):
            return MarketplaceResult("invalid_input")
        if len(search) > 200 or len(location) > 200:
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.browse_jobs, actor, search, location)

    def apply(self, job_id: int, cover_letter: str = "") -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(job_id) or not isinstance(cover_letter, str) or len(cover_letter) > 4000:
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.apply, actor, job_id, cover_letter)

    def my_applications(self) -> MarketplaceResult:
        actor = self._actor("candidate")
        return actor if isinstance(actor, MarketplaceResult) else self._invoke(self._repo.my_applications, actor)

    def withdraw(self, application_id: int) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(application_id):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.withdraw, actor, application_id)

    def save_job(self, job_id: int) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(job_id):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.save_job, actor, job_id)

    def unsave_job(self, job_id: int) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(job_id):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.unsave_job, actor, job_id)

    def set_discoverable(self, visible: bool) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if type(visible) is not bool:
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.set_discoverable, actor, visible)

    def discover_candidates(self, search: str = "") -> MarketplaceResult:
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not isinstance(search, str) or len(search) > 200:
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.discover_candidates, actor, search)

    def applicants(self, job_id: int) -> MarketplaceResult:
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(job_id):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.applicants, actor, job_id)

    def update_application_status(self, application_id: int, status: str) -> MarketplaceResult:
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(application_id) or not isinstance(status, str):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.update_application_status, actor, application_id, status)
