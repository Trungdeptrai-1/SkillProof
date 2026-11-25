import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.database.connection import db
from app.models.user_model import ROLE_LABELS, UserModel
from app.services.auth_service import AuthService, SessionManager
from app.utils.helpers import hash_password


@pytest.fixture
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture(autouse=True)
def reset_session():
    SessionManager._instance = None
    yield
    if SessionManager._instance is not None:
        SessionManager.instance().end_session()
    SessionManager._instance = None


def _insert_and_login(fresh_db, role, email):
    password = "StrongPassword1"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active) "
        "VALUES(?,?,?,?,?,1)",
        (role + "_qa", email, hash_password(password), role.title() + " QA", role),
    )
    result = AuthService().login(email, password)
    assert result.success
    return result.user


def test_first_run_setup_creates_admin_and_routes_to_welcome(fresh_db, qt_app):
    from app.database.schema import is_first_run
    from app.ui.main_window import MainWindow

    assert is_first_run()
    window = MainWindow()
    assert window._stack.currentWidget() is window._first_run

    screen = window._first_run
    screen._name_input.setText("First Run Admin")
    screen._email_input.setText("first-run@example.com")
    screen._pw1_input.setText("StrongPassword1")
    screen._pw2_input.setText("StrongPassword1")
    screen._on_submit()

    row = db.fetchone(
        "SELECT role FROM users WHERE email=?", ("first-run@example.com",)
    )
    assert row["role"] == "admin"
    assert not is_first_run()

    screen._complete()
    assert window._stack.currentWidget() is window._welcome
    window.deleteLater()


def test_registration_login_logout_and_screen_navigation(
    fresh_db, qt_app, monkeypatch
):
    import app.database.schema as schema
    import client.views.login_screen as login_module
    import client.views.register_screen as register_module
    from app.ui.main_window import MainWindow

    class ImmediateTransitionTimer:
        @staticmethod
        def singleShot(interval, callback):
            if interval >= 400:
                callback()

    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    monkeypatch.setattr(login_module, "QTimer", ImmediateTransitionTimer)
    monkeypatch.setattr(register_module, "QTimer", ImmediateTransitionTimer)

    window = MainWindow()
    window._welcome._action_panel.btn_start.click()
    assert window._stack.currentWidget() is window._login

    window._login._form_panel._register_link.click()
    assert window._stack.currentWidget() is window._register

    form = window._register._form_panel
    form._name_input.setText("Candidate UI")
    form._email_input.setText("candidate-ui@example.com")
    form._pw1_input.setText("StrongPassword1")
    form._pw2_input.setText("StrongPassword1")
    form._submit_btn.click()

    assert window._stack.currentWidget() is window._login
    assert db.fetchone(
        "SELECT id FROM users WHERE email=?", ("candidate-ui@example.com",)
    )

    login_form = window._login._form_panel
    login_form._email_input.setText("candidate-ui@example.com")
    login_form._password_input.setText("StrongPassword1")
    login_form._login_btn.click()

    # Candidate now lands on Job Discovery immediately after login.
    assert window._stack.currentWidget() is window._marketplace
    assert window._marketplace.role == "candidate"
    assert window._dashboard._user.role == "candidate"
    assert SessionManager.instance().is_logged_in

    logout_button = next(
        button
        for button in window._dashboard.findChildren(QPushButton)
        if "Đăng xuất" in button.text()
    )
    logout_button.click()

    assert window._stack.currentWidget() is window._login
    assert not SessionManager.instance().is_logged_in

    login_form = window._login._form_panel
    login_form._email_input.setText("candidate-ui@example.com")
    login_form._password_input.setText("StrongPassword1")
    login_form._login_btn.click()
    # Candidate now lands on Job Discovery immediately after login.
    assert window._stack.currentWidget() is window._marketplace
    assert window._marketplace.role == "candidate"
    assert SessionManager.instance().is_logged_in

    logout_button = next(
        button
        for button in window._dashboard.findChildren(QPushButton)
        if "Đăng xuất" in button.text()
    )
    logout_button.click()
    assert not SessionManager.instance().is_logged_in
    window.deleteLater()


@pytest.mark.parametrize(
    "role", ["admin", "instructor", "student", "candidate", "company", "expert"]
)
def test_dashboard_displays_role_specific_content(role, qt_app):
    from client.views.dashboard_screen import DashboardScreen, ROLE_CONFIG

    user = UserModel(
        id=1,
        username="qa-user",
        email="qa@example.com",
        full_name="QA User",
        role=role,
        avatar_path=None,
        is_active=True,
        created_at="",
        updated_at="",
    )
    screen = DashboardScreen(user)
    visible_text = {label.text() for label in screen.findChildren(QLabel)}

    assert ROLE_CONFIG[role]["title"] in visible_text
    assert ROLE_LABELS[role] in visible_text
    screen.deleteLater()


def test_company_profile_screen_creates_profile(fresh_db, qt_app):
    from app.ui.screens.company_profile_screen import CompanyProfileScreen

    _insert_and_login(fresh_db, "company", "company-ui@example.com")
    screen = CompanyProfileScreen()
    screen._company_name.setText("QA Company")
    screen._industry.setText("Software")
    screen._website.setText("https://example.com")
    screen._description.setPlainText("Company profile UI test")
    screen._tax_code.setText("QA-001")
    screen._address.setText("Hanoi")
    screen._btn_save.click()

    assert screen._profile is not None
    assert screen._profile.company_name == "QA Company"
    screen._btn_edit.click()
    screen._company_name.setText("QA Company Updated")
    screen._btn_save.click()
    assert screen._profile.company_name == "QA Company Updated"
    assert screen._controller.get_profile().profile.company_name == "QA Company Updated"
    screen.deleteLater()


def test_expert_profile_screen_creates_profile(fresh_db, qt_app):
    from app.ui.screens.expert_profile_screen import ExpertProfileScreen

    _insert_and_login(fresh_db, "expert", "expert-ui@example.com")
    screen = ExpertProfileScreen()
    screen._title_input.setText("QA Expert")
    screen._spec_input.setText("Python")
    screen._bio_input.setPlainText("Expert profile UI test")
    screen._rate_input.setValue(100000)
    screen._btn_save.click()

    assert screen._profile is not None
    assert screen._profile.title == "QA Expert"
    screen._btn_edit.click()
    screen._title_input.setText("QA Expert Updated")
    screen._btn_save.click()
    assert screen._profile.title == "QA Expert Updated"
    assert screen._controller.get_profile().profile.title == "QA Expert Updated"
    screen.deleteLater()


@pytest.mark.parametrize(
    ("role", "email", "menu_label", "profile_attribute"),
    [
        ("company", "company-navigation@example.com", "Hồ sơ doanh nghiệp", "_company_profile"),
        ("expert", "expert-navigation@example.com", "Hồ sơ chuyên gia", "_expert_profile"),
    ],
)
def test_company_and_expert_dashboard_profile_navigation(
    fresh_db, qt_app, monkeypatch, role, email, menu_label, profile_attribute
):
    import app.database.schema as schema
    from app.ui.main_window import MainWindow

    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    user = _insert_and_login(fresh_db, role, email)
    window = MainWindow()
    window._show_dashboard(user)

    profile_button = next(
        button
        for button in window._dashboard.findChildren(QPushButton)
        if button.text().strip().endswith(menu_label)
    )
    profile_button.click()

    profile_screen = getattr(window, profile_attribute)
    assert profile_screen is not None
    assert window._stack.currentWidget() is profile_screen

    back_button = next(
        button
        for button in profile_screen.findChildren(QPushButton)
        if button.text().strip().endswith("Quay lại Dashboard")
    )
    back_button.click()
    assert window._stack.currentWidget() is window._dashboard

    AuthService().logout()
    window.deleteLater()
