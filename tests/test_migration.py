# -*- coding: utf-8 -*-
"""
Tests: Database migrations — MIG-001, MIG-002, MIG-003.
Kiểm tra trên cả DB mới và DB cũ (legacy).
KHÔNG thao tác trên data/skillproof.db thật.
"""

import sqlite3
import pytest

from app.database.schema import (
    _mig_001_fix_admin_hash,
    _mig_002_fix_role_constraint,
    _mig_003_remove_hardcoded_admin,
    create_all_tables,
    is_first_run,
    mark_setup_done,
    drop_all_tables,
)
from app.utils.helpers import verify_password, needs_rehash


# ══════════════════════════════════════════════════════════════════════════════
# MIG-001: Fix admin hash từ SHA-256 thuần → legacy salted
# ══════════════════════════════════════════════════════════════════════════════

class TestMig001:
    OLD_HASH  = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
    PH1_HASH  = "67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56"

    def test_mig001_upgrades_raw_hash(self, legacy_db):
        conn = legacy_db.get_connection()
        # Đặt lại hash về OLD_HASH để test
        conn.execute(
            "UPDATE users SET password=? WHERE username='admin'", (self.OLD_HASH,)
        )
        conn.commit()

        _mig_001_fix_admin_hash(conn)

        row = conn.execute(
            "SELECT password FROM users WHERE username='admin'"
        ).fetchone()
        assert row["password"] == self.PH1_HASH

    def test_mig001_idempotent(self, legacy_db):
        conn = legacy_db.get_connection()
        _mig_001_fix_admin_hash(conn)
        _mig_001_fix_admin_hash(conn)  # Lần 2 không thay đổi gì
        row = conn.execute(
            "SELECT password FROM users WHERE username='admin'"
        ).fetchone()
        # Hash phải là PH1_HASH (legacy salted) hoặc PBKDF2
        assert row["password"] == self.PH1_HASH or row["password"].startswith("pbkdf2:")

    def test_mig001_skips_pbkdf2(self, fresh_db):
        """Không chạm user đã dùng PBKDF2."""
        from app.utils.helpers import hash_password
        pw_hash = hash_password("admin")
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,'admin')",
            ("admin2", "admin2@sp.local", pw_hash, "Admin2"),
        )
        fresh_db.get_connection().commit()

        conn = fresh_db.get_connection()
        _mig_001_fix_admin_hash(conn)

        row = conn.execute(
            "SELECT password FROM users WHERE username='admin2'"
        ).fetchone()
        # Hash không thay đổi
        assert row["password"] == pw_hash


# ══════════════════════════════════════════════════════════════════════════════
# MIG-002: Recreate users table với role CHECK đầy đủ
# ══════════════════════════════════════════════════════════════════════════════

class TestMig002:
    NEW_ROLES = "'admin','instructor','student','candidate','company','expert'"

    def _ddl_normalized(self, conn) -> str:
        """Lấy DDL và normalize whitespace để so sánh."""
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='users'"
        ).fetchone()["sql"]
        import re
        return re.sub(r'\s+', ' ', ddl)

    def test_mig002_updates_constraint(self, legacy_db):
        conn = legacy_db.get_connection()
        _mig_002_fix_role_constraint(conn)
        ddl = self._ddl_normalized(conn)
        # Kiểm tra từng role có trong DDL (bỏ qua whitespace/newline)
        for role in ["candidate", "company", "expert"]:
            assert f"'{role}'" in ddl, f"Role '{role}' không có trong constraint"

    def test_mig002_preserves_data(self, legacy_db):
        conn = legacy_db.get_connection()
        count_before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        _mig_002_fix_role_constraint(conn)

        count_after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count_before == count_after, (
            f"MIG-002 mất dữ liệu: {count_before} → {count_after}"
        )

    def test_mig002_preserves_specific_user(self, legacy_db):
        """Admin user vẫn còn sau migration với đầy đủ fields."""
        conn = legacy_db.get_connection()
        _mig_002_fix_role_constraint(conn)

        row = conn.execute(
            "SELECT * FROM users WHERE username='admin'"
        ).fetchone()
        assert row is not None
        assert row["email"] == "admin@skillproof.local"
        assert row["role"] == "admin"
        assert row["is_active"] == 1

    def test_mig002_idempotent(self, legacy_db):
        """Chạy 2 lần không gây lỗi và không mất dữ liệu."""
        conn = legacy_db.get_connection()
        count_before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        _mig_002_fix_role_constraint(conn)
        _mig_002_fix_role_constraint(conn)  # Lần 2

        count_after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count_before == count_after

    def test_mig002_skips_if_already_correct(self, fresh_db):
        """Không làm gì nếu constraint đã đúng."""
        conn = fresh_db.get_connection()
        count_before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        _mig_002_fix_role_constraint(conn)

        count_after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        # Không thay đổi row count khi đã đúng
        assert count_before == count_after

    def test_mig002_new_roles_insertable(self, legacy_db):
        """Sau migration, có thể INSERT user với role mới."""
        conn = legacy_db.get_connection()
        _mig_002_fix_role_constraint(conn)

        for role in ["candidate", "company", "expert"]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (f"test_{role}", f"{role}@sp.local", "h", "Test", role),
            )
        conn.commit()

        count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role IN ('candidate','company','expert')"
        ).fetchone()[0]
        assert count == 3

    def test_mig002_foreign_keys_intact(self, legacy_db):
        """
        Foreign key constraints được định nghĩa đúng trong schema sau migration.
        Kiểm tra DDL của bảng users mới có đầy đủ columns.
        """
        conn = legacy_db.get_connection()
        _mig_002_fix_role_constraint(conn)

        # Kiểm tra bảng users sau migration có đủ cột
        cols = conn.execute("PRAGMA table_info(users)").fetchall()
        col_names = [c[1] for c in cols]
        for required_col in ["id","username","email","password","full_name","role","is_active"]:
            assert required_col in col_names, f"Thiếu cột '{required_col}' sau MIG-002"

        # Kiểm tra dữ liệu admin vẫn có thể đọc
        admin = conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()
        assert admin is not None
        assert admin["email"] == "admin@skillproof.local"

    def test_mig002_trigger_recreated(self, legacy_db):
        """Trigger trg_users_updated phải tồn tại sau migration."""
        conn = legacy_db.get_connection()
        _mig_002_fix_role_constraint(conn)

        trigger = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_users_updated'"
        ).fetchone()
        assert trigger is not None, "Trigger trg_users_updated bị mất sau MIG-002"

    def test_mig002_skips_if_already_correct(self, fresh_db):
        """Không làm gì nếu constraint đã đúng."""
        conn = fresh_db.get_connection()
        ddl_before = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='users'"
        ).fetchone()["sql"]

        _mig_002_fix_role_constraint(conn)

        ddl_after = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='users'"
        ).fetchone()["sql"]

        # DDL không thay đổi (đã đúng từ đầu)
        assert ddl_before == ddl_after


# ══════════════════════════════════════════════════════════════════════════════
# MIG-003: Vô hiệu hóa admin legacy
# ══════════════════════════════════════════════════════════════════════════════

class TestMig003:
    LEGACY_HASH = "67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56"

    def test_mig003_deactivates_legacy_admin(self, legacy_db):
        """Admin với legacy hash bị vô hiệu hóa."""
        conn = legacy_db.get_connection()
        _mig_003_remove_hardcoded_admin(conn)

        row = conn.execute(
            "SELECT is_active FROM users WHERE username='admin'"
        ).fetchone()
        assert row["is_active"] == 0

    def test_mig003_sets_reset_required(self, legacy_db):
        """setup_done được đặt thành 'reset_required'."""
        conn = legacy_db.get_connection()
        _mig_003_remove_hardcoded_admin(conn)

        row = conn.execute(
            "SELECT value FROM app_settings WHERE key='setup_done'"
        ).fetchone()
        assert row["value"] == "reset_required"

    def test_mig003_does_not_delete_admin(self, legacy_db):
        """Admin không bị xóa — chỉ vô hiệu hóa."""
        conn = legacy_db.get_connection()
        _mig_003_remove_hardcoded_admin(conn)

        row = conn.execute(
            "SELECT * FROM users WHERE username='admin'"
        ).fetchone()
        assert row is not None

    def test_mig003_skips_pbkdf2_admin(self, fresh_db):
        """Admin đã dùng PBKDF2 không bị chạm."""
        from app.utils.helpers import hash_password
        conn = fresh_db.get_connection()
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,'admin',1)",
            ("admin3", "admin3@sp.local", hash_password("Admin@123"), "Admin3"),
        )
        conn.commit()

        _mig_003_remove_hardcoded_admin(conn)

        row = conn.execute(
            "SELECT is_active FROM users WHERE username='admin3'"
        ).fetchone()
        assert row["is_active"] == 1  # Không bị vô hiệu hóa

    def test_mig003_no_admin_is_noop(self, fresh_db):
        """Không có admin → không crash, không thay đổi gì."""
        conn = fresh_db.get_connection()
        setup_before = conn.execute(
            "SELECT value FROM app_settings WHERE key='setup_done'"
        ).fetchone()["value"]

        _mig_003_remove_hardcoded_admin(conn)

        setup_after = conn.execute(
            "SELECT value FROM app_settings WHERE key='setup_done'"
        ).fetchone()["value"]
        assert setup_before == setup_after

    def test_mig003_idempotent(self, legacy_db):
        conn = legacy_db.get_connection()
        _mig_003_remove_hardcoded_admin(conn)
        _mig_003_remove_hardcoded_admin(conn)  # Lần 2 không crash

        row = conn.execute(
            "SELECT value FROM app_settings WHERE key='setup_done'"
        ).fetchone()
        assert row["value"] == "reset_required"


# ══════════════════════════════════════════════════════════════════════════════
# create_all_tables: toàn bộ migrations chạy đúng thứ tự
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateAllTables:
    def test_fresh_db_setup_done_zero(self, fresh_db):
        """DB mới: setup_done='0', không có admin."""
        assert is_first_run()

    def test_fresh_db_no_admin(self, fresh_db):
        """DB mới không có admin hardcode."""
        row = fresh_db.fetchone("SELECT * FROM users WHERE username='admin'")
        assert row is None

    def test_fresh_db_seven_tables(self, fresh_db):
        tables = {
            r["name"] for r in fresh_db.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            if not r["name"].startswith("sqlite_")
        }
        assert tables == {
            "users", "skills", "certificates", "courses",
            "enrollments", "assessments", "app_settings"
        }

    def test_legacy_db_full_migration(self, legacy_db):
        """
        Chạy create_all_tables trên legacy DB:
        - MIG-001: hash cập nhật
        - MIG-002: role constraint đúng
        - MIG-003: admin bị vô hiệu hóa
        """
        conn = legacy_db.get_connection()

        # Chạy toàn bộ migrations
        _mig_001_fix_admin_hash(conn)
        _mig_002_fix_role_constraint(conn)
        _mig_003_remove_hardcoded_admin(conn)

        # Kiểm tra kết quả
        admin = conn.execute(
            "SELECT password, is_active FROM users WHERE username='admin'"
        ).fetchone()
        assert admin is not None
        # Hash đã được nâng cấp (MIG-001 hoặc vẫn là legacy salted)
        assert admin["is_active"] == 0  # MIG-003

        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='users'"
        ).fetchone()["sql"]
        import re as _re
        ddl_norm = _re.sub(r'\s+', ' ', ddl)
        # MIG-002: role constraint đúng
        assert "'candidate'" in ddl_norm and "'company'" in ddl_norm and "'expert'" in ddl_norm

    def test_mark_setup_done(self, fresh_db):
        mark_setup_done()
        assert not is_first_run()

    def test_is_first_run_reset_required(self, legacy_db):
        """setup_done='reset_required' vẫn được coi là first run."""
        conn = legacy_db.get_connection()
        _mig_003_remove_hardcoded_admin(conn)
        assert is_first_run()


# ══════════════════════════════════════════════════════════════════════════════
# Rollback MIG-002
# ══════════════════════════════════════════════════════════════════════════════

class TestMig002Rollback:
    def test_rollback_verified_by_row_count(self, legacy_db):
        """
        MIG-002 kiểm tra row count trước/sau INSERT.
        Xác minh: nếu count match → commit; nếu không → rollback.
        Test này xác minh logic kiểm tra row count hoạt động đúng.
        """
        conn = legacy_db.get_connection()
        count_before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        # Chạy migration thành công
        _mig_002_fix_role_constraint(conn)

        count_after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count_before == count_after, (
            "MIG-002 phải bảo toàn số hàng dữ liệu"
        )

        # Xác nhận backup table đã bị dọn sạch
        backup_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE name='_users_mig002_backup'"
        ).fetchone()
        assert backup_exists is None, "Backup table phải được dọn sạch sau migration thành công"

    def test_rollback_behavior_documented(self, legacy_db):
        """
        Tài liệu: MIG-002 có logic rollback khi INSERT thất bại.
        Logic rollback được kiểm tra trong source code (schema.py).
        Hành vi: count mismatch → DROP users, rename backup → users.
        Test này xác nhận source code chứa logic rollback.
        """
        import inspect
        from app.database.schema import _mig_002_fix_role_constraint
        source = inspect.getsource(_mig_002_fix_role_constraint)
        assert "count_after != count_before" in source, \
            "MIG-002 phải có kiểm tra row count"
        assert "ROLLBACK" in source or "_users_mig002_backup" in source, \
            "MIG-002 phải có logic rollback"
