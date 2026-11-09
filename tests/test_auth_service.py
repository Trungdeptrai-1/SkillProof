# -*- coding: utf-8 -*-
"""
Tests: AuthService — login, logout, session, phân quyền, timing, lazy rehash.
Dùng fresh_db fixture — không chạm DB thật.
"""

import time
import pytest
from unittest.mock import patch
import sqlite3

from app.services.auth_service import AuthService, SessionManager, LoginResult
from app.utils.helpers import hash_password, verify_password, needs_rehash


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def make_auth(fresh_db):
    """AuthService sạch với session reset."""
    SessionManager._instance = None
    return AuthService()


# ══════════════════════════════════════════════════════════════════════════════
# TC-01: Đăng nhập đúng
# ══════════════════════════════════════════════════════════════════════════════

class TestLoginSuccess:
    def test_login_correct(self, fresh_db, admin_user):
        auth = make_auth(fresh_db)
        email, pw = admin_user
        r = auth.login(email, pw)
        assert r.success
        assert r.status == LoginResult.SUCCESS
        assert r.user is not None
        assert r.user.email == email
        assert r.user.role == "admin"
        auth.logout()

    def test_session_set_after_login(self, fresh_db, admin_user):
        auth = make_auth(fresh_db)
        email, pw = admin_user
        auth.login(email, pw)
        s = SessionManager.instance()
        assert s.is_logged_in
        assert s.current_user.email == email
        auth.logout()

    def test_login_candidate_role(self, fresh_db, candidate_user):
        auth = make_auth(fresh_db)
        email, pw = candidate_user
        r = auth.login(email, pw)
        assert r.success and r.user.role == "candidate"
        auth.logout()


# ══════════════════════════════════════════════════════════════════════════════
# TC-02 / TC-03: Sai email / sai password
# ══════════════════════════════════════════════════════════════════════════════

class TestLoginFailure:
    def test_wrong_email(self, fresh_db):
        auth = make_auth(fresh_db)
        r = auth.login("noone@sp.local", "AnyPass@1")
        assert not r.success
        assert r.status == LoginResult.USER_NOT_FOUND
        # Thông báo giống WRONG_PASSWORD — không tiết lộ email
        assert r.message == LoginResult.MESSAGES[LoginResult.WRONG_PASSWORD]

    def test_wrong_password(self, fresh_db, admin_user):
        auth = make_auth(fresh_db)
        email, _ = admin_user
        r = auth.login(email, "WrongPass@1")
        assert not r.success
        assert r.status == LoginResult.WRONG_PASSWORD

    def test_same_message_for_missing_vs_wrong(self, fresh_db, admin_user):
        """USER_NOT_FOUND và WRONG_PASSWORD trả cùng message — tránh enumeration."""
        auth = make_auth(fresh_db)
        email, _ = admin_user
        r_missing = auth.login("ghost@sp.local", "Any@1Pass")
        r_wrong   = auth.login(email, "BadPass@1")
        assert r_missing.message == r_wrong.message


# ══════════════════════════════════════════════════════════════════════════════
# TC-04 / TC-05: Trường trống
# ══════════════════════════════════════════════════════════════════════════════

class TestEmptyFields:
    def test_empty_email(self, fresh_db):
        auth = make_auth(fresh_db)
        assert auth.login("", "Pass@1").status == LoginResult.EMPTY_EMAIL

    def test_whitespace_email(self, fresh_db):
        auth = make_auth(fresh_db)
        assert auth.login("   ", "Pass@1").status == LoginResult.EMPTY_EMAIL

    def test_empty_password(self, fresh_db, admin_user):
        auth = make_auth(fresh_db)
        email, _ = admin_user
        assert auth.login(email, "").status == LoginResult.EMPTY_PASSWORD


# ══════════════════════════════════════════════════════════════════════════════
# TC-06: Email sai định dạng
# ══════════════════════════════════════════════════════════════════════════════

class TestInvalidEmailFormat:
    @pytest.mark.parametrize("bad_email", [
        "notanemail",
        "missing@",
        "@nodomain.com",
        "a b@test.com",
        "user@",
        "double@@test.com",
    ])
    def test_invalid_format(self, fresh_db, bad_email):
        auth = make_auth(fresh_db)
        r = auth.login(bad_email, "Pass@1Word")
        assert r.status == LoginResult.INVALID_EMAIL_FORMAT


# ══════════════════════════════════════════════════════════════════════════════
# TC-07: Tài khoản bị khoá
# ══════════════════════════════════════════════════════════════════════════════

class TestInactiveAccount:
    def test_inactive_login(self, fresh_db, inactive_user):
        auth = make_auth(fresh_db)
        email, pw = inactive_user
        r = auth.login(email, pw)
        assert not r.success
        assert r.status == LoginResult.ACCOUNT_INACTIVE

    def test_inactive_session_not_set(self, fresh_db, inactive_user):
        auth = make_auth(fresh_db)
        email, pw = inactive_user
        auth.login(email, pw)
        assert not SessionManager.instance().is_logged_in


# ══════════════════════════════════════════════════════════════════════════════
# TC-08: Role đúng
# ══════════════════════════════════════════════════════════════════════════════

class TestRoleAssignment:
    @pytest.mark.parametrize("role", [
        "admin", "instructor", "student", "candidate", "company", "expert"
    ])
    def test_all_roles_can_login(self, fresh_db, role):
        pw    = "Role@Test1"
        email = f"{role}@sp.local"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            (role, email, hash_password(pw), f"Test {role}", role),
        )
        SessionManager._instance = None
        auth = AuthService()
        r = auth.login(email, pw)
        assert r.success, f"Role {role} login failed: {r.status}"
        assert r.user.role == role
        auth.logout()


# ══════════════════════════════════════════════════════════════════════════════
# TC-09: Đăng xuất + đăng nhập lại
# ══════════════════════════════════════════════════════════════════════════════

class TestLogoutRelogin:
    def test_logout_clears_session(self, fresh_db, admin_user):
        auth = make_auth(fresh_db)
        email, pw = admin_user
        auth.login(email, pw)
        assert SessionManager.instance().is_logged_in
        auth.logout()
        assert not SessionManager.instance().is_logged_in
        assert SessionManager.instance().current_user is None

    def test_relogin_after_logout(self, fresh_db, admin_user):
        auth = make_auth(fresh_db)
        email, pw = admin_user
        auth.login(email, pw)
        uid1 = SessionManager.instance().current_user.id
        auth.logout()
        auth.login(email, pw)
        uid2 = SessionManager.instance().current_user.id
        assert uid1 == uid2
        auth.logout()

    def test_multiple_logouts_safe(self, fresh_db):
        auth = make_auth(fresh_db)
        auth.logout()  # Không crash khi logout khi chưa login
        auth.logout()


# ══════════════════════════════════════════════════════════════════════════════
# TC-10: DB lỗi
# ══════════════════════════════════════════════════════════════════════════════

class TestDatabaseError:
    def test_db_error_returns_db_error_status(self, fresh_db):
        auth = make_auth(fresh_db)
        with patch("app.services.auth_service.db") as mock_db:
            mock_db.fetchone.side_effect = sqlite3.OperationalError("gone")
            r = auth.login("test@sp.local", "Pass@1Word")
        assert r.status == LoginResult.DB_ERROR
        assert not r.success
        assert not SessionManager.instance().is_logged_in

    def test_db_error_no_crash(self, fresh_db):
        auth = make_auth(fresh_db)
        with patch("app.services.auth_service.db") as mock_db:
            mock_db.fetchone.side_effect = RuntimeError("unexpected")
            r = auth.login("test@sp.local", "Pass@1Word")
        assert r.status == LoginResult.DB_ERROR


# ══════════════════════════════════════════════════════════════════════════════
# TC-11: SQL Injection
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLInjection:
    @pytest.mark.parametrize("payload", [
        "' OR '1'='1",
        "admin'--",
        "' OR 1=1--",
        "'; DROP TABLE users;--",
        "\" OR \"1\"=\"1",
        "1; SELECT * FROM users--",
        "' UNION SELECT * FROM users--",
    ])
    def test_injection_fails(self, fresh_db, payload):
        auth = make_auth(fresh_db)
        r = auth.login(payload, "anything@1")
        assert not r.success, f"Injection succeeded: {payload!r}"

    def test_users_table_intact_after_injections(self, fresh_db, admin_user):
        auth = make_auth(fresh_db)
        for payload in ["'; DROP TABLE users;--", "' OR '1'='1"]:
            auth.login(payload, "x")
        # Bảng users vẫn tồn tại
        count = fresh_db.fetchone("SELECT COUNT(*) as c FROM users")["c"]
        assert count > 0


# ══════════════════════════════════════════════════════════════════════════════
# Timing: verify chạy đầy đủ kể cả khi email không tồn tại
# ══════════════════════════════════════════════════════════════════════════════

class TestTimingConsistency:
    def test_nonexistent_email_timing(self, fresh_db, admin_user):
        """
        Đảm bảo login với email không tồn tại CŨNG chạy PBKDF2
        (dummy hash) — không return sớm.
        Thời gian phải >= 50ms (PBKDF2 600k).
        """
        auth = make_auth(fresh_db)
        email, _ = admin_user

        t0 = time.perf_counter()
        auth.login("ghost@sp.local", "AnyPass@1")
        t_miss = time.perf_counter() - t0

        # PBKDF2 600k phải mất > 50ms trên mọi máy hợp lý
        assert t_miss > 0.05, (
            f"Login với email không tồn tại quá nhanh ({t_miss*1000:.0f}ms) "
            "— có thể bỏ qua PBKDF2 dummy hash"
        )

    def test_wrong_password_timing(self, fresh_db, admin_user):
        """Sai mật khẩu phải chạy PBKDF2 đầy đủ."""
        auth = make_auth(fresh_db)
        email, _ = admin_user
        t0 = time.perf_counter()
        auth.login(email, "WrongPass@99")
        elapsed = time.perf_counter() - t0
        assert elapsed > 0.05


# ══════════════════════════════════════════════════════════════════════════════
# Lazy rehash
# ══════════════════════════════════════════════════════════════════════════════

class TestLazyRehash:
    def test_legacy_hash_gets_upgraded_on_login(self, fresh_db):
        """
        User với legacy SHA-256 hash: sau khi login thành công,
        DB phải lưu hash PBKDF2 mới.
        """
        legacy_hash = "67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,'admin',1)",
            ("legacy_admin", "legacy@sp.local", legacy_hash, "Legacy Admin"),
        )
        fresh_db.get_connection().execute(
            "INSERT OR REPLACE INTO app_settings(key,value) VALUES('setup_done','1')"
        )
        fresh_db.get_connection().commit()

        SessionManager._instance = None
        auth = AuthService()
        r = auth.login("legacy@sp.local", "admin")
        assert r.success, f"Legacy login failed: {r.status}"

        # Kiểm tra hash đã được upgrade
        row = fresh_db.fetchone(
            "SELECT password FROM users WHERE email='legacy@sp.local'"
        )
        assert row["password"].startswith("pbkdf2:"), (
            "Hash phải được upgrade lên PBKDF2 sau login thành công"
        )
        assert needs_rehash(row["password"]) is False

        # Verify lại sau rehash
        assert verify_password("admin", row["password"])
        auth.logout()

    def test_new_hash_not_rehashed(self, fresh_db, admin_user):
        """User đã có PBKDF2 hash: sau login, hash không thay đổi."""
        email, pw = admin_user
        row_before = fresh_db.fetchone(
            "SELECT password FROM users WHERE email=?", (email,)
        )
        SessionManager._instance = None
        auth = AuthService()
        auth.login(email, pw)
        row_after = fresh_db.fetchone(
            "SELECT password FROM users WHERE email=?", (email,)
        )
        # Hash không thay đổi (không cần rehash)
        assert row_before["password"] == row_after["password"]
        auth.logout()
