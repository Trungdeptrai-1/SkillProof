"""Marketplace widgets call real controller methods and never fabricate data."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication
from client.views.marketplace_screen import MarketplaceScreen
from client.views.dashboard_screen import DashboardScreen
from server.models.user_model import UserModel

APP = None


def qt_app():
    global APP
    if APP is None:
        APP = QApplication.instance() or QApplication([])
    return APP


class FakeMarketplaceController:
    def __init__(self):
        self.calls = []

    def _answer(self, key, *args, data=None):
        self.calls.append((key, args))
        return SimpleNamespace(success=True, data=data, message="OK")

    def browse_jobs(self, search="", location=""):
        return self._answer("browse", search, location, data=[
            {"id": 7, "title": "Python Developer", "company_name": "Company A",
             "location": "Da Nang", "requirements": "Python", "description": "Build apps",
             "saved": 0, "applied": 0}
        ])

    def my_applications(self):
        return self._answer("mine", data=[])

    def saved_jobs(self):
        return self._answer("saved", data=[])

    def get_discoverable(self):
        return self._answer("visibility", data=True)

    def save_job(self, job_id):
        return self._answer("save", job_id, data=True)

    def unsave_job(self, job_id):
        return self._answer("unsave", job_id, data=True)

    def apply(self, job_id, cover_letter=""):
        return self._answer("apply", job_id, cover_letter, data={"id": 9})

    def withdraw(self, app_id):
        return self._answer("withdraw", app_id, data=True)

    def set_discoverable(self, value):
        return self._answer("set_visibility", value, data=True)

    def applicants(self, job_id):
        return self._answer("applicants", job_id, data=[])

    def discover_candidates(self, search=""):
        return self._answer("talents", search, data=[])

    def update_application_status(self, app_id, status):
        return self._answer("status", app_id, status, data=True)


def make_user(role):
    return UserModel(
        id=1, username=role, email=role + "@example.test",
        full_name=role, role=role, avatar_path=None,
        is_active=True, created_at="", updated_at="",
    )


def test_candidate_can_browse_and_save_from_ui():
    app = qt_app()
    controller = FakeMarketplaceController()
    screen = MarketplaceScreen("candidate", controller=controller)
    assert screen.jobs_table.rowCount() == 1
    assert screen.visibility.isChecked()
    assert ("saved", ()) in controller.calls
    screen.jobs_table.selectRow(0)
    screen._save_selected()
    assert ("save", (7,)) in controller.calls
    screen.close()
    app.processEvents()


def test_dashboard_marketplace_route_candidate_and_company():
    app = qt_app()
    for role in ("candidate", "company"):
        dashboard = DashboardScreen(make_user(role))
        calls = []
        dashboard.on_open_marketplace = lambda: calls.append(role)
        dashboard._sidebar._handle_open_marketplace()
        assert calls == [role]
        dashboard.close()
    app.processEvents()
