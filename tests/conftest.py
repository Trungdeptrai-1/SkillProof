# -*- coding: utf-8 -*-
"""
conftest.py — Pytest fixtures dùng chung cho toàn bộ test suite SkillProof.

Nguyên tắc:
- Mỗi test dùng DB SQLite riêng trong bộ nhớ (:memory:) hoặc tmp file.
- KHÔNG thao tác trên data/skillproof.db thật.
- Sau mỗi test, DB được teardown tự động.
"""

import sys
import os
import sqlite3
import pytest

# Đảm bảo project root trong sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ── Fixture: DB test trong tmp file (hỗ trợ re-open) ──────────────────────────

@pytest.fixture()
def test_db_path(tmp_path):
    """Trả về đường dẫn file SQLite tạm (unique cho mỗi test)."""
    return str(tmp_path / "test_skillproof.db")


@pytest.fixture()
def fresh_db(test_db_path, monkeypatch):
    """
    DB SkillProof sạch hoàn toàn — không có admin seed.
    Dùng cho test DB mới (first-run scenario).
    """
    from app.database import connection as conn_module
    from app.database.schema import create_all_tables

    # Patch DB_PATH và DATA_DIR để trỏ vào tmp
    monkeypatch.setattr(conn_module, "_DB_PATH_OVERRIDE", test_db_path, raising=False)

    # Reset singleton
    old_instance = conn_module.DatabaseConnection._instance
    old_conn     = conn_module.DatabaseConnection._connection
    conn_module.DatabaseConnection._instance   = None
    conn_module.DatabaseConnection._connection = None

    # Patch hằng số đường dẫn
    import app.utils.constants as consts
    monkeypatch.setattr(consts, "DB_PATH",  test_db_path)
    monkeypatch.setattr(consts, "DATA_DIR", str(os.path.dirname(test_db_path)))
    import app.database.connection as dc
    monkeypatch.setattr(dc, "DB_PATH",  test_db_path)
    monkeypatch.setattr(dc, "DATA_DIR", str(os.path.dirname(test_db_path)))

    create_all_tables()
    conn = conn_module.db

    yield conn

    # Teardown
    conn.close()
    conn_module.DatabaseConnection._instance   = None
    conn_module.DatabaseConnection._connection = None


@pytest.fixture()
def legacy_db(test_db_path, monkeypatch):
    """
    DB mô phỏng Giai đoạn 01 cũ: có admin với legacy SHA-256+salt hash.
    Dùng để test migration và backward compat.
    """
    from app.database import connection as conn_module
    import app.utils.constants as consts
    import app.database.connection as dc

    monkeypatch.setattr(consts, "DB_PATH",  test_db_path)
    monkeypatch.setattr(consts, "DATA_DIR", str(os.path.dirname(test_db_path)))
    monkeypatch.setattr(dc, "DB_PATH",  test_db_path)
    monkeypatch.setattr(dc, "DATA_DIR", str(os.path.dirname(test_db_path)))

    conn_module.DatabaseConnection._instance   = None
    conn_module.DatabaseConnection._connection = None

    # Tạo schema trực tiếp bằng SQL cũ (giả lập DB phase 01)
    _LEGACY_SCHEMA = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email    TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student'
             CHECK(role IN ('admin','instructor','student')),
        avatar_path TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS skills (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT, category TEXT, level TEXT NOT NULL DEFAULT 'beginner', is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
    CREATE TABLE IF NOT EXISTS certificates (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE, issued_at TEXT NOT NULL DEFAULT (datetime('now','localtime')), expires_at TEXT, score REAL, status TEXT NOT NULL DEFAULT 'active', cert_code TEXT NOT NULL UNIQUE, UNIQUE(user_id, skill_id));
    CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, skill_id INTEGER REFERENCES skills(id) ON DELETE SET NULL, instructor_id INTEGER REFERENCES users(id) ON DELETE SET NULL, duration_hours INTEGER, is_published INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
    CREATE TABLE IF NOT EXISTS enrollments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE, enrolled_at TEXT NOT NULL DEFAULT (datetime('now','localtime')), completed_at TEXT, progress REAL NOT NULL DEFAULT 0.0, UNIQUE(user_id, course_id));
    CREATE TABLE IF NOT EXISTS assessments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE, score REAL NOT NULL, max_score REAL NOT NULL DEFAULT 100, taken_at TEXT NOT NULL DEFAULT (datetime('now','localtime')), notes TEXT);
    """
    _LEGACY_SEED = """
    INSERT OR IGNORE INTO app_settings (key, value) VALUES
        ('app_version','1.0.0'), ('setup_done','0'), ('theme','navy');
    INSERT OR IGNORE INTO users (username,email,password,full_name,role) VALUES
        ('admin','admin@skillproof.local',
         '67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56',
         'Quan tri vien','admin');
    """
    raw = sqlite3.connect(test_db_path)
    raw.row_factory = sqlite3.Row
    raw.executescript(_LEGACY_SCHEMA)
    raw.executescript(_LEGACY_SEED)
    raw.commit()
    raw.close()

    # Kết nối qua DatabaseConnection (với PRAGMA)
    conn_obj = conn_module.db.connect()
    yield conn_module.db

    conn_module.db.close()
    conn_module.DatabaseConnection._instance   = None
    conn_module.DatabaseConnection._connection = None


@pytest.fixture()
def auth(fresh_db):
    """AuthService với fresh DB."""
    # Reset session singleton giữa các test
    from app.services.auth_service import AuthService, SessionManager
    SessionManager._instance = None
    svc = AuthService()
    yield svc
    SessionManager._instance = None


@pytest.fixture()
def session_mgr():
    """SessionManager reset sạch."""
    from app.services.auth_service import SessionManager
    SessionManager._instance = None
    mgr = SessionManager.instance()
    yield mgr
    mgr.end_session()
    SessionManager._instance = None


@pytest.fixture()
def admin_user(fresh_db):
    """Tạo tài khoản admin PBKDF2 trong fresh_db, trả về (email, password)."""
    from app.utils.helpers import hash_password
    pw    = "AdminTest@1"
    email = "admin_test@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,'admin',1)",
        ("admin_test", email, hash_password(pw), "Admin Test"),
    )
    fresh_db.get_connection().execute(
        "INSERT OR REPLACE INTO app_settings(key,value) VALUES('setup_done','1')"
    )
    fresh_db.get_connection().commit()
    return email, pw


@pytest.fixture()
def candidate_user(fresh_db):
    """Tạo tài khoản candidate PBKDF2."""
    from app.utils.helpers import hash_password
    pw    = "Candidate@1"
    email = "cand@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,'candidate',1)",
        ("cand_test", email, hash_password(pw), "Candidate Test"),
    )
    return email, pw


@pytest.fixture()
def inactive_user(fresh_db):
    """Tài khoản bị khoá."""
    from app.utils.helpers import hash_password
    pw    = "Inactive@1"
    email = "inactive@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,'candidate',0)",
        ("inactive_test", email, hash_password(pw), "Inactive Test"),
    )
    return email, pw
