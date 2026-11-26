"""Regressions for business-friendly recruiting dashboard navigation."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QLabel
from client.views.dashboard_screen import DashboardScreen
from server.models.user_model import UserModel


def _company():
    return UserModel(
        id=101, username="test_company", email="company@example.test",
        full_name="Test Company", role="company", avatar_path=None,
        is_active=True, created_at="", updated_at="",
    )


def test_company_overview_uses_real_action_callbacks():
    app = QApplication.instance() or QApplication([])
    screen = DashboardScreen(_company())
    opened = []
    screen.on_open_company_recruitment = lambda: opened.append("positions")
    screen.on_open_marketplace = lambda: opened.append("applicants")
    screen.on_open_extended_workflow = lambda route: opened.append(route)

    action_buttons = [
        btn for btn in screen._content.findChildren(QPushButton)
        if btn.text() == "Mở chức năng"
    ]
    assert len(action_buttons) == 4
    for button in action_buttons:
        button.click()
    assert opened == ["positions", "applicants", "interviews", "manual_grading"]

    visible_labels = [label.text() for label in screen._content.findChildren(QLabel)]
    assert not any("Trong menu" in text for text in visible_labels)
    assert any("Quy trình tuyển dụng" in text for text in visible_labels)

    animation = getattr(screen, "_anim", None)
    if animation is not None:
        animation.stop()
    screen.close()
    screen.deleteLater()
    app.processEvents()


def test_company_sidebar_is_grouped_by_business_workflow():
    app = QApplication.instance() or QApplication([])
    screen = DashboardScreen(_company())
    labels = [widget.text() for widget in screen._sidebar.findChildren(QLabel)]
    assert "TUYỂN DỤNG" in labels
    assert "HỒ SƠ" in labels
    assert "HỢP TÁC CHUYÊN MÔN" in labels
    buttons = [btn.text() for btn in screen._sidebar.findChildren(QPushButton)]
    assert any("Tuyển dụng & đánh giá" in text for text in buttons)
    assert any("Hồ sơ ứng tuyển" in text for text in buttons)
    assert not any("Trong menu" in text for text in buttons)
    screen.close()
    screen.deleteLater()
    app.processEvents()
