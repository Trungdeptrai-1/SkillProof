"""
Định nghĩa schema và khởi tạo CSDL SkillProof.
Chạy create_all_tables() một lần khi khởi động ứng dụng.
"""

import logging
from app.database.connection import db

logger = logging.getLogger(__name__)


# ── Câu lệnh DDL ─────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Bảng người dùng
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    email       TEXT    NOT NULL UNIQUE,
    password    TEXT    NOT NULL,
    full_name   TEXT    NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'candidate'
                        CHECK(role IN ('admin','instructor','student','candidate','company','expert')),
    avatar_path TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Bảng kỹ năng / skill
CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT,
    category    TEXT,
    level       TEXT    NOT NULL DEFAULT 'beginner'
                        CHECK(level IN ('beginner','intermediate','advanced','expert')),
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Bảng chứng chỉ / certificate
CREATE TABLE IF NOT EXISTS certificates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    skill_id     INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    issued_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    expires_at   TEXT,
    score        REAL,
    status       TEXT    NOT NULL DEFAULT 'active'
                         CHECK(status IN ('active','expired','revoked')),
    cert_code    TEXT    NOT NULL UNIQUE,
    UNIQUE(user_id, skill_id)
);

-- Bảng khoá học
CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT,
    skill_id    INTEGER REFERENCES skills(id) ON DELETE SET NULL,
    instructor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    duration_hours INTEGER,
    is_published INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Bảng đăng ký khoá học
CREATE TABLE IF NOT EXISTS enrollments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    course_id   INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
    enrolled_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    completed_at TEXT,
    progress    REAL    NOT NULL DEFAULT 0.0
                        CHECK(progress BETWEEN 0 AND 100),
    UNIQUE(user_id, course_id)
);

-- Bảng đánh giá / assessment
CREATE TABLE IF NOT EXISTS assessments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skills(id)  ON DELETE CASCADE,
    score       REAL    NOT NULL CHECK(score BETWEEN 0 AND 100),
    max_score   REAL    NOT NULL DEFAULT 100,
    taken_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    notes       TEXT
);

-- Bảng cài đặt ứng dụng (key-value)
CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT    PRIMARY KEY,
    value       TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

# ── Trigger cập nhật updated_at ──────────────────────────────────────────────

TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_users_updated
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;
"""

# ── Dữ liệu mặc định ─────────────────────────────────────────────────────────

SEED_SQL = """
INSERT OR IGNORE INTO app_settings (key, value) VALUES
    ('app_version',  '1.0.0'),
    ('setup_done',   '0'),
    ('theme',        'navy');

INSERT OR IGNORE INTO users (username, email, password, full_name, role)
VALUES (
    'admin',
    'admin@skillproof.local',
    '67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56',
    'Quan tri vien',
    'admin'
);
"""
# password = hash_password('admin') via helpers.py (SHA-256 + salt)
# verify_password('admin', hash) == True


# ── Hàm khởi tạo ─────────────────────────────────────────────────────────────

def create_all_tables() -> None:
    """Tạo tất cả bảng và seed dữ liệu mặc định."""
    try:
        conn = db.connect()
        conn.executescript(SCHEMA_SQL)
        conn.executescript(TRIGGERS_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        _apply_migrations(conn)
        logger.info("Schema CSDL đã khởi tạo thành công.")
    except Exception as exc:
        logger.exception("Lỗi khởi tạo schema: %s", exc)
        raise


def _apply_migrations(conn) -> None:
    """
    Áp dụng các migration nhỏ để đồng bộ CSDL hiện có.
    An toàn khi chạy nhiều lần (idempotent).
    """
    # MIG-001: Cập nhật hash mật khẩu admin về hash_password('admin')
    # Lý do: seed ban đầu dùng SHA-256 thuần, helpers.hash_password() dùng salt.
    correct_hash = "67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56"
    old_hash     = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
    row = conn.execute(
        "SELECT password FROM users WHERE username='admin'"
    ).fetchone()
    if row and row["password"] == old_hash:
        conn.execute(
            "UPDATE users SET password=? WHERE username='admin'",
            (correct_hash,)
        )
        conn.commit()
        logger.info("MIG-001: Đã cập nhật hash mật khẩu admin.")

    # MIG-002: Recreate bảng users với role CHECK constraint đúng.
    # SQLite không hỗ trợ ALTER TABLE … ALTER COLUMN CHECK.
    # Giải pháp: rename → create new → copy → drop old (pattern chuẩn SQLite).
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if ddl_row:
        current_ddl = ddl_row["sql"] or ""
        old_check = "'admin','instructor','student'"
        new_check = "'admin','instructor','student','candidate','company','expert'"
        if old_check in current_ddl and new_check not in current_ddl:
            logger.info("MIG-002: Đang cập nhật role CHECK constraint...")
            conn.executescript("""
PRAGMA foreign_keys = OFF;

ALTER TABLE users RENAME TO _users_old;

CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    email       TEXT    NOT NULL UNIQUE,
    password    TEXT    NOT NULL,
    full_name   TEXT    NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'candidate'
                        CHECK(role IN ('admin','instructor','student','candidate','company','expert')),
    avatar_path TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

INSERT INTO users SELECT * FROM _users_old;

DROP TABLE _users_old;

PRAGMA foreign_keys = ON;
""")
            conn.commit()
            logger.info("MIG-002: role CHECK constraint đã cập nhật thành công.")
        elif new_check in current_ddl:
            logger.debug("MIG-002: role constraint đã đúng, bỏ qua.")


def drop_all_tables() -> None:
    """Xoá toàn bộ bảng – CHỈ dùng cho development/testing."""
    tables = [
        "assessments", "enrollments", "certificates",
        "courses", "skills", "users", "app_settings",
    ]
    conn = db.get_connection()
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table};")
    conn.commit()
    logger.warning("Đã xoá toàn bộ bảng CSDL.")
