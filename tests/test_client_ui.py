import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from app.ui.screens.login_screen import LoginScreen as LegacyLoginScreen
from app.ui.screens.register_screen import RegisterScreen as LegacyRegisterScreen
from app.ui.screens.welcome_screen import WelcomeScreen as LegacyWelcomeScreen
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
