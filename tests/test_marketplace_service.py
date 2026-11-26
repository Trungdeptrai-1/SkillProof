"""Controller/Service access checks for two-way marketplace actions."""
import pytest

from app.models.user_model import UserModel
from app.services.auth_service import SessionManager
from server.controllers.marketplace_controller import MarketplaceController
from server.services.marketplace_service import MarketplaceService


def user(user_id: int, role: str) -> UserModel:
    return UserModel(
        id=user_id, username=role, email=role + "@example.test",
        full_name=role, role=role, avatar_path=None, is_active=True,
        created_at="", updated_at="",
    )


class FakeMarketplace:
    def __init__(self):
        self.calls = []

    def browse_jobs(self, *args):
        self.calls.append(("browse", args))
        return [{"id": 3}]

    def respond_to_offer(self, *args):
        self.calls.append(("offer_reply", args))
        return {"offer_response": "accepted" if args[-1] else "declined"}

    def apply(self, *args):
        self.calls.append(("apply", args))
        return {"id": 5}

    def applicants(self, *args):
        self.calls.append(("applicants", args))
        return [{"id": 5}]

    def discover_candidates(self, *args):
        self.calls.append(("talent", args))
        return []


@pytest.fixture
def controller():
    SessionManager._instance = None
    repo = FakeMarketplace()
    ctl = MarketplaceController(MarketplaceService(repo))
    yield ctl, repo, SessionManager.instance()
    SessionManager._instance = None


def test_login_required(controller):
    ctl, repo, _ = controller
    assert ctl.browse_jobs().status == "not_logged_in"
    assert ctl.applicants(3).status == "not_logged_in"
    assert not repo.calls


def test_candidate_cannot_manage_company_applicants(controller):
    ctl, repo, session = controller
    session.start_session(user(11, "candidate"))
    assert ctl.browse_jobs("Python").success
    assert repo.calls[-1] == ("browse", (11, "Python", ""))
    assert ctl.apply(3).success
    assert repo.calls[-1] == ("apply", (11, 3, ""))
    assert ctl.applicants(3).status == "wrong_role"
    assert ctl.discover_candidates().status == "wrong_role"
    assert ctl.apply(True).status == "invalid_input"


def test_company_cannot_apply(controller):
    ctl, repo, session = controller
    session.start_session(user(22, "company"))
    assert ctl.browse_jobs().status == "wrong_role"
    assert ctl.apply(3).status == "wrong_role"
    assert ctl.applicants(3).success
    assert repo.calls[-1] == ("applicants", (22, 3))
    assert ctl.discover_candidates().success
    assert repo.calls[-1] == ("talent", (22, ""))


def test_validation_before_repository_access(controller):
    ctl, repo, session = controller
    session.start_session(user(11, "candidate"))
    assert ctl.apply(-1).status == "invalid_input"
    assert ctl.browse_jobs(123).status == "invalid_input"
    assert ctl.set_discoverable("yes").status == "invalid_input"
    assert repo.calls == []


def test_offer_reply_is_session_scoped_and_validated(controller):
    ctl, repo, session = controller
    assert ctl.respond_to_offer(9, True).status == "not_logged_in"
    session.start_session(user(22, "company"))
    assert ctl.respond_to_offer(9, True).status == "wrong_role"
    session.end_session()
    session.start_session(user(11, "candidate"))
    assert ctl.respond_to_offer(True, True).status == "invalid_input"
    assert ctl.respond_to_offer(9, 1).status == "invalid_input"
    assert ctl.respond_to_offer(9, False).success
    assert repo.calls[-1] == ("offer_reply", (11, 9, False))
