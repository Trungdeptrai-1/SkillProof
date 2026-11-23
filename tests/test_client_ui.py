import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from app.ui.screens.candidate_profile_screen import (
    CandidateProfileScreen as LegacyCandidateProfileScreen,
)
from app.ui.screens.dashboard_screen import DashboardScreen as LegacyDashboardScreen
from app.ui.screens.login_screen import LoginScreen as LegacyLoginScreen
from app.ui.screens.register_screen import RegisterScreen as LegacyRegisterScreen
from app.ui.screens.welcome_screen import WelcomeScreen as LegacyWelcomeScreen
from client.views.candidate_profile_screen import CandidateProfileScreen
from client.views.dashboard_screen import DashboardScreen
from client.views.login_screen import LoginScreen
from client.views.register_screen import RegisterScreen
from client.views.welcome_screen import WelcomeScreen


def test_client_auth_screens_initialize_and_keep_legacy_imports(monkeypatch, fresh_db):
    app = QApplication.instance() or QApplication([])
    assert LegacyWelcomeScreen is WelcomeScreen
    assert LegacyLoginScreen is LoginScreen
    assert LegacyRegisterScreen is RegisterScreen

    welcome = WelcomeScreen()
    login = LoginScreen()
    register = RegisterScreen()
    assert welcome is not None
    assert login is not None
    assert register is not None

    login._form_panel._password_field.toggle_button.click()
    assert login._form_panel._password_input.echoMode() == QLineEdit.EchoMode.Normal
    login.reset()
    assert login._form_panel._password_input.echoMode() == QLineEdit.EchoMode.Password

    from app.database import schema
    from app.ui.main_window import MainWindow

    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    window = MainWindow()
    assert window._stack.currentWidget() is window._welcome

    window._welcome._action_panel.btn_start.click()
    assert window._stack.currentWidget() is window._login

    window._login._form_panel._register_link.click()
    assert window._stack.currentWidget() is window._register

    window._register._form_panel._login_link.click()
    assert window._stack.currentWidget() is window._login

    back_button = next(
        button
        for button in window._login.findChildren(QPushButton)
        if button.text() == "← Quay lại"
    )
    back_button.click()
    assert window._stack.currentWidget() is window._welcome

    window._welcome.deleteLater()
    window._login.deleteLater()
    window._register.deleteLater()
    window.deleteLater()
    app.processEvents()


def test_candidate_dashboard_profile_create_edit_and_validation(
    monkeypatch, fresh_db, candidate_user
):
    app = QApplication.instance() or QApplication([])
    assert LegacyCandidateProfileScreen is CandidateProfileScreen
    assert LegacyDashboardScreen is DashboardScreen

    from app.database import schema
    from app.services.auth_service import AuthService, SessionManager
    from app.ui.main_window import MainWindow

    SessionManager._instance = None
    auth = AuthService()
    login_result = auth.login(*candidate_user)
    assert login_result.success

    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    window = MainWindow()
    window._show_dashboard(login_result.user)
    dashboard = window._dashboard
    assert isinstance(dashboard, DashboardScreen)

    profile_menu_item = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Hồ sơ cá nhân")
    )
    profile_menu_item.click()
    screen = window._candidate_profile
    assert isinstance(screen, CandidateProfileScreen)
    assert window._stack.currentWidget() is screen
    assert not screen._btn_save.isHidden()
    assert not screen._profile

    screen._headline_input.setText("Python Developer")
    screen._portfolio_input.setText("not-a-url")
    screen._btn_save.click()
    assert "portfolio" in screen._banner.text().lower()
    assert not screen._svc.get_profile().success

    screen._portfolio_input.setText("https://example.com/portfolio")
    screen._btn_save.click()
    assert screen._profile is not None
    assert screen._full_name_lbl.text() == login_result.user.full_name
    assert screen._email_lbl.text() == login_result.user.email
    assert screen._headline_input.text() == "Python Developer"
    assert screen._portfolio_input.text() == "https://example.com/portfolio"
    assert not screen._headline_input.isEnabled()

    screen._btn_edit.click()
    screen._headline_input.setText("Senior Python Developer")
    screen._btn_save.click()
    saved = screen._svc.get_profile()
    assert saved.success
    assert saved.profile.headline == "Senior Python Developer"
    assert screen._headline_input.text() == "Senior Python Developer"

    back_button = next(
        button
        for button in screen.findChildren(QPushButton)
        if button.text().strip().endswith("Quay lại Dashboard")
    )
    back_button.click()
    assert window._stack.currentWidget() is dashboard

    auth.logout()
    SessionManager._instance = None
    window.deleteLater()
    app.processEvents()
