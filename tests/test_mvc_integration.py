import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.database.schema import is_first_run
from app.services.auth_service import LoginResult
from app.services.candidate_profile_service import CandidateProfileResult
from app.services.company_profile_service import ProfileResult
from app.services.contract_service import ContractResult
from app.services.expert_profile_service import ExpertProfileResult
from app.services.expert_search_service import SearchResult
from app.services.task_service import TaskResult
from app.utils.helpers import hash_password, verify_password
from app.ui.screens.candidate_profile_screen import CandidateProfileScreen
from server.controllers.auth_controller import AuthController
from server.controllers.collaboration_controller import (
    ContractController,
    ExpertSearchController,
    TaskController,
)
from server.controllers.profile_controller import (
    CandidateProfileController,
    CompanyProfileController,
    ExpertProfileController,
)
from server.controllers.setup_controller import SetupController
from server.controllers.user_controller import UserController


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _insert_user(database, username, email, role, password="StrongPass1"):
    database.execute(
        """
        INSERT INTO users (username, email, password, full_name, role, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (username, email, hash_password(password), username.title(), role),
    )
    return email, password


def test_registration_and_login_flow_uses_controllers(fresh_db, auth):
    registration = UserController().register(
        "MVC Candidate", "mvc-candidate@example.com", "CandidatePass1",
        "CandidatePass1",
    )

    assert registration.success
    assert registration.user.role == "candidate"

    login = AuthController().login("mvc-candidate@example.com", "CandidatePass1")

    assert login.status == LoginResult.SUCCESS
    assert login.user.id == registration.user.id
    AuthController().logout()


def test_registration_handles_duplicate_generated_username(fresh_db, auth):
    controller = UserController()

    first = controller.register(
        "First User", "shared-name@example.com", "StrongPass1", "StrongPass1"
    )
    second = controller.register(
        "Second User", "shared-name@another.example", "StrongPass1", "StrongPass1"
    )

    assert first.success
    assert second.success
    assert second.user.username == "shared-name_2"


def test_candidate_profile_controller_reaches_view(qt_app, fresh_db, auth):
    registered = UserController().register(
        "Candidate View", "candidate-view@example.com", "CandidatePass1",
        "CandidatePass1",
    )
    assert registered.success
    assert AuthController().login(
        "candidate-view@example.com", "CandidatePass1"
    ).success

    controller = CandidateProfileController()
    result = controller.create_profile(
        "Python Developer", "Builds desktop apps", "https://example.com", 4
    )
    assert result.success

    screen = CandidateProfileScreen()
    assert screen._portfolio_input.text() == "https://example.com"
    assert screen._headline_input.text() == "Python Developer"
    screen.close()
    screen.deleteLater()
    qt_app.processEvents()
    AuthController().logout()


def test_admin_setup_and_login_use_service_and_sqlite_transaction(fresh_db, auth):
    password = "AdminStrong1"
    result = SetupController().create_admin(
        "Initial Admin", "initial-admin@example.com", password, password
    )

    assert result.success
    assert not is_first_run()
    row = fresh_db.fetchone(
        "SELECT username, role, password FROM users WHERE email = ?",
        ("initial-admin@example.com",),
    )
    assert row["role"] == "admin"
    assert verify_password(password, row["password"])
    assert AuthController().login("initial-admin@example.com", password).success
    AuthController().logout()


def test_invalid_admin_setup_does_not_change_setup_state(fresh_db, auth):
    result = SetupController().create_admin(
        "Initial Admin", "invalid-email", "weak", "different"
    )

    assert not result.success
    assert is_first_run()
    assert fresh_db.fetchone("SELECT id FROM users WHERE role = 'admin'") is None


def test_company_expert_contract_and_task_flow_uses_controllers(fresh_db, auth):
    company_email, company_password = _insert_user(
        fresh_db, "mvc-company", "mvc-company@example.com", "company"
    )
    expert_email, expert_password = _insert_user(
        fresh_db, "mvc-expert", "mvc-expert@example.com", "expert"
    )

    auth_controller = AuthController()
    expert_controller = ExpertProfileController()
    assert auth_controller.login(expert_email, expert_password).success
    expert_profile = expert_controller.create_profile(
        "Python Expert", specialization="Python", hourly_rate=1000
    )
    assert expert_profile.success
    auth_controller.logout()

    assert auth_controller.login(company_email, company_password).success
    assert CompanyProfileController().create_profile("MVC Company").success
    search = ExpertSearchController().search(specialization="Python")
    assert search.success
    assert len(search.experts) == 1

    contracts = ContractController()
    invitation = contracts.invite_expert(search.experts[0].profile_id)
    assert invitation.success
    contract_id = invitation.contract.id
    auth_controller.logout()

    assert auth_controller.login(expert_email, expert_password).success
    assert contracts.accept_contract(contract_id).status == ContractResult.SUCCESS
    auth_controller.logout()

    assert auth_controller.login(company_email, company_password).success
    task = TaskController().create_task(contract_id, "Grade assessment", "grading")
    assert task.success
    task_id = task.task.id
    auth_controller.logout()

    assert auth_controller.login(expert_email, expert_password).success
    task_controller = TaskController()
    assert task_controller.start_task(task_id).status == TaskResult.SUCCESS
    assert task_controller.complete_task(task_id).status == TaskResult.SUCCESS
    auth_controller.logout()

    assert auth_controller.login(company_email, company_password).success
    assert contracts.complete_contract(contract_id).status == ContractResult.SUCCESS
    auth_controller.logout()


def test_candidate_controller_preserves_service_role_checks(fresh_db, auth):
    registration = UserController().register(
        "Candidate", "role-check@example.com", "CandidatePass1",
        "CandidatePass1",
    )
    assert registration.success
    assert AuthController().login(
        "role-check@example.com", "CandidatePass1"
    ).success

    assert CompanyProfileController().get_profile().status == ProfileResult.WRONG_ROLE
    assert ExpertProfileController().get_profile().status == ExpertProfileResult.WRONG_ROLE
    assert CandidateProfileController().get_profile().status == CandidateProfileResult.NOT_FOUND
    AuthController().logout()


def test_collaboration_controllers_preserve_authentication_guards(fresh_db, auth):
    assert ExpertSearchController().search().status == SearchResult.NOT_LOGGED_IN
    assert ContractController().list_my_contracts().status == ContractResult.NOT_LOGGED_IN
    assert TaskController().list_my_tasks().status == TaskResult.NOT_LOGGED_IN
