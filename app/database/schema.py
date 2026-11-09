"""
Định nghĩa schema và khởi tạo CSDL SkillProof.
Chạy create_all_tables() một lần khi khởi động ứng dụng.

Chính sách tài khoản admin:
- Không seed admin với mật khẩu hardcode.
- Khi DB mới: đặt flag 'setup_done=0' để UI hiển thị màn hình thiết lập lần đầu.
- Khi DB cũ (đã có admin seed hardcode từ giai đoạn 01): 
  MIG-003 đánh dấu setup_done=1 và đặt lại hash theo PBKDF2.
"""

import logging
import sqlite3
from app.database.connection import db

logger = logging.getLogger(__name__)


# ── DDL ───────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    email       TEXT    NOT NULL UNIQUE,
    password    TEXT    NOT NULL,
    full_name   TEXT    NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'candidate'
                        CHECK(role IN ('admin','instructor','student',
                                       'candidate','company','expert')),
    avatar_path TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT,
    category    TEXT,
    level       TEXT    NOT NULL DEFAULT 'beginner'
                        CHECK(level IN ('beginner','intermediate',
                                        'advanced','expert')),
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

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

CREATE TABLE IF NOT EXISTS courses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    description   TEXT,
    skill_id      INTEGER REFERENCES skills(id) ON DELETE SET NULL,
    instructor_id INTEGER REFERENCES users(id)  ON DELETE SET NULL,
    duration_hours INTEGER,
    is_published  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS enrollments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
    course_id    INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    enrolled_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    completed_at TEXT,
    progress     REAL    NOT NULL DEFAULT 0.0
                         CHECK(progress BETWEEN 0 AND 100),
    UNIQUE(user_id, course_id)
);

CREATE TABLE IF NOT EXISTS assessments (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    skill_id  INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    score     REAL    NOT NULL CHECK(score BETWEEN 0 AND 100),
    max_score REAL    NOT NULL DEFAULT 100,
    taken_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    notes     TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_users_updated
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;
"""

# Seed chỉ chứa cài đặt ứng dụng — KHÔNG có admin với mật khẩu hardcode
SEED_SQL = """
INSERT OR IGNORE INTO app_settings (key, value) VALUES
    ('app_version',  '1.0.0'),
    ('setup_done',   '0'),
    ('theme',        'navy'),
    ('pw_scheme',    'pbkdf2_sha256_600k');
"""


# ── Khởi tạo ─────────────────────────────────────────────────────────────────

def create_all_tables() -> None:
    """Tạo tất cả bảng, trigger, seed settings và áp dụng migrations."""
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


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """
    Áp dụng migrations idempotent.
    Mỗi migration kiểm tra điều kiện trước khi chạy.
    """
    _mig_001_fix_admin_hash(conn)
    _mig_002_fix_role_constraint(conn)
    _mig_003_remove_hardcoded_admin(conn)


# ── MIG-001 ───────────────────────────────────────────────────────────────────

def _mig_001_fix_admin_hash(conn: sqlite3.Connection) -> None:
    """
    MIG-001: Cập nhật admin hash từ SHA-256 thuần → hash_password() SHA-256+salt.
    Legacy: hash cũ từ giai đoạn 00 trước khi có helpers.hash_password().
    Sau MIG-003, admin sẽ không còn seed hardcode nên migration này trở thành no-op.
    """
    old_hash = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
    ph1_hash = "67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56"

    row = conn.execute(
        "SELECT id, password FROM users WHERE username='admin'"
    ).fetchone()
    if row and row["password"] == old_hash:
        conn.execute("UPDATE users SET password=? WHERE id=?", (ph1_hash, row["id"]))
        conn.commit()
        logger.info("MIG-001: admin hash cập nhật từ SHA-256 thuần → legacy salted.")


# ── MIG-002 ───────────────────────────────────────────────────────────────────

def _mig_002_fix_role_constraint(conn: sqlite3.Connection) -> None:
    """
    MIG-002: Recreate bảng users với role CHECK constraint đầy đủ 6 roles.
    SQLite không hỗ trợ ALTER COLUMN CHECK.
    Thực hiện: backup → recreate → restore → verify → drop backup.

    Bảo vệ:
    - PRAGMA foreign_keys = OFF trong transaction riêng (không dùng executescript)
    - Kiểm tra row count trước/sau để xác nhận không mất dữ liệu
    - Rollback nếu row count khác nhau
    """
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if not ddl_row:
        return

    current_ddl = ddl_row["sql"] or ""
    old_check   = "'admin','instructor','student'"
    new_check   = "'admin','instructor','student','candidate','company','expert'"

    if new_check in current_ddl:
        logger.debug("MIG-002: role constraint đã đúng, bỏ qua.")
        return

    if old_check not in current_ddl:
        logger.debug("MIG-002: không nhận dạng được constraint cũ, bỏ qua.")
        return

    logger.info("MIG-002: Bắt đầu recreate users table...")
    count_before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    try:
        # FK OFF phải dùng conn.execute (không dùng executescript)
        conn.execute("PRAGMA foreign_keys = OFF")

        conn.execute("ALTER TABLE users RENAME TO _users_mig002_backup")

        conn.execute("""
            CREATE TABLE users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE,
                email       TEXT    NOT NULL UNIQUE,
                password    TEXT    NOT NULL,
                full_name   TEXT    NOT NULL,
                role        TEXT    NOT NULL DEFAULT 'candidate'
                            CHECK(role IN ('admin','instructor','student',
                                           'candidate','company','expert')),
                avatar_path TEXT,
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        conn.execute(
            "INSERT INTO users SELECT * FROM _users_mig002_backup"
        )
        conn.commit()

        count_after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        if count_after != count_before:
            # Rollback: khôi phục bảng gốc
            conn.execute("DROP TABLE IF EXISTS users")
            conn.execute(
                "ALTER TABLE _users_mig002_backup RENAME TO users"
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
            logger.error(
                "MIG-002 ROLLBACK: row count mismatch (%d → %d)",
                count_before, count_after,
            )
            return

        conn.execute("DROP TABLE _users_mig002_backup")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")

        # Recreate trigger (có thể bị mất khi drop backup)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_users_updated
            AFTER UPDATE ON users
            BEGIN
                UPDATE users SET updated_at = datetime('now','localtime')
                WHERE id = NEW.id;
            END
        """)
        conn.commit()

        logger.info(
            "MIG-002: role CHECK constraint cập nhật OK (%d rows bảo toàn).",
            count_after,
        )

    except Exception as exc:
        conn.execute("PRAGMA foreign_keys = ON")
        logger.exception("MIG-002 FAILED: %s", exc)
        raise


# ── MIG-003 ───────────────────────────────────────────────────────────────────

_LEGACY_SALTED_HASH = "67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56"


def _mig_003_remove_hardcoded_admin(conn: sqlite3.Connection) -> None:
    """
    MIG-003: Xử lý tài khoản admin seed hardcode.

    Nếu admin vẫn còn hash cũ (legacy SHA-256+salt):
    - Đánh dấu tài khoản is_active=0 để buộc reset mật khẩu
    - Ghi flag 'setup_done=reset_required' vào app_settings
    - Log rõ ràng để admin biết cần vào màn hình setup

    Nếu admin đã có PBKDF2 hash (đã được rehash qua login hoặc setup):
    - Không làm gì thêm

    Nếu không có admin nào (DB mới hoàn toàn):
    - Giữ nguyên setup_done='0' để first-run setup flow xử lý

    QUAN TRỌNG: Migration này KHÔNG xóa tài khoản admin.
    Chỉ vô hiệu hóa tạm thời cho đến khi mật khẩu được đặt lại qua UI.
    """
    row = conn.execute(
        "SELECT id, password FROM users WHERE username='admin'"
    ).fetchone()

    if row is None:
        # DB mới — không có admin seed, setup_done='0' đã được seed
        logger.debug("MIG-003: Không có admin seed, first-run setup sẽ xử lý.")
        return

    stored = row["password"]

    # Admin đã có PBKDF2 hash → không cần làm gì
    if stored.startswith("pbkdf2:"):
        logger.debug("MIG-003: Admin đã dùng PBKDF2, bỏ qua.")
        return

    # Admin vẫn dùng legacy hash (SHA-256+salt hoặc SHA-256 thuần)
    # → vô hiệu hóa tạm thời + yêu cầu reset
    if stored == _LEGACY_SALTED_HASH or (len(stored) == 64 and not ":" in stored):
        conn.execute(
            "UPDATE users SET is_active=0 WHERE id=?", (row["id"],)
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value) VALUES(?,?)",
            ("setup_done", "reset_required"),
        )
        conn.commit()
        logger.warning(
            "MIG-003: Admin (id=%d) dùng legacy hash — đã vô hiệu hóa tạm thời. "
            "Cần đặt lại mật khẩu qua màn hình First-Run Setup.",
            row["id"],
        )


# ── Tiện ích ──────────────────────────────────────────────────────────────────

def drop_all_tables() -> None:
    """Xoá toàn bộ bảng — CHỈ dùng cho testing."""
    tables = [
        "assessments", "enrollments", "certificates",
        "courses", "skills", "users", "app_settings",
    ]
    conn = db.get_connection()
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table};")
    conn.commit()
    logger.warning("drop_all_tables(): đã xoá toàn bộ bảng CSDL.")


def is_first_run(conn: sqlite3.Connection | None = None) -> bool:
    """
    Trả về True nếu chưa có admin hợp lệ (setup_done != '1').
    Dùng trong MainWindow để quyết định hiển thị màn hình thiết lập lần đầu.
    """
    _conn = conn or db.get_connection()
    row = _conn.execute(
        "SELECT value FROM app_settings WHERE key='setup_done'"
    ).fetchone()
    return row is None or row["value"] != "1"


def mark_setup_done(conn: sqlite3.Connection | None = None) -> None:
    """Đánh dấu thiết lập lần đầu hoàn tất."""
    _conn = conn or db.get_connection()
    _conn.execute(
        "INSERT OR REPLACE INTO app_settings(key,value) VALUES('setup_done','1')"
    )
    _conn.commit()
