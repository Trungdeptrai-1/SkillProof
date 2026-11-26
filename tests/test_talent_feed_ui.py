"""Candidate discovery feed works with opt-in public data and real invite actions."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
from PySide6.QtWidgets import QApplication, QMessageBox

from client.views.marketplace_screen import MarketplaceScreen, selected_id
from client.components.talent_feed import candidate_initials, experience_label


class PublicCandidates:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def discover_candidates(self, search=""):
        self.queries.append(search)
        return SimpleNamespace(success=True, data=self.rows, message="")


class Invitations:
    def __init__(self):
        self.sent_calls = []

    def send(self, job_id, candidate_id, message=""):
        self.sent_calls.append((job_id, candidate_id, message))
        return SimpleNamespace(success=True, data={"id": 42}, message="OK")


def test_talent_card_has_safe_local_avatar_fallback():
    assert candidate_initials("Nguyễn Văn An") == "VA"
    assert candidate_initials("") == "UV"
    assert experience_label(3) == "3 năm kinh nghiệm"
    assert experience_label(None) == "Chưa cập nhật kinh nghiệm"


def test_company_feed_selection_and_direct_invite(monkeypatch):
    app = QApplication.instance() or QApplication([])
    rows = [
        {"id": 21, "full_name": "Nguyễn Văn An", "headline": "Python Developer",
         "bio": "Phát triển ứng dụng backend", "years_experience": 3},
        {"id": 22, "full_name": "Trần Thị Bình", "headline": "QA Engineer",
         "bio": "Kiểm thử tự động", "years_experience": 2},
    ]
    controller = PublicCandidates(rows)
    invites = Invitations()

    def fake_positions(self):
        self.positions.blockSignals(True)
        self.positions.clear()
        self.positions.addItem("Backend Engineer", 10)
        self.positions.blockSignals(False)
        self.invite_position.clear()
        self.invite_position.addItem("Backend Engineer", 10)
        self._refresh_talent_detail(None)

    monkeypatch.setattr(MarketplaceScreen, "_load_positions", fake_positions)
    monkeypatch.setattr(MarketplaceScreen, "_load_assessment_exams", lambda self: None)
    monkeypatch.setattr(MarketplaceScreen, "_load_sent_invites", lambda self: None)
    monkeypatch.setattr(MarketplaceScreen, "_load_applicants", lambda self, *args: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    screen = MarketplaceScreen("company", controller=controller,
                               invitation_controller=invites)
    assert screen.talent_feed.count() == 2
    assert screen.talent_count.text() == "2 hồ sơ ứng viên công khai"
    assert screen.talent_name.text() == "Nguyễn Văn An"
    assert screen.talent_invite_button.isEnabled()
    # Forms must retain usable dimensions inside an independently scrolling
    # detail panel even at the standard desktop demo resolution.
    assert screen.talent_detail_scroll.widget().minimumHeight() >= 615
    assert screen.invite_position.minimumHeight() >= 44
    assert screen.talent_message.minimumHeight() >= 92
    assert screen.talent_avatar.size().width() == 72

    screen.talent_feed.setCurrentRow(1)
    assert screen.talent_name.text() == "Trần Thị Bình"
    assert selected_id(screen.talent_table) == 22
    screen.talent_message.setPlainText("Mời bạn tìm hiểu vị trí QA.")
    screen.talent_invite_button.click()
    assert invites.sent_calls == [(10, 22, "Mời bạn tìm hiểu vị trí QA.")]

    screen.talent_search.setText("Python")
    screen._load_talents()
    assert controller.queries[-1] == "Python"
    screen.close()
    screen.deleteLater()
    app.processEvents()


def test_empty_talent_feed_has_guidance_and_no_invite(monkeypatch):
    app = QApplication.instance() or QApplication([])
    controller = PublicCandidates([])
    monkeypatch.setattr(MarketplaceScreen, "_load_positions", lambda self: None)
    monkeypatch.setattr(MarketplaceScreen, "_load_assessment_exams", lambda self: None)
    monkeypatch.setattr(MarketplaceScreen, "_load_sent_invites", lambda self: None)
    screen = MarketplaceScreen("company", controller=controller,
                               invitation_controller=Invitations())
    assert screen.talent_count.text() == "0 hồ sơ ứng viên công khai"
    assert "Chưa tìm thấy" in screen.talent_feed.item(0).text()
    assert not screen.talent_invite_button.isEnabled()
    screen.close()
    screen.deleteLater()
    app.processEvents()
