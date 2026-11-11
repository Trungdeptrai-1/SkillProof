# -*- coding: utf-8 -*-
"""
Tests: CandidateProfileService — quản lý hồ sơ ứng viên.
Dùng fresh_db fixture — không chạm DB thật.
"""

import pytest
import sqlite3
import os
import tempfile
from unittest.mock import patch

from app.services.candidate_profile_service import (
    CandidateProfileService, CandidateProfileResult, CandidateProfileModel,
    MAX_CV_SIZE,
)
from app.services.auth_service import AuthService, SessionManager
from app.utils.helpers import hash_password


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def candidate_session(fresh_db):
    """Tạo user candidate + đăng nhập + trả về service."""
    SessionManager._instance = None
    pw = "CandP@ss1"
    email = "cand_test@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        ("cand_test", email, hash_password(pw), "Nguyễn Văn Test", "candidate")
    )
    auth = AuthService()
    r = auth.login(email, pw)
    assert r.success, f"Candidate login failed: {r.status}"
    yield CandidateProfileService()
    auth.logout()
    SessionManager._instance = None

@pytest.fixture()
def company_session(fresh_db):
    SessionManager._instance = None
    pw = "CompP@ss1"
    email = "comp_test@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        ("comp_test", email, hash_password(pw), "Comp Test", "company")
    )
    auth = AuthService()
    auth.login(email, pw)
    yield CandidateProfileService()
    auth.logout()
    SessionManager._instance = None

@pytest.fixture()
def expert_session(fresh_db):
    SessionManager._instance = None
    pw = "ExpP@ss1"
    email = "exp_test@sp.local"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        ("exp_test", email, hash_password(pw), "Exp Test", "expert")
    )
    auth = AuthService()
    auth.login(email, pw)
    yield CandidateProfileService()
    auth.logout()
    SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# Create profile
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateProfile:
    def test_create_success(self, candidate_session):
        r = candidate_session.create_profile(
            headline="Python Developer",
            bio="3 năm kinh nghiệm",
            portfolio_url="https://github.com/test",
            years_experience=3,
        )
        assert r.success
        assert r.profile is not None
        assert r.profile.headline == "Python Developer"
        assert r.profile.years_experience == 3
        assert r.profile.full_name == "Nguyễn Văn Test"
        assert r.profile.email == "cand_test@sp.local"

    def test_create_minimal_empty(self, candidate_session):
        """Tất cả trường optional — tạo được với data trống."""
        r = candidate_session.create_profile()
        assert r.success
        assert r.profile.headline is None

    def test_create_unicode(self, candidate_session):
        """Tiếng Việt Unicode."""
        r = candidate_session.create_profile(
            headline="Lập trình viên Python",
            bio="Tôi là lập trình viên với 5 năm kinh nghiệm trong lĩnh vực AI",
        )
        assert r.success
        assert "Python" in r.profile.headline
        assert "AI" in r.profile.bio

    def test_create_duplicate(self, candidate_session):
        r1 = candidate_session.create_profile(headline="First")
        assert r1.success
        r2 = candidate_session.create_profile(headline="Second")
        assert not r2.success
        assert r2.status == CandidateProfileResult.ALREADY_EXISTS

    def test_create_invalid_portfolio(self, candidate_session):
        r = candidate_session.create_profile(
            headline="Dev", portfolio_url="not a url"
        )
        assert not r.success
        assert r.status == CandidateProfileResult.INVALID_PORTFOLIO

    def test_create_negative_years(self, candidate_session):
        r = candidate_session.create_profile(
            headline="Dev", years_experience=-1
        )
        assert not r.success
        assert r.status == CandidateProfileResult.INVALID_YEARS

    def test_create_strips_whitespace(self, candidate_session):
        r = candidate_session.create_profile(
            headline="  Trimmed Headline  ",
            bio="  Trimmed bio  ",
        )
        assert r.success
        assert r.profile.headline == "Trimmed Headline"
        assert r.profile.bio == "Trimmed bio"


# ══════════════════════════════════════════════════════════════════════════════
# Get profile
# ══════════════════════════════════════════════════════════════════════════════

class TestGetProfile:
    def test_get_when_not_exists(self, candidate_session):
        r = candidate_session.get_profile()
        assert not r.success
        assert r.status == CandidateProfileResult.NOT_FOUND

    def test_get_after_create(self, candidate_session):
        candidate_session.create_profile(headline="Test", bio="Bio")
        r = candidate_session.get_profile()
        assert r.success
        assert r.profile.headline == "Test"
        assert r.profile.bio == "Bio"

    def test_get_includes_user_info(self, candidate_session):
        """get_profile trả về full_name và email từ bảng users."""
        candidate_session.create_profile(headline="Dev")
        r = candidate_session.get_profile()
        assert r.success
        assert r.profile.full_name == "Nguyễn Văn Test"
        assert r.profile.email == "cand_test@sp.local"


# ══════════════════════════════════════════════════════════════════════════════
# Update profile
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateProfile:
    def test_update_success(self, candidate_session):
        candidate_session.create_profile(headline="Junior Dev", bio="New grad")
        r = candidate_session.update_profile(
            headline="Senior Dev", bio="5 years exp", years_experience=5
        )
        assert r.success
        assert r.profile.headline == "Senior Dev"
        assert r.profile.bio == "5 years exp"
        assert r.profile.years_experience == 5

    def test_update_when_not_exists(self, candidate_session):
        r = candidate_session.update_profile(headline="Ghost")
        assert not r.success
        assert r.status == CandidateProfileResult.NOT_FOUND

    def test_update_preserves_other_fields(self, candidate_session):
        candidate_session.create_profile(
            headline="Dev", bio="Bio", portfolio_url="https://x.com",
            years_experience=2
        )
        r = candidate_session.update_profile(
            headline="Senior Dev", bio="Bio", portfolio_url="https://x.com",
            years_experience=2
        )
        assert r.success
        assert r.profile.headline == "Senior Dev"
        assert r.profile.bio == "Bio"
        assert r.profile.portfolio_url == "https://x.com"
        assert r.profile.years_experience == 2

    def test_update_invalid_portfolio(self, candidate_session):
        candidate_session.create_profile(headline="Dev")
        r = candidate_session.update_profile(headline="Dev", portfolio_url="bad url")
        assert not r.success
        assert r.status == CandidateProfileResult.INVALID_PORTFOLIO

    def test_update_does_not_change_email(self, candidate_session):
        """Email phải không thay đổi sau update."""
        candidate_session.create_profile(headline="Dev")
        candidate_session.update_profile(headline="Updated Dev")
        r = candidate_session.get_profile()
        assert r.success
        assert r.profile.email == "cand_test@sp.local"

    def test_update_does_not_change_full_name(self, candidate_session):
        candidate_session.create_profile(headline="Dev")
        candidate_session.update_profile(headline="Updated", bio="New bio")
        r = candidate_session.get_profile()
        assert r.success
        assert r.profile.full_name == "Nguyễn Văn Test"


# ══════════════════════════════════════════════════════════════════════════════
# Role guard
# ══════════════════════════════════════════════════════════════════════════════

class TestRoleGuard:
    def test_company_cannot_get(self, company_session):
        r = company_session.get_profile()
        assert not r.success
        assert r.status == CandidateProfileResult.WRONG_ROLE

    def test_company_cannot_create(self, company_session):
        r = company_session.create_profile(headline="Hack")
        assert not r.success
        assert r.status == CandidateProfileResult.WRONG_ROLE

    def test_company_cannot_update(self, company_session):
        r = company_session.update_profile(headline="Hack")
        assert not r.success
        assert r.status == CandidateProfileResult.WRONG_ROLE

    def test_expert_cannot_get(self, expert_session):
        r = expert_session.get_profile()
        assert not r.success
        assert r.status == CandidateProfileResult.WRONG_ROLE

    def test_expert_cannot_create(self, expert_session):
        r = expert_session.create_profile(headline="Hack")
        assert not r.success
        assert r.status == CandidateProfileResult.WRONG_ROLE


# ══════════════════════════════════════════════════════════════════════════════
# Cross-user isolation
# ══════════════════════════════════════════════════════════════════════════════

class TestCrossUserIsolation:
    def test_candidate_a_cannot_see_b(self, fresh_db):
        """Candidate A tạo profile. Candidate B get → NOT_FOUND."""
        # Candidate A
        SessionManager._instance = None
        pw_a = "CandA@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("candA", "candA@sp.local", hash_password(pw_a), "Cand A", "candidate")
        )
        auth_a = AuthService()
        auth_a.login("candA@sp.local", pw_a)
        svc_a = CandidateProfileService()
        svc_a.create_profile(headline="A's headline")
        auth_a.logout()

        # Candidate B
        SessionManager._instance = None
        pw_b = "CandB@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("candB", "candB@sp.local", hash_password(pw_b), "Cand B", "candidate")
        )
        auth_b = AuthService()
        auth_b.login("candB@sp.local", pw_b)
        svc_b = CandidateProfileService()
        r = svc_b.get_profile()
        assert r.status == CandidateProfileResult.NOT_FOUND
        auth_b.logout()
        SessionManager._instance = None

    def test_candidate_b_update_does_not_affect_a(self, fresh_db):
        SessionManager._instance = None
        pw_a = "CandA2@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("candA2", "candA2@sp.local", hash_password(pw_a), "A", "candidate")
        )
        auth_a = AuthService()
        auth_a.login("candA2@sp.local", pw_a)
        svc_a = CandidateProfileService()
        svc_a.create_profile(headline="Original A", bio="A's bio")
        auth_a.logout()

        SessionManager._instance = None
        pw_b = "CandB2@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("candB2", "candB2@sp.local", hash_password(pw_b), "B", "candidate")
        )
        auth_b = AuthService()
        auth_b.login("candB2@sp.local", pw_b)
        svc_b = CandidateProfileService()
        svc_b.create_profile(headline="Original B")
        svc_b.update_profile(headline="Updated B")
        auth_b.logout()

        SessionManager._instance = None
        auth_a2 = AuthService()
        auth_a2.login("candA2@sp.local", pw_a)
        svc_a2 = CandidateProfileService()
        r = svc_a2.get_profile()
        assert r.success
        assert r.profile.headline == "Original A"
        auth_a2.logout()
        SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# Not logged in
# ══════════════════════════════════════════════════════════════════════════════

class TestNotLoggedIn:
    def test_not_logged_get(self, fresh_db):
        SessionManager._instance = None
        svc = CandidateProfileService()
        r = svc.get_profile()
        assert r.status == CandidateProfileResult.NOT_LOGGED_IN

    def test_not_logged_create(self, fresh_db):
        SessionManager._instance = None
        svc = CandidateProfileService()
        r = svc.create_profile(headline="Ghost")
        assert r.status == CandidateProfileResult.NOT_LOGGED_IN

    def test_not_logged_update(self, fresh_db):
        SessionManager._instance = None
        svc = CandidateProfileService()
        r = svc.update_profile(headline="Ghost")
        assert r.status == CandidateProfileResult.NOT_LOGGED_IN


# ══════════════════════════════════════════════════════════════════════════════
# SQL injection
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLInjection:
    @pytest.mark.parametrize("payload", [
        "'; DROP TABLE candidate_profiles;--",
        "' OR '1'='1",
        "Test'--",
        "'; UPDATE users SET role='admin' WHERE 1=1;--",
    ])
    def test_injection_in_headline(self, candidate_session, payload):
        r = candidate_session.create_profile(headline=payload)
        # DB table still exists
        count = candidate_session.get_profile()
        assert count.status in (CandidateProfileResult.SUCCESS, CandidateProfileResult.NOT_FOUND)

    def test_injection_does_not_change_role(self, candidate_session):
        """SQL injection trong headline không thể thay đổi role."""
        candidate_session.create_profile(
            headline="Safe'; UPDATE users SET role='admin' WHERE 1=1;--"
        )
        # Verify role not changed
        row = candidate_session.get_profile()
        if row.success:
            # Check actual user role
            from app.database.connection import db
            user_row = db.fetchone("SELECT role FROM users WHERE id=?", (row.profile.user_id,))
            assert user_row["role"] == "candidate"


# ══════════════════════════════════════════════════════════════════════════════
# CV management
# ══════════════════════════════════════════════════════════════════════════════

class TestCVManagement:
    def _make_test_pdf(self, tmp_path, size_kb=1):
        """Tạo file PDF giả (nội dung bất kỳ với magic bytes PDF)."""
        path = str(tmp_path / f"test_cv_{size_kb}kb.pdf")
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4\n")  # PDF header
            f.write(b"x" * (size_kb * 1024 - 10))  # Padding
        return path

    def test_save_cv_success(self, candidate_session, tmp_path):
        candidate_session.create_profile(headline="Dev")
        pdf_path = self._make_test_pdf(tmp_path, size_kb=5)
        r = candidate_session.save_cv(pdf_path)
        assert r.success
        assert r.profile.resume_path is not None

    def test_save_cv_creates_profile_dir(self, candidate_session, tmp_path):
        candidate_session.create_profile(headline="Dev")
        pdf_path = self._make_test_pdf(tmp_path)
        candidate_session.save_cv(pdf_path)
        # CV directory should exist
        from app.utils import constants as consts
        cv_dir = os.path.join(consts.DATA_DIR, "cvs")
        assert os.path.isdir(cv_dir)

    def test_save_cv_rejects_non_pdf(self, candidate_session, tmp_path):
        candidate_session.create_profile(headline="Dev")
        txt_path = str(tmp_path / "cv.txt")
        with open(txt_path, "w") as f:
            f.write("Not a PDF")
        r = candidate_session.save_cv(txt_path)
        assert not r.success
        assert r.status == CandidateProfileResult.CV_INVALID_FORMAT

    def test_save_cv_rejects_too_large(self, candidate_session, tmp_path):
        candidate_session.create_profile(headline="Dev")
        # Create file slightly over MAX_CV_SIZE (but we'll mock getsize to avoid disk)
        large_path = str(tmp_path / "large.pdf")
        with open(large_path, "wb") as f:
            f.write(b"%PDF-1.4\n")
            f.write(b"\x00" * 100)
        with patch("app.services.candidate_profile_service.os.path.getsize", return_value=MAX_CV_SIZE + 1):
            r = candidate_session.save_cv(large_path)
        assert not r.success
        assert r.status == CandidateProfileResult.CV_TOO_LARGE

    def test_save_cv_rejects_empty_file(self, candidate_session, tmp_path):
        candidate_session.create_profile(headline="Dev")
        empty_path = str(tmp_path / "empty.pdf")
        with open(empty_path, "wb") as f:
            pass  # 0 bytes
        r = candidate_session.save_cv(empty_path)
        assert not r.success
        assert r.status == CandidateProfileResult.CV_INVALID_FORMAT

    def test_save_cv_replaces_old(self, candidate_session, tmp_path):
        """Lưu CV mới → CV cũ bị xóa."""
        candidate_session.create_profile(headline="Dev")
        old_pdf = self._make_test_pdf(tmp_path, size_kb=2)
        candidate_session.save_cv(old_pdf)
        old_cv_path = candidate_session.get_cv_path()
        assert old_cv_path is not None
        assert os.path.exists(old_cv_path)

        new_pdf = self._make_test_pdf(tmp_path, size_kb=3)
        r = candidate_session.save_cv(new_pdf)
        assert r.success
        new_cv_path = candidate_session.get_cv_path()
        assert new_cv_path is not None
        # Old file should be deleted
        if old_cv_path != new_cv_path:
            assert not os.path.exists(old_cv_path), "Old CV should be deleted"

    def test_get_cv_path_none_when_no_cv(self, candidate_session):
        candidate_session.create_profile(headline="Dev")
        assert candidate_session.get_cv_path() is None

    def test_get_cv_path_after_save(self, candidate_session, tmp_path):
        candidate_session.create_profile(headline="Dev")
        pdf_path = self._make_test_pdf(tmp_path)
        candidate_session.save_cv(pdf_path)
        cv = candidate_session.get_cv_path()
        assert cv is not None
        assert os.path.exists(cv)
        assert cv.endswith(".pdf")

    def test_cv_requires_profile(self, candidate_session, tmp_path):
        """Không thể lưu CV khi chưa có profile."""
        pdf_path = self._make_test_pdf(tmp_path)
        r = candidate_session.save_cv(pdf_path)
        # save_cv tries UPDATE WHERE user_id → no rows updated → get_profile returns NOT_FOUND
        assert not r.success
        assert r.status in (CandidateProfileResult.NOT_FOUND, CandidateProfileResult.DB_ERROR)


# ══════════════════════════════════════════════════════════════════════════════
# DB error
# ══════════════════════════════════════════════════════════════════════════════

class TestDBError:
    def test_db_error_on_get(self, fresh_db):
        SessionManager._instance = None
        pw = "CandE@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("candE", "candE@sp.local", hash_password(pw), "Cand E", "candidate")
        )
        auth = AuthService()
        auth.login("candE@sp.local", pw)
        svc = CandidateProfileService()
        with patch("app.services.candidate_profile_service.db") as mock_db:
            mock_db.fetchone.side_effect = sqlite3.OperationalError("gone")
            r = svc.get_profile()
        assert r.status == CandidateProfileResult.DB_ERROR
        auth.logout()
        SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# MIG-004 compatibility
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004Compat:
    def test_candidate_profiles_table_exists(self, fresh_db):
        row = fresh_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='candidate_profiles'"
        )
        assert row is not None

    def test_profile_has_all_columns(self, candidate_session):
        candidate_session.create_profile(headline="Full")
        r = candidate_session.get_profile()
        assert r.success
        p = r.profile
        for field in ["id", "user_id", "headline", "bio", "resume_path",
                       "portfolio_url", "years_experience", "created_at",
                       "updated_at", "full_name", "email"]:
            assert hasattr(p, field), f"Missing field: {field}"

    def test_cascade_delete_user_deletes_profile(self, fresh_db):
        SessionManager._instance = None
        pw = "CandDel@ss1"
        fresh_db.execute(
            "INSERT INTO users(username,email,password,full_name,role,is_active)"
            " VALUES(?,?,?,?,?,1)",
            ("candDel", "candDel@sp.local", hash_password(pw), "Cand Del", "candidate")
        )
        auth = AuthService()
        auth.login("candDel@sp.local", pw)
        svc = CandidateProfileService()
        svc.create_profile(headline="Delete Me")
        auth.logout()

        user_id = fresh_db.fetchone(
            "SELECT id FROM users WHERE username='candDel'"
        )["id"]
        fresh_db.execute("DELETE FROM users WHERE id=?", (user_id,))

        row = fresh_db.fetchone(
            "SELECT * FROM candidate_profiles WHERE user_id=?", (user_id,)
        )
        assert row is None
        SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# Data integrity on failed update
# ══════════════════════════════════════════════════════════════════════════════

class TestDataIntegrity:
    def test_failed_update_preserves_data(self, candidate_session):
        """Update với portfolio_url sai → data cũ không mất."""
        candidate_session.create_profile(
            headline="Original", bio="Original bio",
            portfolio_url="https://valid.com", years_experience=3
        )
        # Try invalid update
        r = candidate_session.update_profile(
            headline="Should Not Save", portfolio_url="invalid url"
        )
        assert not r.success
        # Check original data preserved
        r2 = candidate_session.get_profile()
        assert r2.success
        assert r2.profile.headline == "Original"
        assert r2.profile.bio == "Original bio"
        assert r2.profile.portfolio_url == "https://valid.com"
        assert r2.profile.years_experience == 3
