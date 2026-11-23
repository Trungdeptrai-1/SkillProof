"""Tests for administrator account and skill management."""

import sqlite3
from unittest.mock import Mock, patch

import pytest

import server.services.admin_service as admin_module
from server.controllers.admin_controller import AdminController
from server.models.user_model import UserModel
from server.services.admin_service import AdminResult, AdminService
from server.services.auth_service import AuthService, SessionManager
from app.utils.helpers import hash_password


@pytest.fixture(autouse=True)
def reset_session():
    SessionManager._instance = None
    yield
    SessionManager._instance = None


@pytest.fixture
def admin_controller(admin_user):
    email, password = admin_user
    assert AuthService().login(email, password).success
    yield AdminController(AdminService())
    SessionManager.instance().end_session()


def _insert_user(
    fresh_db,
    username: str,
    role: str,
    *,
    active: bool = True,
    deleted: bool = False,
) -> int:
    cursor = fresh_db.execute(
        """
        INSERT INTO users
            (username, email, password, full_name, role, is_active, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            f"{username}@admin.test",
            hash_password("AdminTest@1"),
            username.title(),
            role,
            int(active),
            int(deleted),
        ),
    )
    return cursor.lastrowid


def _session_for_role(role: str) -> None:
    SessionManager.instance().start_session(
        UserModel(
            id=999,
            username=f"{role}_user",
            email=f"{role}@roles.test",
            full_name="Role User",
            role=role,
            avatar_path=None,
            is_active=True,
            created_at="2026-01-01",
            updated_at="2026-01-01",
        )
    )


def test_admin_lists_searches_and_filters_non_deleted_users(
    admin_controller, fresh_db
):
    alice_id = _insert_user(fresh_db, "alice-candidate", "candidate")
    _insert_user(fresh_db, "inactive-candidate", "candidate", active=False)
    _insert_user(
        fresh_db, "deleted-candidate", "candidate", deleted=True
    )
    _insert_user(fresh_db, "alice-company", "company")

    result = admin_controller.list_users(
        search="ALICE", role="candidate", is_active=True
    )

    assert result.success
    assert [user.id for user in result.users] == [alice_id]
    assert result.users[0].email == "alice-candidate@admin.test"
    assert not hasattr(result.users[0], "password")

    filtered = admin_controller.list_users(role="candidate", is_active=False)
    assert filtered.success
    assert [user.username for user in filtered.users] == ["inactive-candidate"]


def test_invalid_user_filters_are_rejected(admin_controller):
    assert (
        admin_controller.list_users(role="invalid").status
        == AdminResult.INVALID_ROLE
    )
    assert (
        admin_controller.list_users(is_active=1).status
        == AdminResult.INVALID_INPUT
    )
    assert (
        admin_controller.list_users(search=None).status
        == AdminResult.INVALID_INPUT
    )


def test_controller_rejects_bad_request_shapes_before_service_call():
    service = Mock(spec=AdminService)
    controller = AdminController(service)

    assert controller.list_users(search=[]).status == AdminResult.INVALID_INPUT
    assert (
        controller.set_user_active(True, False).status
        == AdminResult.INVALID_INPUT
    )
    assert controller.create_skill(None).status == AdminResult.INVALID_INPUT
    service.list_users.assert_not_called()
    service.set_user_active.assert_not_called()
    service.create_skill.assert_not_called()


def test_admin_can_change_user_status_but_not_disable_last_active_admin(
    admin_controller, fresh_db, admin_user
):
    admin_email, _ = admin_user
    admin_id = fresh_db.fetchone(
        "SELECT id FROM users WHERE email = ?", (admin_email,)
    )["id"]
    second_admin_id = _insert_user(fresh_db, "second-admin", "admin")
    candidate_id = _insert_user(fresh_db, "status-candidate", "candidate")

    blocked = admin_controller.set_user_active(candidate_id, False)
    assert blocked.success
    assert blocked.user.is_active is False

    disabled_admin = admin_controller.set_user_active(second_admin_id, False)
    assert disabled_admin.success
    assert disabled_admin.user.is_active is False

    last_admin = admin_controller.set_user_active(admin_id, False)
    assert last_admin.status == AdminResult.LAST_ACTIVE_ADMIN
    assert fresh_db.fetchone(
        "SELECT is_active FROM users WHERE id = ?", (admin_id,)
    )["is_active"] == 1


def test_user_status_rejects_missing_deleted_and_invalid_ids(
    admin_controller, fresh_db
):
    deleted_id = _insert_user(
        fresh_db, "deleted-user", "candidate", deleted=True
    )

    assert (
        admin_controller.set_user_active(99999, False).status
        == AdminResult.USER_NOT_FOUND
    )
    assert (
        admin_controller.set_user_active(deleted_id, True).status
        == AdminResult.USER_NOT_FOUND
    )
    assert (
        admin_controller.set_user_active(True, False).status
        == AdminResult.INVALID_INPUT
    )


def test_admin_statistics_cover_accounts_profiles_and_skills(
    admin_controller, fresh_db
):
    candidate_id = _insert_user(fresh_db, "stats-candidate", "candidate")
    company_id = _insert_user(fresh_db, "stats-company", "company")
    expert_id = _insert_user(
        fresh_db, "stats-expert", "expert", active=False
    )
    _insert_user(fresh_db, "stats-deleted", "student", deleted=True)
    fresh_db.execute(
        "INSERT INTO candidate_profiles(user_id, headline) VALUES (?, ?)",
        (candidate_id, "Candidate"),
    )
    fresh_db.execute(
        """
        INSERT INTO company_profiles(user_id, company_name)
        VALUES (?, ?)
        """,
        (company_id, "Stats Company"),
    )
    fresh_db.execute(
        "INSERT INTO expert_profiles(user_id, title) VALUES (?, ?)",
        (expert_id, "Expert"),
    )
    fresh_db.execute(
        "INSERT INTO skills(name, level, is_active) VALUES (?, ?, ?)",
        ("Active Skill", "beginner", 1),
    )
    fresh_db.execute(
        "INSERT INTO skills(name, level, is_active) VALUES (?, ?, ?)",
        ("Inactive Skill", "advanced", 0),
    )

    result = admin_controller.get_statistics()

    assert result.success
    stats = result.statistics
    assert stats.total_users == 4
    assert stats.active_users == 3
    assert stats.inactive_users == 1
    assert stats.deleted_users == 1
    assert stats.users_by_role["admin"] == 1
    assert stats.users_by_role["candidate"] == 1
    assert stats.users_by_role["company"] == 1
    assert stats.users_by_role["expert"] == 1
    assert stats.users_by_role["student"] == 0
    assert stats.candidate_profiles == 1
    assert stats.company_profiles == 1
    assert stats.expert_profiles == 1
    assert (stats.total_skills, stats.active_skills, stats.inactive_skills) == (
        2,
        1,
        1,
    )


def test_admin_skill_create_search_filter_update_and_deactivate(admin_controller):
    created = admin_controller.create_skill(
        "Python",
        description="Programming language",
        category="Engineering",
        level="advanced",
    )

    assert created.success
    skill_id = created.skill.id
    assert created.skill.is_active

    filtered = admin_controller.list_skills(
        search="PYTH",
        category="engineering",
        level="advanced",
        is_active=True,
    )
    assert filtered.success
    assert [skill.id for skill in filtered.skills] == [skill_id]

    updated = admin_controller.update_skill(
        skill_id,
        "Python Development",
        "Updated description",
        "Engineering",
        "expert",
    )
    assert updated.success
    assert updated.skill.level == "expert"
    assert updated.skill.description == "Updated description"

    deactivated = admin_controller.set_skill_active(skill_id, False)
    assert deactivated.success
    assert not deactivated.skill.is_active
    assert admin_controller.list_skills(is_active=False).skills[0].id == skill_id


def test_skill_validation_duplicates_and_missing_ids(admin_controller):
    assert (
        admin_controller.create_skill("  ").status
        == AdminResult.EMPTY_SKILL_NAME
    )
    assert (
        admin_controller.create_skill("Rust", level="invalid").status
        == AdminResult.INVALID_SKILL_LEVEL
    )
    assert admin_controller.create_skill("Rust").success
    assert (
        admin_controller.create_skill("Rust").status
        == AdminResult.SKILL_ALREADY_EXISTS
    )
    assert (
        admin_controller.update_skill(99999, "Ghost").status
        == AdminResult.SKILL_NOT_FOUND
    )
    assert (
        admin_controller.set_skill_active(99999, True).status
        == AdminResult.SKILL_NOT_FOUND
    )
    assert (
        admin_controller.create_skill(None).status
        == AdminResult.INVALID_INPUT
    )


@pytest.mark.parametrize(
    "role",
    ["instructor", "student", "candidate", "company", "expert"],
)
@pytest.mark.usefixtures("fresh_db")
def test_non_admin_roles_are_denied_every_admin_operation(role):
    _session_for_role(role)
    controller = AdminController(AdminService())

    results = (
        controller.list_users(),
        controller.set_user_active(1, False),
        controller.get_statistics(),
        controller.list_skills(),
        controller.create_skill("Denied"),
        controller.update_skill(1, "Denied"),
        controller.set_skill_active(1, False),
    )

    assert all(result.status == AdminResult.FORBIDDEN for result in results)


@pytest.mark.usefixtures("fresh_db")
def test_admin_operations_require_a_logged_in_session():
    result = AdminController(AdminService()).list_users()

    assert result.status == AdminResult.NOT_LOGGED_IN


@pytest.mark.parametrize("field, value", [("is_active", 0), ("is_deleted", 1)])
def test_stale_admin_session_is_denied_after_account_is_revoked(
    admin_controller, fresh_db, admin_user, field, value
):
    email, _ = admin_user
    fresh_db.execute(
        f"UPDATE users SET {field} = ? WHERE email = ?",
        (value, email),
    )

    result = admin_controller.list_users()

    assert result.status == AdminResult.FORBIDDEN
    assert not SessionManager.instance().is_logged_in


def test_database_errors_return_explicit_results(admin_controller):
    with patch.object(
        admin_module.db,
        "fetchall",
        side_effect=sqlite3.OperationalError("database unavailable"),
    ):
        assert admin_controller.list_users().status == AdminResult.DB_ERROR

    with patch.object(
        admin_module.db,
        "fetchone",
        side_effect=sqlite3.OperationalError("database unavailable"),
    ):
        assert admin_controller.get_statistics().status == AdminResult.DB_ERROR
    with patch.object(
        admin_module.db,
        "get_connection",
        side_effect=sqlite3.OperationalError("database unavailable"),
    ):
        assert (
            admin_controller.set_user_active(1, False).status
            == AdminResult.DB_ERROR
        )


def test_sqlite_write_failure_rolls_back_user_status(admin_controller, fresh_db):
    candidate_id = _insert_user(fresh_db, "trigger-blocked", "candidate")
    fresh_db.get_connection().execute(
        """
        CREATE TRIGGER reject_admin_service_status
        BEFORE UPDATE OF is_active ON users
        BEGIN
            SELECT RAISE(ABORT, 'status changes disabled for test');
        END
        """
    )
    fresh_db.get_connection().commit()

    result = admin_controller.set_user_active(candidate_id, False)

    assert result.status == AdminResult.DB_ERROR
    assert fresh_db.fetchone(
        "SELECT is_active FROM users WHERE id = ?", (candidate_id,)
    )["is_active"] == 1
