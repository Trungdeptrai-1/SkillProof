import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from app.utils.helpers import hash_password
from server.controllers.auth_controller import AuthController
from server.controllers.profile_controller import (
    CompanyProfileController,
    ExpertProfileController,
)


def _qt_app():
    return QApplication.instance() or QApplication([])


def _insert_user(database, username, email, role):
    password = "StrongDemoPass1"
    database.execute(
        """
        INSERT INTO users (username, email, password, full_name, role, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (username, email, hash_password(password), username.title(), role),
    )
    return email, password


def _button_ending_with(widget, text):
    return next(
        button
        for button in widget.findChildren(QPushButton)
        if button.text().strip().endswith(text)
    )


def test_company_expert_collaboration_completes_through_ui(
    fresh_db, auth, monkeypatch
):
    import app.database.schema as schema
    from app.ui.main_window import MainWindow

    app = _qt_app()
    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    company_credentials = _insert_user(
        fresh_db, "collab-company", "collab-company@example.test", "company"
    )
    expert_credentials = _insert_user(
        fresh_db, "collab-expert", "collab-expert@example.test", "expert"
    )
    auth_controller = AuthController()

    expert_login = auth_controller.login(*expert_credentials)
    assert expert_login.success
    expert_profile = ExpertProfileController().create_profile(
        "Python Expert",
        specialization="Python",
        hourly_rate=1200,
    )
    assert expert_profile.success
    auth_controller.logout()

    company_login = auth_controller.login(*company_credentials)
    assert company_login.success
    assert CompanyProfileController().create_profile("Demo Company").success

    window = MainWindow()
    window._show_dashboard(company_login.user)
    dashboard = window._dashboard
    _button_ending_with(dashboard, "Tìm chuyên gia").click()
    search_screen = window._expert_search
    search_screen._spec_input.setText("Python")
    _button_ending_with(search_screen, "Tìm kiếm").click()
    _button_ending_with(search_screen, "Mời hợp tác").click()
    assert "gửi đề nghị hợp tác thành công" in search_screen._banner.text()

    contract_id = fresh_db.fetchone(
        "SELECT id FROM company_expert_contracts WHERE company_id = "
        "(SELECT id FROM company_profiles WHERE user_id = ?) "
        "ORDER BY id DESC LIMIT 1",
        (company_login.user.id,),
    )["id"]
    _button_ending_with(search_screen, "Hợp đồng của tôi").click()
    assert window._stack.currentWidget() is window._contracts

    auth_controller.logout()
    expert_login = auth_controller.login(*expert_credentials)
    assert expert_login.success
    window._show_dashboard(expert_login.user)
    expert_dashboard = window._dashboard
    _button_ending_with(expert_dashboard, "Hợp đồng của tôi").click()
    _button_ending_with(window._contracts, "Chấp thuận").click()
    assert fresh_db.fetchone(
        "SELECT status FROM company_expert_contracts WHERE id = ?", (contract_id,)
    )["status"] == "active"

    auth_controller.logout()
    company_login = auth_controller.login(*company_credentials)
    assert company_login.success
    window._show_dashboard(company_login.user)
    company_dashboard = window._dashboard
    _button_ending_with(company_dashboard, "Nhiệm vụ của tôi").click()
    company_tasks = window._tasks
    assert company_tasks._contract_combo.findData(contract_id) >= 0
    company_tasks._contract_combo.setCurrentIndex(
        company_tasks._contract_combo.findData(contract_id)
    )
    company_tasks._task_title.setText("UI collaboration task")
    _button_ending_with(company_tasks, "Tạo nhiệm vụ").click()
    task_id = fresh_db.fetchone(
        "SELECT id FROM tasks WHERE contract_id = ?", (contract_id,)
    )["id"]
    assert fresh_db.fetchone(
        "SELECT status FROM tasks WHERE id = ?", (task_id,)
    )["status"] == "pending"

    auth_controller.logout()
    expert_login = auth_controller.login(*expert_credentials)
    assert expert_login.success
    window._show_dashboard(expert_login.user)
    expert_dashboard = window._dashboard
    _button_ending_with(expert_dashboard, "Nhiệm vụ của tôi").click()
    expert_tasks = window._tasks
    _button_ending_with(expert_tasks, "Nhận nhiệm vụ").click()
    _button_ending_with(expert_tasks, "Hoàn thành").click()
    assert fresh_db.fetchone(
        "SELECT status FROM tasks WHERE id = ?", (task_id,)
    )["status"] == "completed"
    expert_tasks.on_back()
    assert window._stack.currentWidget() is expert_dashboard

    auth_controller.logout()
    window.close()
    app.processEvents()
