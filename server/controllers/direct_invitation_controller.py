"""Controller facade for direct, non-exam recruiting invitations."""
from __future__ import annotations
from server.services.direct_invitation_service import DirectInvitationService


class DirectInvitationController:
    def __init__(self, service: DirectInvitationService | None = None) -> None:
        self.service = service if service is not None else DirectInvitationService()

    def send(self, job_id: int, candidate_id: int, message: str = ""):
        return self.service.send(job_id, candidate_id, message)

    def sent(self):
        return self.service.sent()

    def received(self):
        return self.service.received()

    def respond(self, invitation_id: int, accepted: bool):
        return self.service.respond(invitation_id, accepted)

    def cancel(self, invitation_id: int):
        return self.service.cancel(invitation_id)
