# -*- coding: utf-8 -*-
"""
Tests: UserService.register() — đăng ký tài khoản ứng viên.
Dùng fresh_db fixture — không chạm DB thật.
"""

import pytest
from app.services.user_service import UserService, RegisterResult
from app.services.auth_service import AuthService, SessionManager
from app.utils.helpers import verify_password, is_valid_email
from app.models.user_model import UserModel


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def svc(fresh_db):
    """UserService với fresh DB."""
    return UserService()


@pytest.fixture()
def auth(fresh_db):
    """AuthService cho test đăng nhập sau đăng ký."""
    SessionManager._instance = None
    a = AuthService()
    yield a
    SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# Đăng ký hợp lệ
# ══════════════════════════════════════════════════════════════════════════════

class TestRegisterSuccess:
    def test_register_valid(self, svc, fresh_db):
        r = svc.register("Nguyen Van A", "nguyenvana@test.com", "PassWord1", "PassWord1")
        assert r.success
        assert r.status == RegisterResult.SUCCESS
        assert r.user is not None
        assert r.user.email == "nguyenvana@test.com"
        assert r.user.full_name == "Nguyen Van A"
        assert r.user.is_active is True

    def test_register_role_is_candidate(self, svc, fresh_db):
        """Role phải luôn là 'candidate' — không cho user chọn."""
        r = svc.register("Test User", "testuser@reg.com", "PassWord1", "PassWord1")
        assert r.success
        assert r.user.role == "candidate"

    def test_register_password_hashed(self, svc, fresh_db):
        """Password phải được hash bằng PBKDF2, không lưu plain text."""
        r = svc.register("Hash Test", "hashtest@reg.com", "SecretP@1", "SecretP@1")
        assert r.success
        # Lấy hash từ DB
        row = fresh_db.fetchone(
            "SELECT password FROM users WHERE email=?", ("hashtest@reg.com",)
        )
        assert row["password"].startswith("pbkdf2:")
        assert "SecretP@1" not in row["password"]
        # Verify password đúng
        assert verify_password("SecretP@1", row["password"])

    def test_register_can_login_after(self, svc, auth, fresh_db):
        """Sau đăng ký, user phải đăng nhập được ngay."""
        svc.register("Login Test", "logintest@reg.com", "PassWord1", "PassWord1")
        r = auth.login("logintest@reg.com", "PassWord1")
        assert r.success
        assert r.user.email == "logintest@reg.com"
        assert r.user.role == "candidate"
        auth.logout()

    def test_register_username_from_email(self, svc, fresh_db):
        """Username tự sinh từ phần trước @ của email."""
        r = svc.register("Name", "myname@test.com", "PassWord1", "PassWord1")
        assert r.success
        assert r.user.username == "myname"

    def test_register_multiple_users(self, svc, fresh_db):
        """Đăng ký nhiều user khác nhau."""
        for i in range(3):
            r = svc.register(f"User {i}", f"user{i}@reg.com", "PassWord1", "PassWord1")
            assert r.success
        count = fresh_db.fetchone("SELECT COUNT(*) as c FROM users WHERE role='candidate'")["c"]
        assert count == 3


# ══════════════════════════════════════════════════════════════════════════════
# Trường trống
# ══════════════════════════════════════════════════════════════════════════════

class TestEmptyFields:
    def test_empty_full_name(self, svc):
        r = svc.register("", "user@test.com", "PassWord1", "PassWord1")
        assert not r.success
        assert r.status == RegisterResult.EMPTY_FULL_NAME

    def test_whitespace_full_name(self, svc):
        r = svc.register("   ", "user@test.com", "PassWord1", "PassWord1")
        assert not r.success
        assert r.status == RegisterResult.EMPTY_FULL_NAME

    def test_empty_email(self, svc):
        r = svc.register("Test", "", "PassWord1", "PassWord1")
        assert not r.success
        assert r.status == RegisterResult.EMPTY_EMAIL

    def test_empty_password(self, svc):
        r = svc.register("Test", "user@test.com", "", "PassWord1")
        assert not r.success
        assert r.status == RegisterResult.EMPTY_PASSWORD

    def test_empty_confirm(self, svc):
        r = svc.register("Test", "user@test.com", "PassWord1", "")
        assert not r.success
        assert r.status == RegisterResult.EMPTY_CONFIRM


# ══════════════════════════════════════════════════════════════════════════════
# Email sai định dạng
# ══════════════════════════════════════════════════════════════════════════════

class TestInvalidEmail:
    @pytest.mark.parametrize("bad_email", [
        "notanemail",
        "missing@",
        "@nodomain.com",
        "a b@test.com",
        "user@",
        "double@@test.com",
    ])
    def test_invalid_email_format(self, svc, bad_email):
        r = svc.register("Test", bad_email, "PassWord1", "PassWord1")
        assert not r.success
        assert r.status == RegisterResult.INVALID_EMAIL_FORMAT


# ══════════════════════════════════════════════════════════════════════════════
# Mật khẩu yếu
# ══════════════════════════════════════════════════════════════════════════════

class TestWeakPassword:
    def test_short_password(self, svc):
        r = svc.register("Test", "user@test.com", "Ab1", "Ab1")
        assert not r.success
        assert r.status == RegisterResult.WEAK_PASSWORD

    def test_no_uppercase(self, svc):
        r = svc.register("Test", "user@test.com", "alllowercase1", "alllowercase1")
        assert not r.success
        assert r.status == RegisterResult.WEAK_PASSWORD

    def test_no_digit(self, svc):
        r = svc.register("Test", "user@test.com", "NoDigitHere", "NoDigitHere")
        assert not r.success
        assert r.status == RegisterResult.WEAK_PASSWORD

    def test_password_mismatch(self, svc):
        r = svc.register("Test", "user@test.com", "PassWord1", "DifferentP2")
        assert not r.success
        assert r.status == RegisterResult.PASSWORD_MISMATCH


# ══════════════════════════════════════════════════════════════════════════════
# Email trùng
# ══════════════════════════════════════════════════════════════════════════════

class TestDuplicateEmail:
    def test_email_already_used(self, svc, fresh_db):
        """Đăng ký lần 1 thành công, lần 2 cùng email phải fail."""
        r1 = svc.register("User A", "dup@test.com", "PassWord1", "PassWord1")
        assert r1.success

        r2 = svc.register("User B", "dup@test.com", "OtherPw1", "OtherPw1")
        assert not r2.success
        assert r2.status == RegisterResult.EMAIL_ALREADY_USED

    def test_email_case_variants_not_duplicate(self, svc, fresh_db):
        """SQLite mặc định case-sensitive cho TEXT — 'Test@x.com' ≠ 'test@x.com'."""
        # Ghi chú: đây là hành vi SQLite mặc định, không phải bug.
        r1 = svc.register("User A", "Test@x.com", "PassWord1", "PassWord1")
        assert r1.success
        r2 = svc.register("User B", "test@x.com", "PassWord1", "PassWord1")
        # SQLite UNIQUE is case-sensitive by default
        assert r2.success  # Different email in SQLite's view


# ══════════════════════════════════════════════════════════════════════════════
# Security checks
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurity:
    def test_no_plain_password_in_db(self, svc, fresh_db):
        """Hash trong DB không chứa plain password."""
        pw = "MySecretP@1"
        svc.register("Sec Test", "sectest@reg.com", pw, pw)
        row = fresh_db.fetchone(
            "SELECT password FROM users WHERE email=?", ("sectest@reg.com",)
        )
        assert pw not in row["password"]

    def test_sql_injection_in_email(self, svc, fresh_db):
        """Email chứa SQL injection payload không phá hỏng DB."""
        payloads = [
            "test@x.com'; DROP TABLE users;--",
            "' OR '1'='1@x.com",
            "test@x.com' UNION SELECT * FROM users--",
        ]
        for pl in payloads:
            # Có thể fail validation hoặc success (nếu email format hợp lệ)
            # Nhưng không được phá DB
            r = svc.register("Inject", pl, "PassWord1", "PassWord1")
            # DB phải còn nguyên vặn
            count = fresh_db.fetchone("SELECT COUNT(*) as c FROM users")["c"]
            assert count >= 0  # Table vẫn tồn tại

    def test_sql_injection_in_name(self, svc, fresh_db):
        """Full name chứa SQL payload — phải an toàn."""
        r = svc.register(
            "Test'; DROP TABLE users;--",
            "safename@reg.com", "PassWord1", "PassWord1"
        )
        assert r.success  # Parameterized query — an toàn
        # DB vẫn còn
        count = fresh_db.fetchone("SELECT COUNT(*) as c FROM users")["c"]
        assert count > 0

    def test_user_model_no_password_field(self, svc, fresh_db):
        """UserModel trả về từ register không có field password."""
        r = svc.register("Model Test", "modeltest@reg.com", "PassWord1", "PassWord1")
        assert r.success
        assert not hasattr(r.user, "password")


# ══════════════════════════════════════════════════════════════════════════════
# DB error
# ══════════════════════════════════════════════════════════════════════════════

class TestDatabaseError:
    def test_db_error_returns_db_error_status(self, fresh_db):
        svc = UserService()
        from unittest.mock import patch
        import sqlite3
        with patch("app.services.user_service.db") as mock_db:
            mock_db.fetchone.side_effect = sqlite3.OperationalError("gone")
            r = svc.register("Test", "test@x.com", "PassWord1", "PassWord1")
        assert not r.success
        assert r.status == RegisterResult.DB_ERROR


# ══════════════════════════════════════════════════════════════════════════════
# Integration: register → login flow
# ══════════════════════════════════════════════════════════════════════════════

class TestRegisterLoginFlow:
    def test_register_then_login(self, svc, auth, fresh_db):
        """Đăng ký → đăng nhập ngay với email + password vừa tạo."""
        r = svc.register("Flow Test", "flowtest@reg.com", "PassWord1", "PassWord1")
        assert r.success

        login = auth.login("flowtest@reg.com", "PassWord1")
        assert login.success
        assert login.user.role == "candidate"
        auth.logout()

    def test_register_then_wrong_password_login(self, svc, auth, fresh_db):
        """Đăng ký → đăng nhập sai mật khẩu phải fail."""
        svc.register("Wrong Pw", "wrongpw@reg.com", "PassWord1", "PassWord1")
        login = auth.login("wrongpw@reg.com", "WrongPass9")
        assert not login.success
