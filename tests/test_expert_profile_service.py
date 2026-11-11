# -*- coding: utf-8 -*-
"""
Tests: ExpertProfileService — quản lý hồ sơ chuyên gia.
Dùng fresh_db fixture — không chạm DB thật.
"""

import math
import pytest
import sqlite3
from unittest.mock import patch

from app.services.expert_profile_service import (
    ExpertProfileService, ExpertProfileResult, ExpertProfileModel,
    AVAILABILITY_VALUES, TITLE_MAX_LEN,
)
from app.services.auth_service import AuthService, SessionManager
from app.utils.helpers import hash_password


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _login_expert(fresh_db, uname="expert1", email="expert1@sp.local", pw="ExpertP@1"):
    fresh_db.execute(
        "INSERT OR IGNORE INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        (uname, email, hash_password(pw), f"Expert {uname}", "expert")
    )
    SessionManager._instance = None
    auth = AuthService()
    auth.login(email, pw)
    return ExpertProfileService(), auth


@pytest.fixture()
def expert_svc(fresh_db):
    svc, auth = _login_expert(fresh_db)
    yield svc
    auth.logout()
    SessionManager._instance = None


@pytest.fixture()
def candidate_svc(fresh_db):
    pw = "CandP@ss1"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        ("cand_e", "cand_e@sp.local", hash_password(pw), "Cand", "candidate")
    )
    SessionManager._instance = None
    auth = AuthService()
    auth.login("cand_e@sp.local", pw)
    yield ExpertProfileService()
    auth.logout()
    SessionManager._instance = None


@pytest.fixture()
def company_svc(fresh_db):
    pw = "CompP@ss1"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active)"
        " VALUES(?,?,?,?,?,1)",
        ("comp_e", "comp_e@sp.local", hash_password(pw), "Comp", "company")
    )
    SessionManager._instance = None
    auth = AuthService()
    auth.login("comp_e@sp.local", pw)
    yield ExpertProfileService()
    auth.logout()
    SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# 1–2. Create profile
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateProfile:
    def test_create_success(self, expert_svc):
        r = expert_svc.create_profile(
            title="Senior Python Dev",
            bio="10 năm kinh nghiệm",
            specialization="Backend, AI",
            hourly_rate=500_000,
            availability="available",
        )
        assert r.success
        assert r.profile.title == "Senior Python Dev"
        assert r.profile.bio == "10 năm kinh nghiệm"
        assert r.profile.specialization == "Backend, AI"
        assert r.profile.hourly_rate == 500_000
        assert r.profile.availability == "available"
        assert r.profile.is_verified is False

    def test_create_minimal(self, expert_svc):
        """Chỉ title là bắt buộc."""
        r = expert_svc.create_profile(title="Dev")
        assert r.success
        assert r.profile.title == "Dev"
        assert r.profile.bio is None
        assert r.profile.hourly_rate is None

    # 2. Missing title
    def test_create_empty_title(self, expert_svc):
        r = expert_svc.create_profile(title="")
        assert not r.success
        assert r.status == ExpertProfileResult.EMPTY_TITLE

    # 3. Title chỉ chứa khoảng trắng
    def test_create_whitespace_title(self, expert_svc):
        r = expert_svc.create_profile(title="   ")
        assert not r.success
        assert r.status == ExpertProfileResult.EMPTY_TITLE

    def test_create_title_too_long(self, expert_svc):
        r = expert_svc.create_profile(title="A" * (TITLE_MAX_LEN + 1))
        assert not r.success
        assert r.status == ExpertProfileResult.TITLE_TOO_LONG

    def test_create_title_exact_max(self, expert_svc):
        """Đúng TITLE_MAX_LEN ký tự — phải OK."""
        r = expert_svc.create_profile(title="A" * TITLE_MAX_LEN)
        assert r.success

    # 6. Không tạo trùng
    def test_create_duplicate(self, expert_svc):
        expert_svc.create_profile(title="First")
        r = expert_svc.create_profile(title="Second")
        assert not r.success
        assert r.status == ExpertProfileResult.ALREADY_EXISTS

    # Unicode tiếng Việt
    def test_create_unicode(self, expert_svc):
        r = expert_svc.create_profile(
            title="Lập trình viên Python cao cấp",
            bio="Chuyên gia về trí tuệ nhân tạo và học máy"
        )
        assert r.success
        assert "Python" in r.profile.title


# ══════════════════════════════════════════════════════════════════════════════
# 4–5. Update + Get profile
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateGetProfile:
    def test_get_not_found(self, expert_svc):
        r = expert_svc.get_profile()
        assert r.status == ExpertProfileResult.NOT_FOUND

    def test_get_after_create(self, expert_svc):
        expert_svc.create_profile(title="Dev", specialization="Backend")
        r = expert_svc.get_profile()
        assert r.success
        assert r.profile.title == "Dev"

    def test_get_includes_user_info(self, fresh_db):
        svc, auth = _login_expert(fresh_db, "ep_info", "ep_info@sp.local")
        svc.create_profile(title="Dev")
        r = svc.get_profile()
        assert r.success
        assert "ep_info" in r.profile.full_name or r.profile.email == "ep_info@sp.local"
        auth.logout(); SessionManager._instance = None

    def test_update_success(self, expert_svc):
        expert_svc.create_profile(title="Junior", hourly_rate=200_000)
        r = expert_svc.update_profile(
            title="Senior", bio="Updated bio", hourly_rate=800_000, availability="busy"
        )
        assert r.success
        assert r.profile.title == "Senior"
        assert r.profile.hourly_rate == 800_000
        assert r.profile.availability == "busy"

    def test_update_not_exists(self, expert_svc):
        r = expert_svc.update_profile(title="Ghost")
        assert r.status == ExpertProfileResult.NOT_FOUND

    # 9. Không thể sửa is_verified
    def test_update_cannot_change_verified(self, expert_svc):
        expert_svc.create_profile(title="Dev")
        expert_svc.update_profile(title="Dev Updated")
        r = expert_svc.get_profile()
        assert r.success
        assert r.profile.is_verified is False

    # 10. Không thể sửa user_id
    def test_update_cannot_change_user_id(self, fresh_db):
        svc1, auth1 = _login_expert(fresh_db, "ep_uid1", "ep_uid1@sp.local")
        svc1.create_profile(title="Dev 1")
        uid1 = svc1.get_profile().profile.user_id
        auth1.logout()

        svc2, auth2 = _login_expert(fresh_db, "ep_uid2", "ep_uid2@sp.local")
        svc2.create_profile(title="Dev 2")
        svc2.update_profile(title="Dev 2 Updated")
        r2 = svc2.get_profile()
        assert r2.profile.user_id != uid1
        auth2.logout(); SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# 7. Cross-user isolation
# ══════════════════════════════════════════════════════════════════════════════

class TestCrossUserIsolation:
    def test_expert_a_cannot_see_b(self, fresh_db):
        svc_a, auth_a = _login_expert(fresh_db, "ep_a", "ep_a@sp.local")
        svc_a.create_profile(title="Expert A")
        auth_a.logout()

        svc_b, auth_b = _login_expert(fresh_db, "ep_b", "ep_b@sp.local")
        r = svc_b.get_profile()
        assert r.status == ExpertProfileResult.NOT_FOUND, "B should not see A's profile"
        auth_b.logout(); SessionManager._instance = None

    def test_b_update_does_not_affect_a(self, fresh_db):
        svc_a, auth_a = _login_expert(fresh_db, "ep_a2", "ep_a2@sp.local")
        svc_a.create_profile(title="Original A")
        auth_a.logout()

        svc_b, auth_b = _login_expert(fresh_db, "ep_b2", "ep_b2@sp.local")
        svc_b.create_profile(title="B"); svc_b.update_profile(title="Updated B")
        auth_b.logout()

        _, auth_a2 = _login_expert(fresh_db, "ep_a2", "ep_a2@sp.local")
        from app.services.expert_profile_service import ExpertProfileService
        r = ExpertProfileService().get_profile()
        assert r.success and r.profile.title == "Original A"
        auth_a2.logout(); SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# 8. Role guard
# ══════════════════════════════════════════════════════════════════════════════

class TestRoleGuard:
    def test_candidate_cannot_get(self, candidate_svc):
        assert candidate_svc.get_profile().status == ExpertProfileResult.WRONG_ROLE

    def test_candidate_cannot_create(self, candidate_svc):
        assert candidate_svc.create_profile(title="Hack").status == ExpertProfileResult.WRONG_ROLE

    def test_candidate_cannot_update(self, candidate_svc):
        assert candidate_svc.update_profile(title="Hack").status == ExpertProfileResult.WRONG_ROLE

    def test_company_cannot_get(self, company_svc):
        assert company_svc.get_profile().status == ExpertProfileResult.WRONG_ROLE

    def test_company_cannot_create(self, company_svc):
        assert company_svc.create_profile(title="Hack").status == ExpertProfileResult.WRONG_ROLE


# ══════════════════════════════════════════════════════════════════════════════
# Not logged in
# ══════════════════════════════════════════════════════════════════════════════

class TestNotLoggedIn:
    def test_not_logged_get(self, fresh_db):
        SessionManager._instance = None
        r = ExpertProfileService().get_profile()
        assert r.status == ExpertProfileResult.NOT_LOGGED_IN

    def test_not_logged_create(self, fresh_db):
        SessionManager._instance = None
        r = ExpertProfileService().create_profile(title="Ghost")
        assert r.status == ExpertProfileResult.NOT_LOGGED_IN


# ══════════════════════════════════════════════════════════════════════════════
# 11–14. hourly_rate validation
# ══════════════════════════════════════════════════════════════════════════════

class TestHourlyRate:
    # 11. âm
    def test_negative_rate(self, expert_svc):
        r = expert_svc.create_profile(title="Dev", hourly_rate=-1)
        assert not r.success
        assert r.status == ExpertProfileResult.NEGATIVE_HOURLY_RATE

    # 12. không phải số (string)
    def test_string_rate(self, expert_svc):
        r = expert_svc.create_profile(title="Dev", hourly_rate="abc")  # type: ignore
        assert not r.success
        assert r.status == ExpertProfileResult.INVALID_HOURLY_RATE

    # 13. NaN
    def test_nan_rate(self, expert_svc):
        r = expert_svc.create_profile(title="Dev", hourly_rate=float("nan"))
        assert not r.success
        assert r.status == ExpertProfileResult.INVALID_HOURLY_RATE

    # 13. Infinity
    def test_inf_rate(self, expert_svc):
        r = expert_svc.create_profile(title="Dev", hourly_rate=float("inf"))
        assert not r.success
        assert r.status == ExpertProfileResult.INVALID_HOURLY_RATE

    def test_neg_inf_rate(self, expert_svc):
        r = expert_svc.create_profile(title="Dev", hourly_rate=float("-inf"))
        assert not r.success

    # 14. bằng 0 — hợp lệ
    def test_zero_rate(self, expert_svc):
        r = expert_svc.create_profile(title="Dev", hourly_rate=0)
        assert r.success
        assert r.profile.hourly_rate == 0

    def test_valid_rate(self, expert_svc):
        r = expert_svc.create_profile(title="Dev", hourly_rate=1_500_000)
        assert r.success
        assert r.profile.hourly_rate == 1_500_000

    def test_rate_stored_as_integer_vnd(self, expert_svc):
        """VNĐ lưu dưới dạng số nguyên (làm tròn)."""
        r = expert_svc.create_profile(title="Dev", hourly_rate=1_000_000.7)
        assert r.success
        # Phải làm tròn, không có phần lẻ
        assert r.profile.hourly_rate == round(1_000_000.7)

    def test_rate_display_format(self, expert_svc):
        """hourly_rate_display format VNĐ."""
        expert_svc.create_profile(title="Dev", hourly_rate=1_500_000)
        r = expert_svc.get_profile()
        assert r.success
        display = r.profile.hourly_rate_display
        assert "VNĐ" in display
        assert "1" in display  # Có số


# ══════════════════════════════════════════════════════════════════════════════
# 15–16. availability validation
# ══════════════════════════════════════════════════════════════════════════════

class TestAvailability:
    @pytest.mark.parametrize("avail", ["available", "busy", "unavailable"])
    def test_valid_availability(self, expert_svc, avail):
        r = expert_svc.create_profile(title="Dev", availability=avail)
        assert r.success
        assert r.profile.availability == avail

    @pytest.mark.parametrize("bad_avail", ["online", "free", "", "AVAILABLE", "1"])
    def test_invalid_availability(self, expert_svc, bad_avail):
        r = expert_svc.create_profile(title="Dev", availability=bad_avail)
        assert not r.success
        assert r.status == ExpertProfileResult.INVALID_AVAILABILITY

    def test_update_availability(self, expert_svc):
        expert_svc.create_profile(title="Dev", availability="available")
        r = expert_svc.update_profile(title="Dev", availability="busy")
        assert r.success and r.profile.availability == "busy"


# ══════════════════════════════════════════════════════════════════════════════
# 17. SQL injection
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLInjection:
    @pytest.mark.parametrize("payload", [
        "'; DROP TABLE expert_profiles;--",
        "' OR '1'='1",
        "'; UPDATE users SET role='admin' WHERE 1=1;--",
        "Test'--",
    ])
    def test_injection_in_title(self, expert_svc, payload):
        r = expert_svc.create_profile(title=payload)
        # DB phải còn nguyên
        get_r = expert_svc.get_profile()
        assert get_r.status in (ExpertProfileResult.SUCCESS, ExpertProfileResult.NOT_FOUND)

    def test_injection_does_not_elevate_role(self, expert_svc):
        expert_svc.create_profile(
            title="Dev'; UPDATE users SET role='admin' WHERE 1=1;--"
        )
        r = expert_svc.get_profile()
        if r.success:
            from app.database.connection import db
            u = db.fetchone("SELECT role FROM users WHERE id=?", (r.profile.user_id,))
            assert u["role"] == "expert"


# ══════════════════════════════════════════════════════════════════════════════
# 19. Rollback khi DB lỗi
# ══════════════════════════════════════════════════════════════════════════════

class TestRollback:
    def test_db_error_on_get(self, fresh_db):
        svc, auth = _login_expert(fresh_db, "ep_roll", "ep_roll@sp.local")
        with patch("app.services.expert_profile_service.db") as mock_db:
            mock_db.fetchone.side_effect = sqlite3.OperationalError("gone")
            r = svc.get_profile()
        assert r.status == ExpertProfileResult.DB_ERROR
        auth.logout(); SessionManager._instance = None

    def test_failed_update_preserves_data(self, expert_svc):
        """Update với availability sai → data cũ không mất."""
        expert_svc.create_profile(
            title="Original", bio="Original bio",
            specialization="Python", hourly_rate=500_000, availability="available"
        )
        # Thử update với availability sai
        r = expert_svc.update_profile(
            title="Should Not Save", availability="invalid_val"
        )
        assert not r.success
        # Dữ liệu gốc vẫn còn
        r2 = expert_svc.get_profile()
        assert r2.success
        assert r2.profile.title == "Original"
        assert r2.profile.bio == "Original bio"
        assert r2.profile.availability == "available"


# ══════════════════════════════════════════════════════════════════════════════
# 20. MIG-004 compatibility
# ══════════════════════════════════════════════════════════════════════════════

class TestMig004Compat:
    def test_expert_profiles_table_exists(self, fresh_db):
        row = fresh_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='expert_profiles'"
        )
        assert row is not None

    def test_all_columns_present(self, expert_svc):
        expert_svc.create_profile(title="Full", specialization="X",
                                   bio="B", hourly_rate=100_000, availability="busy")
        r = expert_svc.get_profile()
        assert r.success
        for f in ["id","user_id","title","bio","specialization",
                   "hourly_rate","availability","is_verified",
                   "created_at","updated_at","full_name","email"]:
            assert hasattr(r.profile, f), f"Missing field: {f}"

    def test_cascade_delete(self, fresh_db):
        svc, auth = _login_expert(fresh_db, "ep_del", "ep_del@sp.local")
        svc.create_profile(title="Delete Me")
        uid = fresh_db.fetchone("SELECT id FROM users WHERE username='ep_del'")["id"]
        auth.logout()
        fresh_db.execute("DELETE FROM users WHERE id=?", (uid,))
        row = fresh_db.fetchone("SELECT * FROM expert_profiles WHERE user_id=?", (uid,))
        assert row is None
        SessionManager._instance = None

    def test_availability_label(self, expert_svc):
        expert_svc.create_profile(title="Dev", availability="busy")
        r = expert_svc.get_profile()
        assert r.success
        assert r.profile.availability_label == "Đang bận"
