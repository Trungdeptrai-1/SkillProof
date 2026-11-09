# -*- coding: utf-8 -*-
"""
Tests: MIG-004 — Tạo 14 bảng nghiệp vụ Giai đoạn 03.
Kiểm tra: tạo bảng, idempotent, dữ liệu cũ không mất, FK hoạt động,
CHECK constraints, UNIQUE constraints, index, trigger, rollback.
Dùng fresh_db + legacy_db fixtures — không chạm DB thật.
"""

import sqlite3
import pytest

from app.database.schema import (
    _mig_004_create_business_tables,
    BUSINESS_TABLES,
    create_all_tables,
)


# Danh sách 14 bảng mới kỳ vọng
EXPECTED_NEW_TABLES = [
    "company_profiles",
    "expert_profiles",
    "candidate_profiles",
    "question_bank",
    "question_options",
    "exam_papers",
    "exam_paper_questions",
    "exam_sessions",
    "exam_answers",
    "exam_grade_revisions",
    "interviews",
    "interview_participants",
    "interview_evaluations",
    "company_expert_contracts",
    "tasks",
]

# 7 bảng cũ không được mất
OLD_TABLES = [
    "users", "skills", "certificates", "courses",
    "enrollments", "assessments", "app_settings",
]


# ══════════════════════════════════════════════════════════════════════════════
# Tạo bảng — 14 bảng xuất hiện
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004CreatesTables:
    def test_all_14_tables_created(self, fresh_db):
        """MIG-004 tạo đủ 14 bảng."""
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)

        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for table in EXPECTED_NEW_TABLES:
            assert table in tables, f"Thiếu bảng: {table}"

    def test_table_count_after_migration(self, fresh_db):
        """Sau MIG-004 có 22 bảng (7 cũ + 15 mới)."""
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)

        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        assert len(tables) == 22, f"Expected 22 tables, got {len(tables)}: {tables}"

    @pytest.mark.parametrize("table_name", EXPECTED_NEW_TABLES)
    def test_each_table_exists(self, fresh_db, table_name):
        """Kiểm tra từng bảng tồn tại."""
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        assert row is not None, f"Bảng {table_name} không tồn tại"


# ══════════════════════════════════════════════════════════════════════════════
# Idempotent — chạy nhiều lần không lỗi
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004Idempotent:
    def test_run_twice_no_error(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        _mig_004_create_business_tables(conn)  # Lần 2 — no-op

        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "company_profiles" in tables

    def test_run_three_times(self, fresh_db):
        conn = fresh_db.get_connection()
        for _ in range(3):
            _mig_004_create_business_tables(conn)
        # Không raise, đủ bảng
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        assert count == 22

    def test_create_all_tables_includes_mig004(self, fresh_db):
        """create_all_tables() phải chạy MIG-004 tự động."""
        # fresh_db đã chạy create_all_tables trong fixture
        conn = fresh_db.get_connection()
        # MIG-004 chạy trong _apply_migrations
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE name='tasks'"
        ).fetchone()
        assert row is not None, "tasks table phải được tạo bởi MIG-004"


# ══════════════════════════════════════════════════════════════════════════════
# Dữ liệu cũ không mất
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004PreservesOldData:
    def test_old_tables_intact(self, fresh_db):
        """7 bảng cũ vẫn tồn tại sau MIG-004."""
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)

        for table in OLD_TABLES:
            row = conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            ).fetchone()
            assert row is not None, f"Bảng cũ {table} bị mất sau MIG-004"

    def test_old_data_preserved(self, legacy_db):
        """DB cũ có dữ liệu → MIG-004 không xóa."""
        conn = legacy_db.get_connection()
        # legacy DB có admin user
        count_before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count_before > 0

        _mig_004_create_business_tables(conn)

        count_after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count_after == count_before, "MIG-004 làm mất dữ liệu users"

    def test_admin_user_intact(self, legacy_db):
        """Admin user trong DB cũ vẫn còn sau MIG-004."""
        conn = legacy_db.get_connection()
        _mig_004_create_business_tables(conn)

        admin = conn.execute(
            "SELECT * FROM users WHERE username='admin'"
        ).fetchone()
        assert admin is not None
        assert admin["email"] == "admin@skillproof.local"

    def test_app_settings_intact(self, legacy_db):
        """app_settings không bị thay đổi."""
        conn = legacy_db.get_connection()
        settings_before = conn.execute(
            "SELECT key, value FROM app_settings"
        ).fetchall()

        _mig_004_create_business_tables(conn)

        settings_after = conn.execute(
            "SELECT key, value FROM app_settings"
        ).fetchall()
        assert len(settings_before) == len(settings_after)


# ══════════════════════════════════════════════════════════════════════════════
# Foreign Keys
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004ForeignKeys:
    def test_company_profiles_fk(self, fresh_db):
        """company_profiles.user_id → users.id ON DELETE CASCADE."""
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)

        # Tạo user company
        from app.utils.helpers import hash_password
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)" ,
            ("comp1", "comp1@sp.local", hash_password("P@ss1"), "Company 1", "company")
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE username='comp1'"
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO company_profiles(user_id, company_name) VALUES (?,?)",
            (user_id, "Test Company")
        )
        conn.commit()

        # Delete user → cascade delete profile
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()

        profile = conn.execute(
            "SELECT * FROM company_profiles WHERE user_id=?", (user_id,)
        ).fetchone()
        assert profile is None, "CASCADE DELETE không hoạt động"

    def test_question_bank_fk(self, fresh_db):
        """question_bank.expert_id → users.id, question_bank.skill_id → skills.id."""
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)

        from app.utils.helpers import hash_password
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("exp1", "exp1@sp.local", hash_password("P@ss1"), "Expert 1", "expert")
        )
        expert_id = conn.execute(
            "SELECT id FROM users WHERE username='exp1'"
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO skills(name) VALUES('Python')"
        )
        skill_id = conn.execute(
            "SELECT id FROM skills WHERE name='Python'"
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO question_bank(expert_id, skill_id, question_type, title, content)"
            " VALUES(?,?,?,'Test Q','Content')",
            (expert_id, skill_id, "coding")
        )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM question_bank").fetchone()[0] == 1

    def test_tasks_fk_to_exam_sessions(self, fresh_db):
        """tasks.exam_session_id → exam_sessions.id."""
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)

        from app.utils.helpers import hash_password
        # Tạo company + expert
        for uname, role in [("comp_t", "company"), ("exp_t", "expert"), ("cand_t", "candidate")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@sp.local", hash_password("P@ss1"), uname, role)
            )
        conn.commit()
        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_t'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_t'").fetchone()[0]
        cand_id = conn.execute("SELECT id FROM users WHERE username='cand_t'").fetchone()[0]

        # Tạo exam_paper → exam_session
        conn.execute(
            "INSERT INTO exam_papers(title, created_by) VALUES('Paper 1', ?)",
            (exp_id,)
        )
        paper_id = conn.execute("SELECT id FROM exam_papers").fetchone()[0]

        conn.execute(
            "INSERT INTO exam_sessions(exam_paper_id, candidate_id, company_id)"
            " VALUES(?,?,?)",
            (paper_id, cand_id, comp_id)
        )
        session_id = conn.execute("SELECT id FROM exam_sessions").fetchone()[0]

        # Tạo task trỏ đến exam_session
        conn.execute(
            "INSERT INTO tasks(company_id, expert_id, title, task_type, exam_session_id)"
            " VALUES(?,?,?,?,?)",
            (comp_id, exp_id, "Grade exam", "grading", session_id)
        )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1

    def test_interview_participants_unique(self, fresh_db):
        """interview_participants: UNIQUE(interview_id, expert_id)."""
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)

        from app.utils.helpers import hash_password
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("cand_iv", "cand_iv@sp.local", hash_password("P@ss1"), "Cand", "candidate")
        )
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("exp_iv", "exp_iv@sp.local", hash_password("P@ss1"), "Exp", "expert")
        )
        cand_id = conn.execute("SELECT id FROM users WHERE username='cand_iv'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_iv'").fetchone()[0]

        conn.execute(
            "INSERT INTO interviews(candidate_id, title, scheduled_at) VALUES(?, 'IV1', '2026-01-01')",
            (cand_id,)
        )
        iv_id = conn.execute("SELECT id FROM interviews").fetchone()[0]

        conn.execute(
            "INSERT INTO interview_participants(interview_id, expert_id) VALUES(?,?)",
            (iv_id, exp_id)
        )
        conn.commit()

        # Duplicate phải fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO interview_participants(interview_id, expert_id) VALUES(?,?)",
                (iv_id, exp_id)
            )


# ══════════════════════════════════════════════════════════════════════════════
# CHECK constraints
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004CheckConstraints:
    def test_expert_availability_check(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        from app.utils.helpers import hash_password

        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("exp_chk", "exp_chk@sp.local", hash_password("P@ss1"), "Exp", "expert")
        )
        uid = conn.execute("SELECT id FROM users WHERE username='exp_chk'").fetchone()[0]

        # Valid
        conn.execute(
            "INSERT INTO expert_profiles(user_id, title, availability) VALUES(?,?,?)",
            (uid, "Senior", "available")
        )
        conn.commit()

        # Invalid
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO expert_profiles(user_id, title, availability) VALUES(?,?,?)",
                (uid, "Senior2", "invalid_status")
            )

    def test_question_type_check(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        from app.utils.helpers import hash_password

        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("exp_q", "exp_q@sp.local", hash_password("P@ss1"), "Exp", "expert")
        )
        uid = conn.execute("SELECT id FROM users WHERE username='exp_q'").fetchone()[0]

        # Valid types
        for qtype in ["multiple_choice", "coding", "essay"]:
            conn.execute(
                "INSERT INTO question_bank(expert_id, question_type, title, content)"
                " VALUES(?,?,'T','C')", (uid, qtype)
            )
        conn.commit()

        # Invalid
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO question_bank(expert_id, question_type, title, content)"
                " VALUES(?,?,'T','C')", (uid, "invalid_type")
            )

    def test_interview_status_check(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        from app.utils.helpers import hash_password

        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("cand_s", "cand_s@sp.local", hash_password("P@ss1"), "Cand", "candidate")
        )
        uid = conn.execute("SELECT id FROM users WHERE username='cand_s'").fetchone()[0]

        conn.execute(
            "INSERT INTO interviews(candidate_id, title, scheduled_at, status)"
            " VALUES(?, 'IV', '2026-01-01', 'scheduled')", (uid,)
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO interviews(candidate_id, title, scheduled_at, status)"
                " VALUES(?, 'IV2', '2026-01-01', 'invalid')", (uid,)
            )

    def test_contract_status_check(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        from app.utils.helpers import hash_password

        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("comp_c", "comp_c@sp.local", hash_password("P@ss1"), "Comp", "company")
        )
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("exp_c", "exp_c@sp.local", hash_password("P@ss1"), "Exp", "expert")
        )
        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_c'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_c'").fetchone()[0]

        conn.execute(
            "INSERT INTO company_expert_contracts(company_id, expert_id, contract_code, status)"
            " VALUES(?,?,?,'active')", (comp_id, exp_id, "CTR-001")
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO company_expert_contracts(company_id, expert_id, contract_code, status)"
                " VALUES(?,?,?,'invalid')", (comp_id, exp_id, "CTR-002")
            )

    def test_contract_code_unique(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        from app.utils.helpers import hash_password

        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("comp_u", "comp_u@sp.local", hash_password("P@ss1"), "Comp", "company")
        )
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("exp_u", "exp_u@sp.local", hash_password("P@ss1"), "Exp", "expert")
        )
        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_u'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_u'").fetchone()[0]

        conn.execute(
            "INSERT INTO company_expert_contracts(company_id, expert_id, contract_code)"
            " VALUES(?,?,?)", (comp_id, exp_id, "UNIQUE-001")
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO company_expert_contracts(company_id, expert_id, contract_code)"
                " VALUES(?,?,?)", (comp_id, exp_id, "UNIQUE-001")
            )

    def test_company_expert_multiple_contracts(self, fresh_db):
        """Cùng company+expert có thể có nhiều hợp đồng (không UNIQUE)."""
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        from app.utils.helpers import hash_password

        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("comp_m", "comp_m@sp.local", hash_password("P@ss1"), "Comp", "company")
        )
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("exp_m", "exp_m@sp.local", hash_password("P@ss1"), "Exp", "expert")
        )
        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_m'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_m'").fetchone()[0]

        # Hợp đồng 1
        conn.execute(
            "INSERT INTO company_expert_contracts(company_id, expert_id, contract_code, status)"
            " VALUES(?,?,?,'completed')", (comp_id, exp_id, "CTR-A")
        )
        # Hợp đồng 2 (cùng company+expert, contract_code khác)
        conn.execute(
            "INSERT INTO company_expert_contracts(company_id, expert_id, contract_code, status)"
            " VALUES(?,?,?,'active')", (comp_id, exp_id, "CTR-B")
        )
        conn.commit()

        count = conn.execute(
            "SELECT COUNT(*) FROM company_expert_contracts WHERE company_id=? AND expert_id=?",
            (comp_id, exp_id)
        ).fetchone()[0]
        assert count == 2, "Phải cho phép nhiều hợp đồng cùng company+expert"

    def test_evaluation_scores_check(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        from app.utils.helpers import hash_password

        for uname, role in [("cand_e", "candidate"), ("exp_e", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@sp.local", hash_password("P@ss1"), uname, role)
            )
        cand_id = conn.execute("SELECT id FROM users WHERE username='cand_e'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_e'").fetchone()[0]

        conn.execute(
            "INSERT INTO interviews(candidate_id, title, scheduled_at) VALUES(?, 'IV', '2026-01-01')",
            (cand_id,)
        )
        iv_id = conn.execute("SELECT id FROM interviews").fetchone()[0]

        # Valid scores 1-5
        conn.execute(
            "INSERT INTO interview_evaluations(interview_id, expert_id, technical_score)"
            " VALUES(?,?,?)", (iv_id, exp_id, 5)
        )
        conn.commit()

        # Invalid score 6
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO interview_evaluations(interview_id, expert_id, technical_score)"
                " VALUES(?,?,?)", (iv_id, exp_id, 6)
            )

    def test_recommendation_check(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)
        from app.utils.helpers import hash_password

        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("cand_r", "cand_r@sp.local", hash_password("P@ss1"), "Cand", "candidate")
        )
        cand_id = conn.execute("SELECT id FROM users WHERE username='cand_r'").fetchone()[0]

        # Tạo 4 expert khác nhau cho 4 recommendation khác nhau
        for i in range(4):
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (f"exp_r{i}", f"exp_r{i}@sp.local", hash_password("P@ss1"), f"Exp{i}", "expert")
            )

        conn.execute(
            "INSERT INTO interviews(candidate_id, title, scheduled_at) VALUES(?, 'IV', '2026-01-01')",
            (cand_id,)
        )
        iv_id = conn.execute("SELECT id FROM interviews").fetchone()[0]

        valid_recs = ["strong_hire", "hire", "no_hire", "strong_no_hire"]
        for i, rec in enumerate(valid_recs):
            exp_id = conn.execute(
                "SELECT id FROM users WHERE username=?", (f"exp_r{i}",)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO interview_evaluations(interview_id, expert_id, recommendation)"
                " VALUES(?,?,?)", (iv_id, exp_id, rec)
            )
        conn.commit()

        # Invalid — tạo expert thứ 5
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("exp_r5", "exp_r5@sp.local", hash_password("P@ss1"), "Exp5", "expert")
        )
        exp_id_5 = conn.execute("SELECT id FROM users WHERE username='exp_r5'").fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO interview_evaluations(interview_id, expert_id, recommendation)"
                " VALUES(?,?,?)", (iv_id, exp_id_5, "maybe_hire")
            )


# ══════════════════════════════════════════════════════════════════════════════
# Index
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004Indexes:
    EXPECTED_INDEXES = [
        "idx_company_profiles_user",
        "idx_expert_profiles_user",
        "idx_candidate_profiles_user",
        "idx_qb_expert", "idx_qb_skill", "idx_qb_type", "idx_qb_published",
        "idx_qo_question",
        "idx_ep_skill", "idx_ep_created_by",
        "idx_epq_paper", "idx_epq_question",
        "idx_es_paper", "idx_es_candidate", "idx_es_company", "idx_es_status",
        "idx_ea_session", "idx_ea_question", "idx_ea_graded_by", "idx_ea_is_graded",
        "idx_gr_answer", "idx_gr_grader",
        "idx_iv_candidate", "idx_iv_company", "idx_iv_status",
        "idx_ip_interview", "idx_ip_expert",
        "idx_ie_interview", "idx_ie_expert",
        "idx_contracts_company", "idx_contracts_expert", "idx_contracts_status",
        "idx_tasks_company", "idx_tasks_expert", "idx_tasks_status", "idx_tasks_type",
    ]

    def test_indexes_created(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)

        indexes = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ).fetchall()
        }
        for idx in self.EXPECTED_INDEXES:
            assert idx in indexes, f"Thiếu index: {idx}"


# ══════════════════════════════════════════════════════════════════════════════
# Triggers
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004Triggers:
    EXPECTED_TRIGGERS = [
        "trg_company_profiles_updated",
        "trg_expert_profiles_updated",
        "trg_candidate_profiles_updated",
        "trg_question_bank_updated",
        "trg_exam_papers_updated",
    ]

    def test_triggers_created(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_004_create_business_tables(conn)

        triggers = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_%_updated'"
            ).fetchall()
        }
        for trg in self.EXPECTED_TRIGGERS:
            assert trg in triggers, f"Thiếu trigger: {trg}"


# ══════════════════════════════════════════════════════════════════════════════
# Legacy DB upgrade
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004LegacyUpgrade:
    def test_legacy_db_gets_new_tables(self, legacy_db):
        """DB cũ (Giai đoạn 01) → MIG-004 thêm 14 bảng mới."""
        conn = legacy_db.get_connection()
        _mig_004_create_business_tables(conn)

        for table in EXPECTED_NEW_TABLES:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            assert row is not None, f"Bảng {table} không tạo được trên legacy DB"

    def test_legacy_data_not_lost(self, legacy_db):
        """Dữ liệu legacy không mất sau MIG-004."""
        conn = legacy_db.get_connection()
        users_before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        settings_before = conn.execute("SELECT COUNT(*) FROM app_settings").fetchone()[0]

        _mig_004_create_business_tables(conn)

        users_after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        settings_after = conn.execute("SELECT COUNT(*) FROM app_settings").fetchone()[0]
        assert users_after == users_before
        assert settings_after == settings_before

    def test_legacy_admin_still_exists(self, legacy_db):
        conn = legacy_db.get_connection()
        _mig_004_create_business_tables(conn)
        admin = conn.execute(
            "SELECT * FROM users WHERE username='admin'"
        ).fetchone()
        assert admin is not None
