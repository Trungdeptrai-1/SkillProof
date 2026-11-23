"""Focused tests for the server database/model layer and legacy imports."""

import sqlite3

import pytest


@pytest.fixture
def isolated_database_connection(tmp_path, monkeypatch):
    from server.database import connection as connection_module

    if connection_module.DatabaseConnection._connection is not None:
        connection_module.DatabaseConnection._connection.close()
    connection_module.DatabaseConnection._instance = None
    connection_module.DatabaseConnection._connection = None

    database_path = tmp_path / "connection_test.db"
    monkeypatch.setattr(connection_module, "DB_PATH", str(database_path))
    monkeypatch.setattr(connection_module, "DATA_DIR", str(tmp_path))

    yield connection_module.db

    connection_module.db.close()
    connection_module.DatabaseConnection._instance = None
    connection_module.DatabaseConnection._connection = None


def test_database_connection_creates_temporary_sqlite_file(isolated_database_connection):
    connection = isolated_database_connection.connect()

    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("SELECT 1").fetchone()[0] == 1


def test_schema_initializes_on_temporary_database(tmp_path):
    from server.database.schema import create_all_tables, is_first_run

    database_path = tmp_path / "schema_test.db"
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        create_all_tables(connection)

        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        user_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(users)")
        }

        assert {"users", "app_settings", "company_profiles"} <= table_names
        assert "is_deleted" in user_columns
        assert is_first_run(connection)
    finally:
        connection.close()


def test_user_model_maps_database_row_without_password(tmp_path):
    from server.database.schema import create_all_tables
    from server.models.user_model import UserModel

    connection = sqlite3.connect(tmp_path / "user_model_test.db")
    connection.row_factory = sqlite3.Row
    try:
        create_all_tables(connection)
        connection.execute(
            "INSERT INTO users (username, email, password, full_name, role) "
            "VALUES (?, ?, ?, ?, ?)",
            ("phat", "phat@example.test", "hashed-value", "  Phat Nguyen  ", "candidate"),
        )
        row = connection.execute(
            "SELECT * FROM users WHERE username = ?", ("phat",)
        ).fetchone()

        user = UserModel.from_row(row)

        assert user.username == "phat"
        assert user.display_name == "Phat Nguyen"
        assert user.role == "candidate"
        assert user.is_active is True
        assert not hasattr(user, "password")
    finally:
        connection.close()


def test_legacy_imports_reference_server_implementations():
    from app.database import connection as legacy_connection
    from app.database import schema as legacy_schema
    from app.database.connection import db as legacy_db
    from app.database.schema import create_all_tables as legacy_create_all_tables
    from app.models.user_model import UserModel as LegacyUserModel
    from server.database import connection, schema
    from server.models.user_model import UserModel

    assert legacy_connection is connection
    assert legacy_schema is schema
    assert legacy_db is connection.db
    assert legacy_create_all_tables is schema.create_all_tables
    assert LegacyUserModel is UserModel
