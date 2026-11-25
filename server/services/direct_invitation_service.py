"""Business rules for direct recruitment invitations, scoped to the logged-in actor."""
from __future__ import annotations

import logging
import sqlite3
from app.services.auth_service import SessionManager
from server.models.direct_invitation_repository import DirectInvitationRepository
from server.services.marketplace_service import MarketplaceResult

logger = logging.getLogger(__name__)


class DirectInvitationService:
    def __init__(self, repository: DirectInvitationRepository | None = None) -> None:
        self._repo = repository if repository is not None else DirectInvitationRepository()

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
    def _id(value: object) -> bool:
        return type(value) is int and value > 0

    @staticmethod
    def _call(action, *args) -> MarketplaceResult:
        try:
            value = action(*args)
        except sqlite3.Error:
            logger.exception("Direct recruitment invitation DB error")
            return MarketplaceResult("db_error")
        if value is None or value is False:
            return MarketplaceResult("not_found")
        return MarketplaceResult("success", value)

    def send(self, job_id: int, candidate_id: int, message: str = "") -> MarketplaceResult:
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if (not self._id(job_id) or not self._id(candidate_id)
                or not isinstance(message, str) or len(message) > 2000):
            return MarketplaceResult("invalid_input")
        return self._call(self._repo.send, actor, job_id, candidate_id, message)

    def sent(self) -> MarketplaceResult:
        actor = self._actor("company")
        return actor if isinstance(actor, MarketplaceResult) else self._call(self._repo.sent, actor)

    def received(self) -> MarketplaceResult:
        actor = self._actor("candidate")
        return actor if isinstance(actor, MarketplaceResult) else self._call(self._repo.received, actor)

    def respond(self, invitation_id: int, accepted: bool) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._id(invitation_id) or type(accepted) is not bool:
            return MarketplaceResult("invalid_input")
        return self._call(self._repo.respond, actor, invitation_id, accepted)

    def cancel(self, invitation_id: int) -> MarketplaceResult:
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._id(invitation_id):
            return MarketplaceResult("invalid_input")
        return self._call(self._repo.cancel, actor, invitation_id)
