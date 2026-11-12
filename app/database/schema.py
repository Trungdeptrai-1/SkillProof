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
    _mig_004_create_business_tables(conn)
    _mig_005_extend_contracts_and_softdelete(conn)


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
    # Normalize whitespace để so sánh constraint string an toàn
    import re as _re
    _ddl_norm = _re.sub(r'\s+', '', current_ddl)   # bỏ toàn bộ whitespace
    old_check  = "'admin','instructor','student'"
    new_check  = "'admin','instructor','student','candidate','company','expert'"
    # So sánh trên DDL đã normalize (không có whitespace)
    if new_check in _ddl_norm:
        logger.debug("MIG-002: role constraint đã đúng, bỏ qua.")
        return

    if old_check not in _ddl_norm:
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


# ── MIG-004: Bảng nghiệp vụ Giai đoạn 03 ──────────────────────────────────────
# 14 bảng mới, không sửa bảng cũ. Thứ tự tạo theo FK dependency.

BUSINESS_SCHEMA_SQL = """
-- A1. company_profiles (FK→users only, safe first)
CREATE TABLE IF NOT EXISTS company_profiles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    company_name  TEXT    NOT NULL,
    industry      TEXT,
    website       TEXT,
    description   TEXT,
    logo_path     TEXT,
    tax_code      TEXT,
    address       TEXT,
    is_verified   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_company_profiles_user ON company_profiles(user_id);

-- A2. expert_profiles
CREATE TABLE IF NOT EXISTS expert_profiles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    title          TEXT    NOT NULL,
    bio            TEXT,
    specialization TEXT,
    hourly_rate    REAL,
    availability   TEXT    NOT NULL DEFAULT 'available'
                   CHECK(availability IN ('available','busy','unavailable')),
    is_verified    INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_expert_profiles_user ON expert_profiles(user_id);

-- A3. candidate_profiles
CREATE TABLE IF NOT EXISTS candidate_profiles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    headline         TEXT,
    bio              TEXT,
    resume_path      TEXT,
    portfolio_url    TEXT,
    years_experience INTEGER,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_candidate_profiles_user ON candidate_profiles(user_id);

-- C1. question_bank (FK→users, skills)
CREATE TABLE IF NOT EXISTS question_bank (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    expert_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id         INTEGER REFERENCES skills(id) ON DELETE SET NULL,
    question_type    TEXT    NOT NULL
                     CHECK(question_type IN ('multiple_choice','coding','essay')),
    title            TEXT    NOT NULL,
    content          TEXT    NOT NULL,
    difficulty       TEXT    NOT NULL DEFAULT 'medium'
                     CHECK(difficulty IN ('easy','medium','hard')),
    points           REAL    NOT NULL DEFAULT 10,
    test_cases       TEXT,
    reference_answer TEXT,
    is_published     INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_qb_expert    ON question_bank(expert_id);
CREATE INDEX IF NOT EXISTS idx_qb_skill     ON question_bank(skill_id);
CREATE INDEX IF NOT EXISTS idx_qb_type      ON question_bank(question_type);
CREATE INDEX IF NOT EXISTS idx_qb_published ON question_bank(is_published);

-- C2. question_options (FK→question_bank)
CREATE TABLE IF NOT EXISTS question_options (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES question_bank(id) ON DELETE CASCADE,
    content     TEXT    NOT NULL,
    is_correct  INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_qo_question ON question_options(question_id);

-- D1. exam_papers (FK→skills, users)
CREATE TABLE IF NOT EXISTS exam_papers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    description   TEXT,
    skill_id      INTEGER REFERENCES skills(id) ON DELETE SET NULL,
    created_by     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_points  REAL    NOT NULL DEFAULT 100,
    duration_min  INTEGER NOT NULL DEFAULT 60,
    is_published  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_ep_skill      ON exam_papers(skill_id);
CREATE INDEX IF NOT EXISTS idx_ep_created_by ON exam_papers(created_by);

-- D2. exam_paper_questions (N-N: exam_papers ↔ question_bank)
CREATE TABLE IF NOT EXISTS exam_paper_questions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_paper_id INTEGER NOT NULL REFERENCES exam_papers(id) ON DELETE CASCADE,
    question_id   INTEGER NOT NULL REFERENCES question_bank(id) ON DELETE RESTRICT,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    points        REAL,
    UNIQUE(exam_paper_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_epq_paper    ON exam_paper_questions(exam_paper_id);
CREATE INDEX IF NOT EXISTS idx_epq_question ON exam_paper_questions(question_id);

-- D3. exam_sessions (FK→exam_papers, users)
CREATE TABLE IF NOT EXISTS exam_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_paper_id INTEGER NOT NULL REFERENCES exam_papers(id) ON DELETE RESTRICT,
    candidate_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status        TEXT    NOT NULL DEFAULT 'scheduled'
                  CHECK(status IN ('scheduled','in_progress','completed','cancelled')),
    scheduled_at  TEXT,
    started_at    TEXT,
    completed_at  TEXT,
    total_score   REAL,
    max_score     REAL    NOT NULL DEFAULT 100,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_es_paper     ON exam_sessions(exam_paper_id);
CREATE INDEX IF NOT EXISTS idx_es_candidate ON exam_sessions(candidate_id);
CREATE INDEX IF NOT EXISTS idx_es_company   ON exam_sessions(company_id);
CREATE INDEX IF NOT EXISTS idx_es_status    ON exam_sessions(status);

-- D4. exam_answers (FK→exam_sessions, question_bank, users)
CREATE TABLE IF NOT EXISTS exam_answers (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_session_id    INTEGER NOT NULL REFERENCES exam_sessions(id) ON DELETE CASCADE,
    question_id        INTEGER NOT NULL REFERENCES question_bank(id) ON DELETE RESTRICT,
    answer_text        TEXT,
    answer_code        TEXT,
    selected_option_id INTEGER,
    score              REAL,
    max_score          REAL    NOT NULL DEFAULT 10,
    feedback           TEXT,
    graded_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    graded_at          TEXT,
    is_graded          INTEGER NOT NULL DEFAULT 0,
    UNIQUE(exam_session_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_ea_session   ON exam_answers(exam_session_id);
CREATE INDEX IF NOT EXISTS idx_ea_question  ON exam_answers(question_id);
CREATE INDEX IF NOT EXISTS idx_ea_graded_by ON exam_answers(graded_by);
CREATE INDEX IF NOT EXISTS idx_ea_is_graded ON exam_answers(is_graded);

-- E1. exam_grade_revisions (FK→exam_answers, users)
CREATE TABLE IF NOT EXISTS exam_grade_revisions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_answer_id INTEGER NOT NULL REFERENCES exam_answers(id) ON DELETE CASCADE,
    graded_by      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    old_score      REAL,
    new_score      REAL    NOT NULL,
    old_feedback   TEXT,
    new_feedback   TEXT,
    reason         TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_gr_answer ON exam_grade_revisions(exam_answer_id);
CREATE INDEX IF NOT EXISTS idx_gr_grader ON exam_grade_revisions(graded_by);

-- F1. interviews (FK→users)
CREATE TABLE IF NOT EXISTS interviews (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    title          TEXT    NOT NULL,
    description    TEXT,
    status         TEXT    NOT NULL DEFAULT 'scheduled'
                  CHECK(status IN ('scheduled','in_progress','completed','cancelled','no_show')),
    scheduled_at   TEXT    NOT NULL,
    duration_min   INTEGER NOT NULL DEFAULT 60,
    meeting_url    TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_iv_candidate ON interviews(candidate_id);
CREATE INDEX IF NOT EXISTS idx_iv_company   ON interviews(company_id);
CREATE INDEX IF NOT EXISTS idx_iv_status    ON interviews(status);

-- F2. interview_participants (FK→interviews, users)
CREATE TABLE IF NOT EXISTS interview_participants (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    expert_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role         TEXT    NOT NULL DEFAULT 'interviewer'
                 CHECK(role IN ('interviewer','observer','moderator')),
    joined_at    TEXT,
    UNIQUE(interview_id, expert_id)
);
CREATE INDEX IF NOT EXISTS idx_ip_interview ON interview_participants(interview_id);
CREATE INDEX IF NOT EXISTS idx_ip_expert    ON interview_participants(expert_id);

-- F3. interview_evaluations (FK→interviews, users)
CREATE TABLE IF NOT EXISTS interview_evaluations (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id         INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    expert_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    technical_score      INTEGER CHECK(technical_score BETWEEN 1 AND 5),
    communication_score  INTEGER CHECK(communication_score BETWEEN 1 AND 5),
    problem_solving_score INTEGER CHECK(problem_solving_score BETWEEN 1 AND 5),
    overall_rating       INTEGER CHECK(overall_rating BETWEEN 1 AND 5),
    feedback             TEXT,
    recommendation       TEXT CHECK(recommendation IN ('strong_hire','hire','no_hire','strong_no_hire')),
    created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(interview_id, expert_id)
);
CREATE INDEX IF NOT EXISTS idx_ie_interview ON interview_evaluations(interview_id);
CREATE INDEX IF NOT EXISTS idx_ie_expert    ON interview_evaluations(expert_id);

-- B1. company_expert_contracts (FK→users, N-N with history)
CREATE TABLE IF NOT EXISTS company_expert_contracts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expert_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contract_code TEXT    NOT NULL UNIQUE,
    status        TEXT    NOT NULL DEFAULT 'active'
                  CHECK(status IN ('active','completed','terminated','cancelled')),
    start_date    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    end_date      TEXT,
    notes         TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_contracts_company ON company_expert_contracts(company_id);
CREATE INDEX IF NOT EXISTS idx_contracts_expert  ON company_expert_contracts(expert_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status   ON company_expert_contracts(status);

-- B2. tasks (FK→users, contracts, exam_sessions, interviews — LAST)
CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expert_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contract_id     INTEGER REFERENCES company_expert_contracts(id) ON DELETE SET NULL,
    title           TEXT    NOT NULL,
    description     TEXT,
    task_type       TEXT    NOT NULL
                    CHECK(task_type IN ('grading','interview','question_creation','review')),
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','in_progress','completed','cancelled')),
    priority        TEXT    NOT NULL DEFAULT 'normal'
                    CHECK(priority IN ('low','normal','high','urgent')),
    assigned_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    due_at          TEXT,
    completed_at    TEXT,
    exam_session_id INTEGER REFERENCES exam_sessions(id) ON DELETE SET NULL,
    interview_id    INTEGER REFERENCES interviews(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_company ON tasks(company_id);
CREATE INDEX IF NOT EXISTS idx_tasks_expert  ON tasks(expert_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status  ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_type    ON tasks(task_type);
"""

BUSINESS_TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_company_profiles_updated
AFTER UPDATE ON company_profiles
BEGIN
    UPDATE company_profiles SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_expert_profiles_updated
AFTER UPDATE ON expert_profiles
BEGIN
    UPDATE expert_profiles SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_candidate_profiles_updated
AFTER UPDATE ON candidate_profiles
BEGIN
    UPDATE candidate_profiles SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_question_bank_updated
AFTER UPDATE ON question_bank
BEGIN
    UPDATE question_bank SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_exam_papers_updated
AFTER UPDATE ON exam_papers
BEGIN
    UPDATE exam_papers SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;
"""

# Danh sách 14 bảng mới (theo thứ tự DROP ngược lại — con trước cha)
BUSINESS_TABLES = [
    "tasks",
    "company_expert_contracts",
    "interview_evaluations",
    "interview_participants",
    "interviews",
    "exam_grade_revisions",
    "exam_answers",
    "exam_sessions",
    "exam_paper_questions",
    "exam_papers",
    "question_options",
    "question_bank",
    "candidate_profiles",
    "expert_profiles",
    "company_profiles",
]


def _mig_004_create_business_tables(conn: sqlite3.Connection) -> None:
    """
    MIG-004: Tạo 14 bảng nghiệp vụ + 22 index + 5 trigger.

    An toàn:
    - CREATE TABLE IF NOT EXISTS → không ghi đè bảng đã có.
    - Không sửa bảng cũ (7 bảng Giai đoạn 00-01).
    - Kiểm tra bảng cũ trước/sau → không mất dữ liệu.

    Rollback:
    - Nếu lỗi → DROP các bảng mới đã tạo → bảng cũ không bị ảnh hưởng.
    """
    # Kiểm tra đã chạy chưa (idempotent)
    check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='company_profiles'"
    ).fetchone()
    if check:
        logger.debug("MIG-004: business tables already exist, skip.")
        return

    # Lưu danh sách bảng cũ trước migration
    old_tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    created_tables = []

    try:
        conn.executescript(BUSINESS_SCHEMA_SQL)
        conn.executescript(BUSINESS_TRIGGERS_SQL)
        conn.commit()

        # Lấy danh sách bảng hiện tại
        current_tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        # Verify: tất cả bảng cũ vẫn còn
        missing_old = old_tables - current_tables
        if missing_old:
            raise RuntimeError(f"MIG-004: Bảng cũ bị mất: {missing_old}")

        # Lấy danh sách bảng mới đã tạo
        created_tables = list(current_tables - old_tables)

        logger.info(
            "MIG-004: %d business tables + indexes + triggers created.",
            len([t for t in BUSINESS_TABLES if t in current_tables])
        )

    except Exception as exc:
        # Rollback: xóa bảng mới đã tạo (theo thứ tự ngược FK)
        for table in created_tables:
            try:
                conn.execute(f"DROP TABLE IF EXISTS [{table}]")
            except Exception:
                pass
        conn.commit()
        logger.exception("MIG-004 FAILED, rolled back %d tables: %s",
                         len(created_tables), exc)
        raise


def _mig_005_extend_contracts_and_softdelete(conn: sqlite3.Connection) -> None:
    """
    MIG-005: Mở rộng company_expert_contracts và users cho Giai đoạn 04.4.

    Thay đổi:
    A. users: thêm cột is_deleted (soft-delete, không CASCADE xóa lịch sử).
    B. company_expert_contracts: recreate với CHECK mở rộng thêm
       'pending_expert' và 'rejected', cộng 2 cột lý do.

    Bảo toàn:
    - Mọi hàng contracts hiện có (status cũ) vẫn hợp lệ.
    - Dữ liệu users không mất.
    - Idempotent: chạy nhiều lần không lỗi.
    """
    # ── Phần A: Thêm is_deleted vào users ────────────────────────────────────
    # Kiểm tra cột đã tồn tại chưa
    user_cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "is_deleted" not in user_cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
        logger.info("MIG-005A: Thêm cột is_deleted vào users.")
    else:
        logger.debug("MIG-005A: is_deleted đã có, bỏ qua.")

    # Thêm index nếu chưa có
    idx_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_users_is_deleted'"
    ).fetchone()
    if not idx_exists:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_is_deleted ON users(is_deleted)"
        )
        conn.commit()

    # ── Phần B: Recreate company_expert_contracts với CHECK mở rộng ───────────
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='company_expert_contracts'"
    ).fetchone()
    if not ddl_row:
        logger.debug("MIG-005B: company_expert_contracts chưa tồn tại, bỏ qua.")
        return

    current_ddl = ddl_row["sql"] or ""
    # Nếu đã có pending_expert trong DDL → đã migrate
    if "pending_expert" in current_ddl:
        logger.debug("MIG-005B: contracts đã có pending_expert, bỏ qua.")
        return

    logger.info("MIG-005B: Bắt đầu recreate company_expert_contracts...")
    count_before = conn.execute(
        "SELECT COUNT(*) FROM company_expert_contracts"
    ).fetchone()[0]

    try:
        conn.execute("PRAGMA foreign_keys = OFF")

        # Kiểm tra backup cũ từ migration thất bại trước (nếu có)
        backup_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name='_contracts_mig005_backup'"
        ).fetchone()
        if backup_exists:
            conn.execute("DROP TABLE _contracts_mig005_backup")
            conn.commit()

        conn.execute(
            "ALTER TABLE company_expert_contracts RENAME TO _contracts_mig005_backup"
        )

        conn.execute("""
            CREATE TABLE company_expert_contracts (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expert_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                contract_code     TEXT    NOT NULL UNIQUE,
                status            TEXT    NOT NULL DEFAULT 'pending_expert'
                                  CHECK(status IN (
                                      'pending_expert',
                                      'rejected',
                                      'active',
                                      'completed',
                                      'terminated',
                                      'cancelled'
                                  )),
                start_date        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                end_date          TEXT,
                notes             TEXT,
                rejection_reason  TEXT,
                terminated_reason TEXT,
                created_at        TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        # Copy dữ liệu cũ; 2 cột mới có giá trị NULL (không vi phạm)
        conn.execute("""
            INSERT INTO company_expert_contracts
                (id, company_id, expert_id, contract_code, status,
                 start_date, end_date, notes, created_at)
            SELECT
                id, company_id, expert_id, contract_code, status,
                start_date, end_date, notes, created_at
            FROM _contracts_mig005_backup
        """)
        conn.commit()

        count_after = conn.execute(
            "SELECT COUNT(*) FROM company_expert_contracts"
        ).fetchone()[0]

        if count_after != count_before:
            # Rollback
            conn.execute("DROP TABLE IF EXISTS company_expert_contracts")
            conn.execute(
                "ALTER TABLE _contracts_mig005_backup RENAME TO company_expert_contracts"
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
            logger.error(
                "MIG-005B ROLLBACK: row count mismatch (%d → %d)",
                count_before, count_after,
            )
            return

        conn.execute("DROP TABLE _contracts_mig005_backup")

        # Recreate tasks để fix FK reference từ _contracts_mig005_backup → company_expert_contracts
        # SQLite quirk: sau RENAME+DROP+CREATE, FK của bảng khác vẫn trỏ tên cũ
        tasks_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        if tasks_exists:
            conn.execute("ALTER TABLE tasks RENAME TO _tasks_mig005_backup")
            conn.execute("""
                CREATE TABLE tasks (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expert_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    contract_id     INTEGER REFERENCES company_expert_contracts(id) ON DELETE SET NULL,
                    title           TEXT    NOT NULL,
                    description     TEXT,
                    task_type       TEXT    NOT NULL
                                    CHECK(task_type IN ('grading','interview','question_creation','review')),
                    status          TEXT    NOT NULL DEFAULT 'pending'
                                    CHECK(status IN ('pending','in_progress','completed','cancelled')),
                    priority        TEXT    NOT NULL DEFAULT 'normal'
                                    CHECK(priority IN ('low','normal','high','urgent')),
                    assigned_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                    due_at          TEXT,
                    completed_at    TEXT,
                    exam_session_id INTEGER REFERENCES exam_sessions(id) ON DELETE SET NULL,
                    interview_id    INTEGER REFERENCES interviews(id) ON DELETE SET NULL
                )
            """)
            conn.execute("INSERT INTO tasks SELECT * FROM _tasks_mig005_backup")
            conn.execute("DROP TABLE _tasks_mig005_backup")
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_tasks_company ON tasks(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_expert  ON tasks(expert_id)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_status  ON tasks(status)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_type    ON tasks(task_type)",
            ]:
                conn.execute(idx_sql)
        conn.commit()

        # Recreate indexes for contracts
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contracts_company "
            "ON company_expert_contracts(company_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contracts_expert "
            "ON company_expert_contracts(expert_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contracts_status "
            "ON company_expert_contracts(status)"
        )
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")

        logger.info(
            "MIG-005B: company_expert_contracts recreated OK (%d rows).",
            count_after,
        )

    except Exception as exc:
        conn.execute("PRAGMA foreign_keys = ON")
        logger.exception("MIG-005B FAILED: %s", exc)
        raise


# ── Tiện ích ──────────────────────────────────────────────────────────────────

def drop_all_tables() -> None:
    """Xoá toàn bộ bảng — CHỈ dùng cho testing."""
    # Bảng mới (Giai đoạn 03) — drop theo thứ tự ngược FK
    business_tables = [
        "tasks", "company_expert_contracts",
        "interview_evaluations", "interview_participants", "interviews",
        "exam_grade_revisions", "exam_answers", "exam_sessions",
        "exam_paper_questions", "exam_papers",
        "question_options", "question_bank",
        "candidate_profiles", "expert_profiles", "company_profiles",
    ]
    # Bảng cũ (Giai đoạn 00-01)
    old_tables = [
        "assessments", "enrollments", "certificates",
        "courses", "skills", "users", "app_settings",
    ]
    conn = db.get_connection()
    for table in business_tables + old_tables:
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
