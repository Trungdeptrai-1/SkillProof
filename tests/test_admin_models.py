"""Tests for admin-facing model DTOs and legacy schema compatibility."""

import sqlite3

from server.database.schema import create_all_tables
from server.models import (
    AdminStatisticsModel,
    AppSettingModel,
    SkillModel,
    UserModel,
)


def _connection(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def test_user_model_maps_soft_delete_without_exposing_password(fresh_db):
    connection = fresh_db.get_connection()
    connection.execute(
        "INSERT INTO users (username, email, password, full_name, role, is_deleted) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("deleted-user", "deleted@example.test", "hash", "Deleted User", "candidate", 1),
    )
    row = connection.execute(
        "SELECT * FROM users WHERE username = ?", ("deleted-user",)
    ).fetchone()

    user = UserModel.from_row(row)

    assert user.is_deleted is True
    assert user.is_active is True
    assert not hasattr(user, "password")


def test_user_model_defaults_soft_delete_for_legacy_rows():
    legacy_row = {
        "id": 4,
        "username": "legacy",
        "email": "legacy@example.test",
        "full_name": "Legacy User",
        "role": "candidate",
        "avatar_path": None,
        "is_active": 1,
        "created_at": "2026-01-01",
        "updated_at": "2026-01-01",
    }

    assert UserModel.from_row(legacy_row).is_deleted is False


def test_skill_model_maps_existing_skill_columns(fresh_db):
    connection = fresh_db.get_connection()
    connection.execute(
        "INSERT INTO skills (name, description, category, level, is_active) "
        "VALUES (?, ?, ?, ?, ?)",
        ("Python", "Programming language", "Engineering", "advanced", 0),
    )
    row = connection.execute(
        "SELECT * FROM skills WHERE name = ?", ("Python",)
    ).fetchone()

    skill = SkillModel.from_row(row)

    assert skill.name == "Python"
    assert skill.category == "Engineering"
    assert skill.level == "advanced"
    assert skill.is_active is False


def test_app_setting_model_maps_existing_key_value_row(fresh_db):
    row = fresh_db.get_connection().execute(
        "SELECT key, value, updated_at FROM app_settings WHERE key = 'theme'"
    ).fetchone()

    setting = AppSettingModel.from_row(row)

    assert setting.key == "theme"
    assert setting.value == "navy"
    assert setting.updated_at


def test_admin_statistics_model_maps_database_aggregate_aliases(tmp_path):
    connection = _connection(tmp_path / "statistics.db")
    try:
        row = connection.execute(
            """
            SELECT 4 AS total_users,
                   2 AS active_users,
                   1 AS inactive_users,
                   1 AS deleted_users,
                   3 AS total_skills,
                   2 AS active_skills,
                   1 AS inactive_skills,
                   5 AS total_certificates,
                   6 AS total_courses,
                   7 AS total_enrollments,
                   8 AS total_assessments
            """
        ).fetchone()

        statistics = AdminStatisticsModel.from_row(row)

        assert statistics.total_users == 4
        assert statistics.active_users == 2
        assert statistics.deleted_users == 1
        assert statistics.total_skills == 3
        assert statistics.total_assessments == 8
    finally:
        connection.close()


def test_full_migration_preserves_legacy_users_and_adds_soft_delete(legacy_db):
    connection = legacy_db.get_connection()
    before = connection.execute(
        "SELECT id, username, email FROM users ORDER BY id"
    ).fetchall()
    legacy_user = UserModel.from_row(
        connection.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
    )
    assert legacy_user.is_deleted is False

    create_all_tables(connection)

    after = connection.execute(
        "SELECT id, username, email FROM users ORDER BY id"
    ).fetchall()
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(users)")
    }
    migrated_user = UserModel.from_row(
        connection.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
    )

    assert [tuple(row) for row in after] == [tuple(row) for row in before]
    assert "is_deleted" in columns
    assert migrated_user.is_deleted is False

    create_all_tables(connection)
    assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == len(before)
