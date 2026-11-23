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

    def list_users(self, search="", role=None, is_active=None):
        users = [
            user
            for user in self.users
            if (not search or search.casefold() in user.display_name.casefold())
            and (role is None or user.role == role)
            and (is_active is None or user.is_active is is_active)
        ]
        return UserListResult(True, tuple(users))

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

    def list_skills(self, search=""):
        skills = [
            skill
            for skill in self.skills
            if not search
            or search.casefold()
            in " ".join(
                (skill.name, skill.description or "", skill.category or "")
            ).casefold()
        ]
        return SkillListResult(True, tuple(skills))

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


def test_admin_dashboard_routes_and_admin_features_use_real_controller(
    monkeypatch, fresh_db, admin_user
):
    from app.database import schema
    from app.ui.main_window import MainWindow

    app = _qt_app()
    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    candidate_credentials = _insert_user(
        fresh_db, "candidate_ui", "candidate-ui@example.com",
        "candidate", "Candidate UI"
    )
    candidate_email = candidate_credentials[0]
    company_credentials = _insert_user(
        fresh_db, "company_ui", "company-ui@example.com",
        "company", "Company UI"
    )
    company_email = company_credentials[0]
    expert_email, _ = _insert_user(
        fresh_db, "expert_ui", "expert-ui@example.com",
        "expert", "Expert UI"
    )
    candidate_id = fresh_db.fetchone(
        "SELECT id FROM users WHERE email = ?", (candidate_email,)
    )["id"]
    company_id = fresh_db.fetchone(
        "SELECT id FROM users WHERE email = ?", (company_email,)
    )["id"]
    expert_id = fresh_db.fetchone(
        "SELECT id FROM users WHERE email = ?", (expert_email,)
    )["id"]
    fresh_db.execute(
        "INSERT INTO candidate_profiles(user_id, headline) VALUES (?, ?)",
        (candidate_id, "Candidate profile"),
    )
    fresh_db.execute(
        "INSERT INTO company_profiles(user_id, company_name) VALUES (?, ?)",
        (company_id, "Company profile"),
    )
    fresh_db.execute(
        "INSERT INTO expert_profiles(user_id, title) VALUES (?, ?)",
        (expert_id, "Expert profile"),
    )
    fresh_db.execute(
        "INSERT INTO skills(name, category, level) VALUES (?, ?, ?)",
        ("Existing skill", "Engineering", "beginner"),
    )
    auth = AuthController()
    login = auth.login(*admin_user)
    assert login.success

    window = MainWindow()
    window._show_dashboard(login.user)
    assert isinstance(window._dashboard, AdminDashboardScreen)
    assert (
        "Tổng chưa xóa: 4"
        in window._dashboard._users_statistics_label.text()
    )
    assert "Candidate: 1" in window._dashboard._profiles_statistics_label.text()
    assert "Tổng: 1" in window._dashboard._skills_statistics_label.text()

    window._dashboard._users_card_button.click()
    users = window._user_management
    assert isinstance(users, UserManagementScreen)
    assert window._stack.currentWidget() is users
    assert users._table.rowCount() == 4
    users._role_filter.setCurrentIndex(users._role_filter.findData("candidate"))
    assert users._table.rowCount() == 1
    users._table.selectRow(0)
    users._toggle_active_button.click()
    assert fresh_db.fetchone(
        "SELECT is_active FROM users WHERE email = ?", (candidate_email,)
    )["is_active"] == 0
    assert "Đã khóa tài khoản" in users._status_label.text()
    users._status_filter.setCurrentIndex(users._status_filter.findData(False))
    assert users._table.rowCount() == 1
    users._table.selectRow(0)
    assert users._toggle_active_button.text() == "Mở khoá tài khoản"
    users._toggle_active_button.click()
    assert fresh_db.fetchone(
        "SELECT is_active FROM users WHERE email = ?", (candidate_email,)
    )["is_active"] == 1
    assert "Đã mở khóa tài khoản" in users._status_label.text()
    users._back_button.click()

    window._dashboard._skills_card_button.click()
    skills = window._skill_management
    assert isinstance(skills, SkillManagementScreen)
    assert window._stack.currentWidget() is skills
    assert skills._table.rowCount() == 1
    skills._name_input.setText("Python")
    skills._category_input.setText("Engineering")
    skills._description_input.setPlainText("Programming language")
    skills._level_combo.setCurrentIndex(skills._level_combo.findData("advanced"))
    skills._save_button.click()
    assert skills._table.rowCount() == 2
    assert "Đã thêm kỹ năng 'Python'" in skills._status_label.text()

    python_row = next(
        row
        for row in range(skills._table.rowCount())
        if skills._table.item(row, 1).text() == "Python"
    )
    skills._table.selectRow(python_row)
    skills._edit_button.click()
    skills._name_input.setText("Python Advanced")
    skills._save_button.click()
    assert fresh_db.fetchone(
        "SELECT name FROM skills WHERE name = 'Python Advanced'"
    ) is not None
    assert "Đã cập nhật kỹ năng" in skills._status_label.text()

    python_row = next(
        row
        for row in range(skills._table.rowCount())
        if skills._table.item(row, 1).text() == "Python Advanced"
    )
    skills._table.selectRow(python_row)
    skills._toggle_active_button.click()
    assert fresh_db.fetchone(
        "SELECT is_active FROM skills WHERE name = 'Python Advanced'"
    )["is_active"] == 0
    assert "Đã ngừng sử dụng kỹ năng" in skills._status_label.text()
    skills._back_button.click()
    window._dashboard._refresh_statistics_button.click()
    assert "Tổng: 2" in window._dashboard._skills_statistics_label.text()

    auth.logout()
    company_login = auth.login(*company_credentials)
    assert company_login.success
    window._show_dashboard(company_login.user)
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
    assert screen._table.rowCount() == 0
    screen._search_input.clear()
    screen._table.selectRow(0)
    screen._toggle_active_button.click()

    assert controller.actions == [(7, False)]
    assert screen._table.item(0, 4).text() == "Đã khoá"
    assert "Đã khóa tài khoản" in screen._status_label.text()
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
