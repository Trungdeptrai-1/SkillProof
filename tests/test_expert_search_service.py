# -*- coding: utf-8 -*-
"""Tests: ExpertSearchService — tìm kiếm chuyên gia."""

import pytest
from app.services.expert_search_service import (
    ExpertSearchService, SearchResult, ExpertSearchResult,
)
from app.services.auth_service import AuthService, SessionManager
from app.utils.helpers import hash_password


def _login(fdb, uname, role, pw="Test@Pass1"):
    email = f"{uname}@sp.local"
    fdb.execute(
        "INSERT OR IGNORE INTO users(username,email,password,full_name,role,is_active,is_deleted)"
        " VALUES(?,?,?,?,?,1,0)",
        (uname, email, hash_password(pw), uname.title(), role)
    )
    if role == "expert":
        uid = fdb.fetchone("SELECT id FROM users WHERE username=?", (uname,))["id"]
        fdb.execute(
            "INSERT OR IGNORE INTO expert_profiles"
            "(user_id,title,specialization,availability,hourly_rate,is_verified)"
            " VALUES(?,?,?,'available',?,0)",
            (uid, f"Expert {uname}", "Python Backend", 1_000_000)
        )
    elif role == "company":
        uid = fdb.fetchone("SELECT id FROM users WHERE username=?", (uname,))["id"]
        fdb.execute(
            "INSERT OR IGNORE INTO company_profiles(user_id,company_name)"
            " VALUES(?,?)", (uid, f"Co {uname}")
        )
    SessionManager._instance = None
    auth = AuthService()
    r = auth.login(email, pw)
    assert r.success, f"Login failed for {uname}: {r.status}"
    return auth


@pytest.fixture()
def search_svc(fresh_db):
    auth = _login(fresh_db, "search_co", "company")
    # Tạo vài expert
    for i, spec in enumerate(["Python Backend","Java","AI ML","Python Backend"]):
        exp_u = f"search_exp{i}"
        auth_e = _login(fresh_db, exp_u, "expert")
        uid = fresh_db.fetchone("SELECT id FROM users WHERE username=?", (exp_u,))["id"]
        fresh_db.execute(
            "UPDATE expert_profiles SET specialization=?, hourly_rate=?, availability=?"
            " WHERE user_id=?",
            (spec, (i+1)*500_000, "available" if i!=3 else "busy", uid)
        )
        auth_e.logout()

    SessionManager._instance = None
    auth.logout()
    _login(fresh_db, "search_co", "company")
    yield ExpertSearchService(), fresh_db


class TestExpertSearch:
    def test_search_returns_results(self, search_svc):
        svc, fdb = search_svc
        r = svc.search()
        assert r.success
        assert len(r.experts) > 0

    def test_search_hides_user_id(self, search_svc):
        """Kết quả không có user_id — chỉ có profile_id."""
        svc, fdb = search_svc
        r = svc.search()
        assert r.success
        for e in r.experts:
            assert isinstance(e, ExpertSearchResult)
            assert hasattr(e, "profile_id")
            assert not hasattr(e, "user_id")

    def test_search_hides_email(self, search_svc):
        """Kết quả không có email."""
        svc, fdb = search_svc
        r = svc.search()
        for e in r.experts:
            assert not hasattr(e, "email")
            assert not hasattr(e, "full_name")

    def test_filter_by_specialization(self, search_svc):
        svc, fdb = search_svc
        r = svc.search(specialization="Python")
        assert r.success
        for e in r.experts:
            assert e.specialization and "Python" in e.specialization

    def test_filter_by_availability(self, search_svc):
        svc, fdb = search_svc
        r = svc.search(availability="available")
        for e in r.experts:
            assert e.availability == "available"

    def test_filter_by_max_rate(self, search_svc):
        svc, fdb = search_svc
        r = svc.search(max_rate=1_000_000)
        for e in r.experts:
            if e.hourly_rate is not None:
                assert e.hourly_rate <= 1_000_000

    def test_filter_by_min_rate(self, search_svc):
        svc, fdb = search_svc
        r = svc.search(min_rate=1_500_000)
        for e in r.experts:
            if e.hourly_rate is not None:
                assert e.hourly_rate >= 1_500_000

    def test_excludes_already_contracted(self, search_svc):
        """Expert đã có hợp đồng pending/active với Company không xuất hiện."""
        svc, fdb = search_svc
        # Lấy 1 expert từ kết quả
        r = svc.search()
        assert len(r.experts) > 0
        ep_id = r.experts[0].profile_id

        # Tạo hợp đồng pending với expert đó
        from app.services.contract_service import ContractService
        ContractService().invite_expert(ep_id)

        # Tìm lại — expert đó không còn trong kết quả
        r2 = svc.search()
        profile_ids = [e.profile_id for e in r2.experts]
        assert ep_id not in profile_ids

    def test_excludes_deleted_experts(self, fresh_db):
        """Expert bị soft-delete không hiển thị."""
        _login(fresh_db, "comp_del_srch", "company")
        _login(fresh_db, "exp_del_srch", "expert")
        uid = fresh_db.fetchone("SELECT id FROM users WHERE username='exp_del_srch'")["id"]
        fresh_db.execute("UPDATE users SET is_deleted=1 WHERE id=?", (uid,))

        r = ExpertSearchService().search()
        profile_ids = [e.profile_id for e in r.experts]
        ep_id = fresh_db.fetchone(
            "SELECT id FROM expert_profiles WHERE user_id=?", (uid,)
        )["id"]
        assert ep_id not in profile_ids
        SessionManager._instance = None

    def test_wrong_role_candidate(self, fresh_db):
        fresh_db.execute(
            "INSERT OR IGNORE INTO users(username,email,password,full_name,role,is_active,is_deleted)"
            " VALUES(?,?,?,?,?,1,0)",
            ("srch_cand","srch_cand@sp.local",hash_password("Test@Pass1"),"Cand","candidate")
        )
        SessionManager._instance = None
        auth = AuthService(); auth.login("srch_cand@sp.local","Test@Pass1")
        r = ExpertSearchService().search()
        assert r.status == SearchResult.WRONG_ROLE
        auth.logout(); SessionManager._instance = None

    def test_not_logged_in(self, fresh_db):
        SessionManager._instance = None
        r = ExpertSearchService().search()
        assert r.status == SearchResult.NOT_LOGGED_IN

    def test_hourly_rate_display_format(self, search_svc):
        svc, fdb = search_svc
        r = svc.search()
        for e in r.experts:
            display = e.hourly_rate_display
            assert isinstance(display, str)
            if e.hourly_rate is not None:
                assert "VNĐ" in display

    def test_profile_id_maps_to_different_users(self, search_svc):
        """Mỗi profile_id là duy nhất trong kết quả."""
        svc, fdb = search_svc
        r = svc.search()
        ids = [e.profile_id for e in r.experts]
        assert len(ids) == len(set(ids)), "profile_id phải unique trong kết quả"

    def test_verified_only_filter(self, fresh_db):
        _login(fresh_db, "comp_vrf", "company")
        _login(fresh_db, "exp_vrf", "expert")
        uid = fresh_db.fetchone("SELECT id FROM users WHERE username='exp_vrf'")["id"]
        fresh_db.execute("UPDATE expert_profiles SET is_verified=1 WHERE user_id=?", (uid,))

        r = ExpertSearchService().search(verified_only=True)
        for e in r.experts:
            assert e.is_verified is True
        SessionManager._instance = None
