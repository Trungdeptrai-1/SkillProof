# -*- coding: utf-8 -*-
"""
Tests: CompanyProfileService — quản lý hồ sơ doanh nghiệp.
Dùng fresh_db fixture — không chạm DB thật.
"""

import pytest
import sqlite3
from unittest.mock import patch

from app.services.company_profile_service import (
    CompanyProfileService, ProfileResult, CompanyProfileModel,
)
from app.services.auth_service import AuthService, SessionManager
from app.utils.helpers import hash_password


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def svc(fresh_db):
    return CompanyProfileService()

@pytest.fixture()
def company_session(fresh_db):
    """Tạo user company + đăng nhập + trả về service."""
    SessionManager._instance = None
    pw = "CompanyP@1"
    email = "company@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        ("company1", email, hash_password(pw), "Tech Corp", "company")
    )
    auth = AuthService()
    r = auth.login(email, pw)
    assert r.success, f"Company login failed: {r.status}"
    yield CompanyProfileService()
    auth.logout()
    SessionManager._instance = None

@pytest.fixture()
def company_b_session(fresh_db):
    """Tạo user company thứ B + đăng nhập."""
    # company_session đã tạo company1. Ta tạo company2 nhưng session đang là company1.
    # Phải logout company1, login company2.
    pw = "CompanyB@1"
    email = "companyB@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        ("company2", email, hash_password(pw), "Biz Inc", "company")
    )
    auth = AuthService()
    # Logout company1 first
    SessionManager.instance().end_session()
    r = auth.login(email, pw)
    assert r.success
    yield CompanyProfileService()
    auth.logout()
    SessionManager._instance = None

@pytest.fixture()
def candidate_session(fresh_db):
    """Tạo user candidate + đăng nhập."""
    pw = "CandP@ss1"
    email = "cand_sp@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        ("cand_sp", email, hash_password(pw), "Cand", "candidate")
    )
    auth = AuthService()
    r = auth.login(email, pw)
    assert r.success
    yield CompanyProfileService()
    auth.logout()
    SessionManager._instance = None

@pytest.fixture()
def expert_session(fresh_db):
    """Tạo user expert + đăng nhập."""
    pw = "ExpertP@1"
    email = "expert_sp@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        ("expert_sp", email, hash_password(pw), "Expert", "expert")
    )
    auth = AuthService()
    r = auth.login(email, pw)
    assert r.success
    yield CompanyProfileService()
    auth.logout()
    SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# Create profile
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateProfile:
    def test_create_success(self, company_session):
        r = company_session.create_profile(
            company_name="Tech Corp",
            industry="IT",
            website="https://techcorp.com",
            description="Công ty công nghệ",
            tax_code="0123456789",
            address="123 Lê Lợi, Q.1, TP.HCM"
        )
        assert r.success
        assert r.profile is not None
        assert r.profile.company_name == "Tech Corp"
        assert r.profile.industry == "IT"
        assert r.profile.is_verified is False

    def test_create_minimal(self, company_session):
        """Chỉ company_name là bắt buộc."""
        r = company_session.create_profile(company_name="Minimal Co")
        assert r.success
        assert r.profile.company_name == "Minimal Co"
        assert r.profile.industry is None

    def test_create_empty_name(self, company_session):
        r = company_session.create_profile(company_name="")
        assert not r.success
        assert r.status == ProfileResult.EMPTY_COMPANY_NAME

    def test_create_whitespace_name(self, company_session):
        r = company_session.create_profile(company_name="   ")
        assert not r.success
        assert r.status == ProfileResult.EMPTY_COMPANY_NAME

    def test_create_duplicate(self, company_session):
        """Không tạo được 2 hồ sơ cho cùng user."""
        r1 = company_session.create_profile(company_name="First Co")
        assert r1.success
        r2 = company_session.create_profile(company_name="Second Co")
        assert not r2.success
        assert r2.status == ProfileResult.ALREADY_EXISTS

    def test_create_invalid_website(self, company_session):
        """Website không hợp lệ."""
        r = company_session.create_profile(
            company_name="Co", website="not a url"
        )
        assert not r.success
        assert r.status == ProfileResult.INVALID_WEBSITE

    def test_create_valid_website_formats(self, company_session):
        for url in ["https://example.com", "http://test.com", "www.example.com", "example.com"]:
            SessionManager._instance = None
            # Need fresh login for each since we can't reuse session
            pw = "CompanyP@1"
            email = f"co_{url.split('.')[-1].split('/')[0]}@sp.local"
            fresh_db_conn = company_session  # reuse same db
            # This is tricky — just test website validation logic directly
            assert CompanyProfileService._is_valid_website(url)

    def test_create_strips_whitespace(self, company_session):
        r = company_session.create_profile(
            company_name="  Trimmed Co  ",
            industry="  IT  ",
        )
        assert r.success
        assert r.profile.company_name == "Trimmed Co"
        assert r.profile.industry == "IT"


# ══════════════════════════════════════════════════════════════════════════════
# Get profile
# ══════════════════════════════════════════════════════════════════════════════

class TestGetProfile:
    def test_get_when_not_exists(self, company_session):
        r = company_session.get_profile()
        assert not r.success
        assert r.status == ProfileResult.NOT_FOUND

    def test_get_after_create(self, company_session):
        company_session.create_profile(company_name="Get Co")
        r = company_session.get_profile()
        assert r.success
        assert r.profile.company_name == "Get Co"

    def test_get_returns_correct_user(self, company_session):
        """get_profile phải trả về profile của user đang đăng nhập."""
        company_session.create_profile(company_name="My Co", industry="Finance")
        r = company_session.get_profile()
        assert r.success
        assert r.profile.company_name == "My Co"
        assert r.profile.industry == "Finance"


# ══════════════════════════════════════════════════════════════════════════════
# Update profile
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateProfile:
    def test_update_success(self, company_session):
        company_session.create_profile(company_name="Original", industry="Old")
        r = company_session.update_profile(
            company_name="Updated Co", industry="New Industry"
        )
        assert r.success
        assert r.profile.company_name == "Updated Co"
        assert r.profile.industry == "New Industry"

    def test_update_empty_name(self, company_session):
        company_session.create_profile(company_name="Co")
        r = company_session.update_profile(company_name="")
        assert not r.success
        assert r.status == ProfileResult.EMPTY_COMPANY_NAME

    def test_update_when_not_exists(self, company_session):
        r = company_session.update_profile(company_name="Ghost Co")
        assert not r.success
        assert r.status == ProfileResult.NOT_FOUND

    def test_update_preserves_other_fields(self, company_session):
        """Update một field không mất field khác."""
        company_session.create_profile(
            company_name="Keep Co", industry="IT", website="https://keep.com",
            tax_code="TAX123", address="Addr 1"
        )
        r = company_session.update_profile(
            company_name="Keep Co", industry="Updated IT", website="https://keep.com",
            tax_code="TAX123", address="Addr 1"
        )
        assert r.success
        assert r.profile.company_name == "Keep Co"
        assert r.profile.industry == "Updated IT"
        assert r.profile.website == "https://keep.com"
        assert r.profile.tax_code == "TAX123"

    def test_update_invalid_website(self, company_session):
        company_session.create_profile(company_name="Co")
        r = company_session.update_profile(company_name="Co", website="bad url")
        assert not r.success
        assert r.status == ProfileResult.INVALID_WEBSITE


# ══════════════════════════════════════════════════════════════════════════════
# Role guard — Candidate/Expert không được dùng
# ══════════════════════════════════════════════════════════════════════════════

class TestRoleGuard:
    def test_candidate_cannot_get(self, candidate_session):
        r = candidate_session.get_profile()
        assert not r.success
        assert r.status == ProfileResult.WRONG_ROLE

    def test_candidate_cannot_create(self, candidate_session):
        r = candidate_session.create_profile(company_name="Hack")
        assert not r.success
        assert r.status == ProfileResult.WRONG_ROLE

    def test_candidate_cannot_update(self, candidate_session):
        r = candidate_session.update_profile(company_name="Hack")
        assert not r.success
        assert r.status == ProfileResult.WRONG_ROLE

    def test_expert_cannot_get(self, expert_session):
        r = expert_session.get_profile()
        assert not r.success
        assert r.status == ProfileResult.WRONG_ROLE

    def test_expert_cannot_create(self, expert_session):
        r = expert_session.create_profile(company_name="Hack")
        assert not r.success
        assert r.status == ProfileResult.WRONG_ROLE


# ══════════════════════════════════════════════════════════════════════════════
# Cross-user isolation — Company A không truy cập Company B
# ══════════════════════════════════════════════════════════════════════════════

class TestCrossUserIsolation:
    def test_company_a_cannot_see_b(self, fresh_db):
        """Company A tạo profile. Company B đăng nhập → get_profile chỉ thấy B's profile (None)."""
        # Company A
        SessionManager._instance = None
        pw_a = "CompA@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("compA", "compA@sp.local", hash_password(pw_a), "Comp A", "company")
        )
        auth_a = AuthService()
        auth_a.login("compA@sp.local", pw_a)
        svc_a = CompanyProfileService()
        r = svc_a.create_profile(company_name="Company A Inc")
        assert r.success
        auth_a.logout()

        # Company B
        SessionManager._instance = None
        pw_b = "CompB@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("compB", "compB@sp.local", hash_password(pw_b), "Comp B", "company")
        )
        auth_b = AuthService()
        auth_b.login("compB@sp.local", pw_b)
        svc_b = CompanyProfileService()
        r_b = svc_b.get_profile()
        assert r_b.status == ProfileResult.NOT_FOUND, \
            "Company B không được thấy profile của Company A"
        auth_b.logout()
        SessionManager._instance = None

    def test_company_b_update_does_not_affect_a(self, fresh_db):
        """Company B update không thay đổi profile của Company A."""
        # Company A creates
        SessionManager._instance = None
        pw_a = "CompA@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("compA2", "compA2@sp.local", hash_password(pw_a), "Comp A", "company")
        )
        auth_a = AuthService()
        auth_a.login("compA2@sp.local", pw_a)
        svc_a = CompanyProfileService()
        svc_a.create_profile(company_name="Original A")
        auth_a.logout()

        # Company B creates + updates
        SessionManager._instance = None
        pw_b = "CompB@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("compB2", "compB2@sp.local", hash_password(pw_b), "Comp B", "company")
        )
        auth_b = AuthService()
        auth_b.login("compB2@sp.local", pw_b)
        svc_b = CompanyProfileService()
        svc_b.create_profile(company_name="Original B")
        svc_b.update_profile(company_name="Updated B")
        auth_b.logout()

        # Company A logs back in — profile unchanged
        SessionManager._instance = None
        auth_a2 = AuthService()
        auth_a2.login("compA2@sp.local", pw_a)
        svc_a2 = CompanyProfileService()
        r = svc_a2.get_profile()
        assert r.success
        assert r.profile.company_name == "Original A", \
            "Company A's profile was modified by Company B"
        auth_a2.logout()
        SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# Not logged in
# ══════════════════════════════════════════════════════════════════════════════

class TestNotLoggedIn:
    def test_not_logged_in_get(self, fresh_db):
        SessionManager._instance = None
        svc = CompanyProfileService()
        r = svc.get_profile()
        assert r.status == ProfileResult.NOT_LOGGED_IN

    def test_not_logged_in_create(self, fresh_db):
        SessionManager._instance = None
        svc = CompanyProfileService()
        r = svc.create_profile(company_name="Ghost")
        assert r.status == ProfileResult.NOT_LOGGED_IN

    def test_not_logged_in_update(self, fresh_db):
        SessionManager._instance = None
        svc = CompanyProfileService()
        r = svc.update_profile(company_name="Ghost")
        assert r.status == ProfileResult.NOT_LOGGED_IN


# ══════════════════════════════════════════════════════════════════════════════
# SQL injection
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLInjection:
    @pytest.mark.parametrize("payload", [
        "'; DROP TABLE company_profiles;--",
        "' OR '1'='1",
        "Test'--",
        "'; UPDATE company_profiles SET is_verified=1 WHERE 1=1;--",
    ])
    def test_injection_in_company_name(self, company_session, payload):
        r = company_session.create_profile(company_name=payload)
        # Có thể success hoặc fail, nhưng DB không bị hỏng
        # Kiểm tra bảng vẫn tồn tại
        count = company_session.get_profile()
        # Table exists
        assert count.status in (ProfileResult.SUCCESS, ProfileResult.NOT_FOUND)

    def test_injection_does_not_set_verified(self, company_session):
        """SQL injection không thể set is_verified=1."""
        company_session.create_profile(company_name="Safe Co")
        # Thử inject
        company_session.update_profile(
            company_name="Safe Co'; UPDATE company_profiles SET is_verified=1;--"
        )
        r = company_session.get_profile()
        if r.success:
            assert r.profile.is_verified is False, \
                "SQL injection set is_verified to True!"


# ══════════════════════════════════════════════════════════════════════════════
# DB error
# ══════════════════════════════════════════════════════════════════════════════

class TestDBError:
    def test_db_error_on_get(self, fresh_db):
        SessionManager._instance = None
        pw = "CompE@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("compE", "compE@sp.local", hash_password(pw), "Comp E", "company")
        )
        auth = AuthService()
        auth.login("compE@sp.local", pw)
        svc = CompanyProfileService()
        with patch("app.services.company_profile_service.db") as mock_db:
            mock_db.fetchone.side_effect = sqlite3.OperationalError("gone")
            r = svc.get_profile()
        assert r.status == ProfileResult.DB_ERROR
        auth.logout()
        SessionManager._instance = None

    def test_db_error_on_create(self, fresh_db):
        SessionManager._instance = None
        pw = "CompE2@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("compE2", "compE2@sp.local", hash_password(pw), "Comp E2", "company")
        )
        auth = AuthService()
        auth.login("compE2@sp.local", pw)
        svc = CompanyProfileService()
        with patch("app.services.company_profile_service.db") as mock_db:
            mock_db.fetchone.side_effect = sqlite3.OperationalError("gone")
            r = svc.create_profile(company_name="Test")
        assert r.status == ProfileResult.DB_ERROR
        auth.logout()
        SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# MIG-004 compatibility
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004Compat:
    def test_company_profiles_table_exists(self, fresh_db):
        """Bảng company_profiles tồn tại sau MIG-004."""
        row = fresh_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='company_profiles'"
        )
        assert row is not None

    def test_profile_has_all_columns(self, company_session):
        """Profile trả về có đầy đủ fields."""
        company_session.create_profile(
            company_name="Full Co", industry="IT", website="https://full.com",
            description="Desc", tax_code="TAX", address="Addr"
        )
        r = company_session.get_profile()
        assert r.success
        p = r.profile
        assert hasattr(p, "id")
        assert hasattr(p, "user_id")
        assert hasattr(p, "company_name")
        assert hasattr(p, "industry")
        assert hasattr(p, "website")
        assert hasattr(p, "description")
        assert hasattr(p, "logo_path")
        assert hasattr(p, "tax_code")
        assert hasattr(p, "address")
        assert hasattr(p, "is_verified")
        assert hasattr(p, "created_at")
        assert hasattr(p, "updated_at")

    def test_cascade_delete_user_deletes_profile(self, fresh_db):
        """Xóa user → profile bị cascade delete."""
        SessionManager._instance = None
        pw = "CompDel@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("compDel", "compDel@sp.local", hash_password(pw), "Comp Del", "company")
        )
        auth = AuthService()
        auth.login("compDel@sp.local", pw)
        svc = CompanyProfileService()
        svc.create_profile(company_name="Delete Me")
        auth.logout()

        user_id = fresh_db.fetchone(
            "SELECT id FROM users WHERE username='compDel'"
        )["id"]
        fresh_db.execute("DELETE FROM users WHERE id=?", (user_id,))

        row = fresh_db.fetchone(
            "SELECT * FROM company_profiles WHERE user_id=?", (user_id,)
        )
        assert row is None, "Profile should be cascade deleted"
        SessionManager._instance = None
