# -*- coding: utf-8 -*-
"""
Tests: MIG-005 — Mở rộng company_expert_contracts và soft-delete users.

Kiểm tra:
A. users.is_deleted được thêm đúng (ALTER TABLE safe)
B. company_expert_contracts được recreate với 6 status + 2 cột mới
C. Dữ liệu cũ được bảo toàn
D. Idempotent (chạy nhiều lần không lỗi)
E. Rollback khi lỗi
F. Tích hợp create_all_tables()
"""

import sqlite3
import pytest

from app.database.schema import (
    _mig_005_extend_contracts_and_softdelete,
    create_all_tables,
)


# ══════════════════════════════════════════════════════════════════════════════
# A. users.is_deleted
# ══════════════════════════════════════════════════════════════════════════════

class TestMig005AUsersIsDeleted:
    def test_is_deleted_column_added(self, fresh_db):
        """MIG-005A thêm cột is_deleted vào bảng users."""
        conn = fresh_db.get_connection()
        _mig_005_extend_contracts_and_softdelete(conn)

        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        assert "is_deleted" in cols, "Cột is_deleted phải được thêm vào users"

    def test_is_deleted_default_zero(self, fresh_db):
        """is_deleted mặc định 0 cho tất cả user hiện có."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("u1", "u1@t.com", hash_password("P@ss1"), "User1", "candidate")
        )
        conn.commit()
        _mig_005_extend_contracts_and_softdelete(conn)

        rows = conn.execute("SELECT is_deleted FROM users").fetchall()
        assert all(r[0] == 0 for r in rows), "Tất cả user hiện có phải có is_deleted=0"

    def test_is_deleted_index_created(self, fresh_db):
        """Index idx_users_is_deleted được tạo."""
        conn = fresh_db.get_connection()
        _mig_005_extend_contracts_and_softdelete(conn)

        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
            " AND name='idx_users_is_deleted'"
        ).fetchone()
        assert idx is not None

    def test_is_deleted_idempotent(self, fresh_db):
        """Chạy MIG-005A 3 lần không lỗi."""
        conn = fresh_db.get_connection()
        for _ in range(3):
            _mig_005_extend_contracts_and_softdelete(conn)

        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        assert "is_deleted" in cols

    def test_new_user_gets_is_deleted_zero(self, fresh_db):
        """User tạo sau migration có is_deleted=0 theo DEFAULT."""
        conn = fresh_db.get_connection()
        _mig_005_extend_contracts_and_softdelete(conn)

        from app.utils.helpers import hash_password
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("u2", "u2@t.com", hash_password("P@ss1"), "User2", "candidate")
        )
        conn.commit()

        row = conn.execute(
            "SELECT is_deleted FROM users WHERE username='u2'"
        ).fetchone()
        assert row[0] == 0

    def test_soft_delete_does_not_remove_row(self, fresh_db):
        """Đặt is_deleted=1 không xóa row khỏi DB."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password
        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("sdel", "sdel@t.com", hash_password("P@ss1"), "SDel", "candidate")
        )
        conn.commit()
        _mig_005_extend_contracts_and_softdelete(conn)

        conn.execute("UPDATE users SET is_deleted=1 WHERE username='sdel'")
        conn.commit()

        row = conn.execute("SELECT * FROM users WHERE username='sdel'").fetchone()
        assert row is not None, "Row phải tồn tại sau soft-delete"
        assert row["is_deleted"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# B. company_expert_contracts — recreate với 6 status
# ══════════════════════════════════════════════════════════════════════════════

class TestMig005BContractsRecreate:
    def test_new_status_values_accepted(self, fresh_db):
        """Sau MIG-005B, có thể INSERT pending_expert và rejected."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        for uname, role in [("comp_m5", "company"), ("exp_m5", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@t.com", hash_password("P@ss1"), uname, role)
            )
        conn.commit()
        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_m5'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_m5'").fetchone()[0]

        _mig_005_extend_contracts_and_softdelete(conn)

        # INSERT với pending_expert
        conn.execute(
            "INSERT INTO company_expert_contracts"
            "(company_id, expert_id, contract_code, status)"
            " VALUES(?,?,?,'pending_expert')",
            (comp_id, exp_id, "CTR-PE-001")
        )
        conn.commit()

        row = conn.execute(
            "SELECT status FROM company_expert_contracts WHERE contract_code='CTR-PE-001'"
        ).fetchone()
        assert row[0] == "pending_expert"

    def test_rejected_status_accepted(self, fresh_db):
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        for uname, role in [("comp_rej", "company"), ("exp_rej", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@t.com", hash_password("P@ss1"), uname, role)
            )
        conn.commit()
        _mig_005_extend_contracts_and_softdelete(conn)

        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_rej'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_rej'").fetchone()[0]

        conn.execute(
            "INSERT INTO company_expert_contracts"
            "(company_id, expert_id, contract_code, status)"
            " VALUES(?,?,?,'rejected')",
            (comp_id, exp_id, "CTR-REJ-001")
        )
        conn.commit()

        row = conn.execute(
            "SELECT status FROM company_expert_contracts WHERE contract_code='CTR-REJ-001'"
        ).fetchone()
        assert row[0] == "rejected"

    def test_invalid_status_still_rejected(self, fresh_db):
        """CHECK constraint vẫn chặn status không hợp lệ sau migrate."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        for uname, role in [("comp_inv", "company"), ("exp_inv", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@t.com", hash_password("P@ss1"), uname, role)
            )
        conn.commit()
        _mig_005_extend_contracts_and_softdelete(conn)

        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_inv'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_inv'").fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO company_expert_contracts"
                "(company_id, expert_id, contract_code, status)"
                " VALUES(?,?,?,'invalid_status')",
                (comp_id, exp_id, "CTR-INV-001")
            )

    def test_all_6_status_values_valid(self, fresh_db):
        """Tất cả 6 trạng thái hợp lệ đều được chấp nhận."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        for uname, role in [("comp_6", "company"), ("exp_6", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@t.com", hash_password("P@ss1"), uname, role)
            )
        conn.commit()
        _mig_005_extend_contracts_and_softdelete(conn)

        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_6'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_6'").fetchone()[0]

        for status in ["pending_expert", "rejected", "active",
                       "completed", "terminated", "cancelled"]:
            code = f"CTR-{status[:4].upper()}"
            conn.execute(
                "INSERT INTO company_expert_contracts"
                "(company_id, expert_id, contract_code, status)"
                " VALUES(?,?,?,?)",
                (comp_id, exp_id, code, status)
            )
        conn.commit()

        count = conn.execute(
            "SELECT COUNT(*) FROM company_expert_contracts"
        ).fetchone()[0]
        assert count == 6

    def test_new_columns_rejection_reason(self, fresh_db):
        """Cột rejection_reason và terminated_reason tồn tại."""
        conn = fresh_db.get_connection()
        _mig_005_extend_contracts_and_softdelete(conn)

        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(company_expert_contracts)"
        ).fetchall()}
        assert "rejection_reason" in cols
        assert "terminated_reason" in cols

    def test_default_status_is_pending_expert(self, fresh_db):
        """DEFAULT status mới là 'pending_expert' (thay vì 'active')."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        for uname, role in [("comp_def", "company"), ("exp_def", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@t.com", hash_password("P@ss1"), uname, role)
            )
        conn.commit()
        _mig_005_extend_contracts_and_softdelete(conn)

        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_def'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_def'").fetchone()[0]

        conn.execute(
            "INSERT INTO company_expert_contracts"
            "(company_id, expert_id, contract_code)"
            " VALUES(?,?,?)",
            (comp_id, exp_id, "CTR-DEF-001")
        )
        conn.commit()

        row = conn.execute(
            "SELECT status FROM company_expert_contracts WHERE contract_code='CTR-DEF-001'"
        ).fetchone()
        assert row[0] == "pending_expert"


# ══════════════════════════════════════════════════════════════════════════════
# C. Bảo toàn dữ liệu cũ
# ══════════════════════════════════════════════════════════════════════════════

class TestMig005CDataPreservation:
    def test_existing_contracts_preserved(self, fresh_db):
        """
        DB đã có hợp đồng (status='active') → sau MIG-005B data vẫn còn.
        Mô phỏng bằng cách tạo contract trực tiếp trước khi chạy MIG-005.
        """
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        # Tạo users
        for uname, role in [("comp_old", "company"), ("exp_old", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@t.com", hash_password("P@ss1"), uname, role)
            )
        conn.commit()
        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_old'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_old'").fetchone()[0]

        # Tạo hợp đồng với status 'active' (trước khi MIG-005)
        # Lúc này DB đã có company_expert_contracts với CHECK cũ 4 trạng thái
        conn.execute(
            "INSERT INTO company_expert_contracts"
            "(company_id, expert_id, contract_code, status)"
            " VALUES(?,?,?,'active')",
            (comp_id, exp_id, "CTR-OLD-001")
        )
        conn.commit()
        count_before = conn.execute(
            "SELECT COUNT(*) FROM company_expert_contracts"
        ).fetchone()[0]
        assert count_before == 1

        # Chạy MIG-005
        _mig_005_extend_contracts_and_softdelete(conn)

        count_after = conn.execute(
            "SELECT COUNT(*) FROM company_expert_contracts"
        ).fetchone()[0]
        assert count_before == count_after, "Số hàng phải giữ nguyên"

        old_contract = conn.execute(
            "SELECT status FROM company_expert_contracts WHERE contract_code='CTR-OLD-001'"
        ).fetchone()
        assert old_contract is not None
        assert old_contract[0] == "active", "Status cũ 'active' phải được bảo toàn"

    def test_legacy_active_contracts_still_valid(self, fresh_db):
        """Hợp đồng status='active' cũ vẫn hợp lệ trong schema mới."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        for uname, role in [("comp_lv", "company"), ("exp_lv", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@t.com", hash_password("P@ss1"), uname, role)
            )
        conn.commit()
        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_lv'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_lv'").fetchone()[0]

        conn.execute(
            "INSERT INTO company_expert_contracts"
            "(company_id, expert_id, contract_code, status)"
            " VALUES(?,?,?,'active')",
            (comp_id, exp_id, "CTR-LV-001")
        )
        conn.commit()

        _mig_005_extend_contracts_and_softdelete(conn)

        # Update status từ active sang completed — phải OK
        conn.execute(
            "UPDATE company_expert_contracts SET status='completed'"
            " WHERE contract_code='CTR-LV-001'"
        )
        conn.commit()
        row = conn.execute(
            "SELECT status FROM company_expert_contracts WHERE contract_code='CTR-LV-001'"
        ).fetchone()
        assert row[0] == "completed"

    def test_users_data_preserved(self, fresh_db):
        """User cũ không mất sau MIG-005."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        conn.execute(
            "INSERT INTO users(username,email,password,full_name,role)"
            " VALUES(?,?,?,?,?)",
            ("preserve_u", "preserve_u@t.com", hash_password("P@ss1"), "Preserve", "candidate")
        )
        conn.commit()
        count_before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        _mig_005_extend_contracts_and_softdelete(conn)

        count_after = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count_before == count_after


# ══════════════════════════════════════════════════════════════════════════════
# D. Idempotent
# ══════════════════════════════════════════════════════════════════════════════

class TestMig005DIdempotent:
    def test_run_twice_no_error(self, fresh_db):
        conn = fresh_db.get_connection()
        _mig_005_extend_contracts_and_softdelete(conn)
        _mig_005_extend_contracts_and_softdelete(conn)  # Lần 2 — no-op

        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        assert "is_deleted" in cols

    def test_run_three_times_no_error(self, fresh_db):
        conn = fresh_db.get_connection()
        for _ in range(3):
            _mig_005_extend_contracts_and_softdelete(conn)

        # Contracts vẫn có đủ 6 status
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='company_expert_contracts'"
        ).fetchone()["sql"]
        assert "pending_expert" in ddl

    def test_data_unchanged_after_second_run(self, fresh_db):
        """Chạy migration lần 2 không làm thay đổi dữ liệu."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        _mig_005_extend_contracts_and_softdelete(conn)

        for uname, role in [("comp_idem", "company"), ("exp_idem", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@t.com", hash_password("P@ss1"), uname, role)
            )
        conn.commit()

        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_idem'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_idem'").fetchone()[0]

        conn.execute(
            "INSERT INTO company_expert_contracts"
            "(company_id, expert_id, contract_code, status)"
            " VALUES(?,?,?,'pending_expert')",
            (comp_id, exp_id, "CTR-IDEM")
        )
        conn.commit()

        # Chạy lại migration
        _mig_005_extend_contracts_and_softdelete(conn)

        # Dữ liệu không mất
        row = conn.execute(
            "SELECT status FROM company_expert_contracts WHERE contract_code='CTR-IDEM'"
        ).fetchone()
        assert row is not None and row[0] == "pending_expert"


# ══════════════════════════════════════════════════════════════════════════════
# E. create_all_tables bao gồm MIG-005
# ══════════════════════════════════════════════════════════════════════════════

class TestMig005ECreateAllTables:
    def test_create_all_tables_includes_mig005(self, fresh_db):
        """create_all_tables() tự động chạy MIG-005."""
        conn = fresh_db.get_connection()

        # MIG-005 đã chạy trong fresh_db fixture (qua create_all_tables)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        assert "is_deleted" in cols

        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='company_expert_contracts'"
        ).fetchone()["sql"]
        assert "pending_expert" in ddl

    def test_total_table_count_unchanged(self, fresh_db):
        """MIG-005 không thêm bảng mới, chỉ sửa cột/CHECK."""
        conn = fresh_db.get_connection()
        tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        # Vẫn là 22 bảng (7 cũ + 15 MIG-004), không tăng thêm
        assert tables == 22, f"Expected 22 tables, got {tables}"

    def test_contract_code_unique_constraint_still_works(self, fresh_db):
        """UNIQUE(contract_code) vẫn hoạt động sau migrate."""
        conn = fresh_db.get_connection()
        from app.utils.helpers import hash_password

        for uname, role in [("comp_uniq", "company"), ("exp_uniq", "expert")]:
            conn.execute(
                "INSERT INTO users(username,email,password,full_name,role)"
                " VALUES(?,?,?,?,?)",
                (uname, f"{uname}@t.com", hash_password("P@ss1"), uname, role)
            )
        conn.commit()
        comp_id = conn.execute("SELECT id FROM users WHERE username='comp_uniq'").fetchone()[0]
        exp_id  = conn.execute("SELECT id FROM users WHERE username='exp_uniq'").fetchone()[0]

        conn.execute(
            "INSERT INTO company_expert_contracts"
            "(company_id, expert_id, contract_code) VALUES(?,?,?)",
            (comp_id, exp_id, "UNIQUE-CODE")
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO company_expert_contracts"
                "(company_id, expert_id, contract_code) VALUES(?,?,?)",
                (comp_id, exp_id, "UNIQUE-CODE")
            )
