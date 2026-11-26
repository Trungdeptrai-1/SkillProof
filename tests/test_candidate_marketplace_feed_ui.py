"""Candidate marketplace feeds preserve controller-backed actions and privacy."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication
from client.views.marketplace_screen import MarketplaceScreen, selected_id


class CandidateData:
    def __init__(self):
        self.calls = []

    def _ok(self, data=None):
        return SimpleNamespace(success=True, data=data, message="OK")

    def browse_jobs(self, search="", location=""):
        return self._ok([])
    def my_applications(self):
        return self._ok([
            {"id": 12, "title": "Python Developer", "company_name": "FPT",
             "status": "offered", "decision_note": "Mời gia nhập",
             "offer_response": None, "applied_at": "2026-11-26"},
            {"id": 13, "title": "QA Engineer", "company_name": "VNG",
             "status": "reviewing", "decision_note": "",
             "offer_response": None, "applied_at": "2026-11-26"},
        ])
    def saved_jobs(self):
        return self._ok([{"id": 32, "title": "Java Developer", "company_name": "FPT",
                          "location": "Đà Nẵng", "status": "published", "applied": 0}])
    def get_discoverable(self):
        return self._ok(True)
    def set_discoverable(self, visible):
        self.calls.append(("privacy", visible))
        return self._ok(True)
    def withdraw(self, application_id):
        self.calls.append(("withdraw", application_id))
        return self._ok(True)
    def respond_to_offer(self, application_id, accepted):
        self.calls.append(("offer", application_id, accepted))
        return self._ok(True)
    def unsave_job(self, job_id):
        self.calls.append(("unsave", job_id))
        return self._ok(True)


class Invitations:
    def received(self):
        return SimpleNamespace(success=True, data=[
            {"id": 23, "job_title": "React Developer", "company_name": "VNG",
             "message": "Mời trao đổi", "status": "pending", "sent_at": "2026-11-26"},
            {"id": 24, "job_title": "Java Developer", "company_name": "FPT",
             "message": "", "status": "accepted", "sent_at": "2026-11-25"},
        ], message="OK")
    def respond(self, invitation_id, accepted):
        return SimpleNamespace(success=True, data=True, message="OK")


def test_candidate_tabs_have_real_feed_selection_and_state_actions():
    app = QApplication.instance() or QApplication([])
    screen = MarketplaceScreen("candidate", controller=CandidateData(),
                               invitation_controller=Invitations())
    assert screen.apps_feed.count() == 2
    assert screen.saved_feed.count() == 1
    assert screen.invites_feed.count() == 2

    assert screen.apps_heading.text() == "Python Developer"
    assert selected_id(screen.apps_table) == 12
    assert screen.accept_offer_button.isEnabled()
    assert screen.decline_offer_button.isEnabled()
    assert not screen.withdraw_button.isEnabled()

    screen.apps_feed.setCurrentRow(1)
    assert selected_id(screen.apps_table) == 13
    assert screen.withdraw_button.isEnabled()
    assert not screen.accept_offer_button.isEnabled()

    assert selected_id(screen.saved_table) == 32
    assert screen.unsave_button.isEnabled()
    assert screen.saved_heading.text() == "Java Developer"

    assert selected_id(screen.received_table) == 23
    assert screen.invite_accept_button.isEnabled()
    screen.invites_feed.setCurrentRow(1)
    assert not screen.invite_accept_button.isEnabled()
    assert not screen.invite_decline_button.isEnabled()
    assert "Lời nhắn" in screen.invites_summary.text()

    assert "công khai" in screen.privacy_status.text()
    screen.visibility.setChecked(False)
    assert "sau khi" in screen.privacy_status.text()

    screen.close()
    screen.deleteLater()
    app.processEvents()


def test_candidate_empty_tabs_show_guidance_not_fake_entries():
    app = QApplication.instance() or QApplication([])
    data = CandidateData()
    data.my_applications = lambda: SimpleNamespace(success=True, data=[], message="")
    data.saved_jobs = lambda: SimpleNamespace(success=True, data=[], message="")
    invitations = Invitations()
    invitations.received = lambda: SimpleNamespace(success=True, data=[], message="")
    screen = MarketplaceScreen("candidate", controller=data, invitation_controller=invitations)
    assert "Chưa có dữ liệu" in screen.apps_feed.item(0).text()
    assert "Chưa có dữ liệu" in screen.saved_feed.item(0).text()
    assert "Chưa có dữ liệu" in screen.invites_feed.item(0).text()
    assert not screen.accept_offer_button.isEnabled()
    assert not screen.unsave_button.isEnabled()
    assert not screen.invite_accept_button.isEnabled()
    screen.close()
    screen.deleteLater()
    app.processEvents()
