import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import replace

from PySide6.QtWidgets import QApplication, QPushButton

from app.ui.screens.company_profile_screen import (
    CompanyProfileScreen as LegacyCompanyProfileScreen,
)
from app.ui.screens.expert_profile_screen import (
    ExpertProfileScreen as LegacyExpertProfileScreen,
)
from app.ui.screens.contract_management_screen import (
    ContractManagementScreen as LegacyContractManagementScreen,
)
from app.ui.screens.expert_search_screen import (
    ExpertSearchScreen as LegacyExpertSearchScreen,
)
from app.ui.screens.first_run_screen import FirstRunScreen as LegacyFirstRunScreen
from app.ui.screens.task_management_screen import (
    TaskManagementScreen as LegacyTaskManagementScreen,
)
from app.utils.helpers import hash_password
from client.views.admin_dashboard_screen import AdminDashboardScreen
from client.views.company_profile_screen import CompanyProfileScreen
from client.views.expert_profile_screen import ExpertProfileScreen
from client.views.expert_search_screen import ExpertSearchScreen
from client.views.first_run_screen import FirstRunScreen
from client.views.skill_management_screen import (
    SkillActionResult,
    SkillListResult,
    SkillManagementScreen,
)
from client.views.task_management_screen import TaskManagementScreen
from client.views.contract_management_screen import ContractManagementScreen
from client.views.dashboard_screen import DashboardScreen
from client.views.user_management_screen import (
    UserActionResult,
    UserListResult,
    UserManagementScreen,
)
from server.controllers.auth_controller import AuthController
from server.models.skill_model import SkillModel
from server.models.user_model import UserModel


def _qt_app():
    return QApplication.instance() or QApplication([])


def test_moved_views_keep_legacy_import_compatibility():
    assert LegacyCompanyProfileScreen is CompanyProfileScreen
    assert LegacyExpertProfileScreen is ExpertProfileScreen
    assert LegacyFirstRunScreen is FirstRunScreen
    assert LegacyExpertSearchScreen is ExpertSearchScreen
    assert LegacyContractManagementScreen is ContractManagementScreen
    assert LegacyTaskManagementScreen is TaskManagementScreen


def _insert_user(database, username, email, role, full_name):
    password = "StrongPass1"
    database.execute(
        """
        INSERT INTO users (username, email, password, full_name, role, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (username, email, hash_password(password), full_name, role),
    )
    return email, password


class _UserManagementControllerMock:
    def __init__(self):
        self.users = [
            UserModel(
                7,
                "demo",
                "demo@example.com",
                "Demo Candidate",
                "candidate",
                None,
                True,
                "",
                "",
            )
        ]
        self.actions = []

    def list_users(self):
        return UserListResult(True, tuple(self.users))

    def set_user_active(self, user_id, is_active):
        self.actions.append((user_id, is_active))
        self.users = [
            replace(user, is_active=is_active) if user.id == user_id else user
            for user in self.users
        ]
        return UserActionResult(True, "Updated")


class _SkillManagementControllerMock:
    def __init__(self):
        self.skills = []

    def list_skills(self):
        return SkillListResult(True, tuple(self.skills))

    def create_skill(self, name, category, level, description):
        skill = SkillModel(
            id=len(self.skills) + 1,
            name=name,
            description=description,
            category=category,
            level=level,
            is_active=True,
            created_at="test",
        )
        self.skills.append(skill)
        return SkillActionResult(True, skill)

    def update_skill(self, skill_id, name, category, level, description):
        skill = replace(
            self.skills[0],
            name=name,
            category=category,
            level=level,
            description=description,
        )
        self.skills = [
            skill if existing.id == skill_id else existing
            for existing in self.skills
        ]
        return SkillActionResult(True, skill)

    def set_skill_active(self, skill_id, is_active):
        self.skills = [
            replace(skill, is_active=is_active)
            if skill.id == skill_id
            else skill
            for skill in self.skills
        ]
        skill = next(item for item in self.skills if item.id == skill_id)
        return SkillActionResult(True, skill)


def test_admin_dashboard_routes_and_unavailable_views_are_explicit(
    monkeypatch, fresh_db, admin_user
):
    from app.database import schema
    from app.ui.main_window import MainWindow

    app = _qt_app()
    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    auth = AuthController()
    login = auth.login(*admin_user)
    assert login.success

    window = MainWindow()
    window._show_dashboard(login.user)
    assert isinstance(window._dashboard, AdminDashboardScreen)

    window._dashboard._users_card_button.click()
    users = window._user_management
    assert isinstance(users, UserManagementScreen)
    assert window._stack.currentWidget() is users
    assert users._table.rowCount() == 0
    assert not users._refresh_button.isEnabled()
    assert "Controller" in users._status_label.text()
    users._back_button.click()

    window._dashboard._skills_card_button.click()
    skills = window._skill_management
    assert isinstance(skills, SkillManagementScreen)
    assert window._stack.currentWidget() is skills
    assert skills._table.rowCount() == 0
    assert not skills._save_button.isEnabled()
    assert "Controller" in skills._status_label.text()

    auth.logout()
    candidate_credentials = _insert_user(
        fresh_db, "candidate_ui", "candidate-ui@example.com",
        "candidate", "Candidate UI"
    )
    candidate_login = auth.login(*candidate_credentials)
    assert candidate_login.success
    window._show_dashboard(candidate_login.user)
    dashboard = window._dashboard
    assert isinstance(dashboard, DashboardScreen)
    window._show_user_management()
    window._show_skill_management()
    assert window._stack.currentWidget() is dashboard
    assert window._user_management is None
    assert window._skill_management is None

    auth.logout()
    window.close()
    app.processEvents()


def test_user_management_view_uses_injected_controller_and_filters():
    app = _qt_app()
    controller = _UserManagementControllerMock()
    screen = UserManagementScreen(controller)
    screen.show()
    assert screen._table.rowCount() == 1
    assert screen._table.item(0, 1).text() == "Demo Candidate"

    screen._search_input.setText("missing")
    assert screen._table.isRowHidden(0)
    screen._search_input.clear()
    screen._table.selectRow(0)
    screen._toggle_active_button.click()

    assert controller.actions == [(7, False)]
    assert screen._table.item(0, 4).text() == "Đã khoá"
    screen.close()
    app.processEvents()


def test_skill_management_view_uses_injected_controller_for_crud():
    app = _qt_app()
    controller = _SkillManagementControllerMock()
    screen = SkillManagementScreen(controller)
    screen.show()

    screen._save_button.click()
    assert not controller.skills
    assert "không được để trống" in screen._status_label.text()
    screen._name_input.setText("Python")
    screen._category_input.setText("Programming")
    screen._description_input.setPlainText("General-purpose language")
    screen._save_button.click()
    assert len(controller.skills) == 1
    assert screen._table.item(0, 1).text() == "Python"

    screen._table.selectRow(0)
    screen._edit_button.click()
    screen._name_input.setText("Python Advanced")
    screen._save_button.click()
    assert controller.skills[0].name == "Python Advanced"
    assert screen._table.item(0, 1).text() == "Python Advanced"

    screen._table.selectRow(0)
    screen._toggle_active_button.click()
    assert not controller.skills[0].is_active
    screen.close()
    app.processEvents()


def test_company_profile_is_client_view_and_dashboard_navigation_is_connected(
    monkeypatch, fresh_db
):
    from app.database import schema
    from app.ui.main_window import MainWindow

    app = _qt_app()
    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    credentials = _insert_user(
        fresh_db, "company_ui", "company-ui@example.com", "company", "Company UI"
    )
    auth = AuthController()
    login = auth.login(*credentials)
    assert login.success

    window = MainWindow()
    window._show_dashboard(login.user)
    dashboard = window._dashboard
    search_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Tìm chuyên gia")
    )
    search_button.click()
    assert isinstance(window._expert_search, ExpertSearchScreen)
    assert window._stack.currentWidget() is window._expert_search

    contract_button = next(
        button
        for button in window._expert_search.findChildren(QPushButton)
        if button.text().strip().endswith("Hợp đồng của tôi")
    )
    contract_button.click()
    assert isinstance(window._contracts, ContractManagementScreen)
    assert window._stack.currentWidget() is window._contracts

    window._contracts.on_find_experts()
    assert window._stack.currentWidget() is window._expert_search
    window._expert_search.on_back()
    assert window._stack.currentWidget() is dashboard

    dashboard_contract_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Hợp đồng của tôi")
    )
    dashboard_contract_button.click()
    assert isinstance(window._contracts, ContractManagementScreen)
    window._contracts.on_back()
    dashboard_task_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Nhiệm vụ của tôi")
    )
    dashboard_task_button.click()
    assert isinstance(window._tasks, TaskManagementScreen)
    window._tasks.on_back()

    profile_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Hồ sơ doanh nghiệp")
    )
    profile_button.click()
    profile = window._company_profile
    assert isinstance(profile, CompanyProfileScreen)
    assert LegacyCompanyProfileScreen is CompanyProfileScreen
    profile._company_name.setText("UI Company")
    profile._website.setText("https://example.com")
    profile._btn_save.click()
    assert profile._profile is not None
    assert profile._profile.company_name == "UI Company"

    auth.logout()
    window.close()
    app.processEvents()


def test_expert_profile_and_tasks_are_reached_from_expert_dashboard(
    monkeypatch, fresh_db
):
    from app.database import schema
    from app.ui.main_window import MainWindow

    app = _qt_app()
    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    credentials = _insert_user(
        fresh_db, "expert_ui", "expert-ui@example.com", "expert", "Expert UI"
    )
    auth = AuthController()
    login = auth.login(*credentials)
    assert login.success

    window = MainWindow()
    window._show_dashboard(login.user)
    dashboard = window._dashboard

    contract_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Hợp đồng của tôi")
    )
    contract_button.click()
    assert isinstance(window._contracts, ContractManagementScreen)
    window._contracts.on_back()

    task_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Nhiệm vụ của tôi")
    )
    task_button.click()
    assert isinstance(window._tasks, TaskManagementScreen)
    assert window._stack.currentWidget() is window._tasks
    window._tasks.on_back()
    assert window._stack.currentWidget() is dashboard

    profile_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Hồ sơ chuyên gia")
    )
    profile_button.click()
    profile = window._expert_profile
    assert isinstance(profile, ExpertProfileScreen)
    assert LegacyExpertProfileScreen is ExpertProfileScreen
    profile._title_input.setText("UI Expert")
    profile._btn_save.click()
    assert profile._profile is not None
    assert profile._profile.title == "UI Expert"

    auth.logout()
    window.close()
    app.processEvents()
