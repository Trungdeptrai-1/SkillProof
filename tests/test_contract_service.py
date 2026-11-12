# -*- coding: utf-8 -*-
"""Tests: ContractService — hợp đồng Company–Expert."""

import pytest
import sqlite3

from app.services.contract_service import (
    ContractService, ContractResult, ContractModel,
)
from app.services.auth_service import AuthService, SessionManager
from app.utils.helpers import hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_user(fdb, uname, role, pw="Test@Pass1"):
    """Chỉ tạo user + profile, KHÔNG login."""
    email = f"{uname}@sp.local"
    fdb.execute(
        "INSERT OR IGNORE INTO users(username,email,password,full_name,role,is_active,is_deleted)"
        " VALUES(?,?,?,?,?,1,0)",
        (uname, email, hash_password(pw), uname.title(), role)
    )
    if role == "expert":
        uid = fdb.fetchone("SELECT id FROM users WHERE username=?", (uname,))["id"]
        fdb.execute(
            "INSERT OR IGNORE INTO expert_profiles(user_id,title,availability)"
            " VALUES(?,?,'available')",
            (uid, f"Expert {uname}")
        )
    elif role == "company":
        uid = fdb.fetchone("SELECT id FROM users WHERE username=?", (uname,))["id"]
        fdb.execute(
            "INSERT OR IGNORE INTO company_profiles(user_id,company_name)"
            " VALUES(?,?)",
            (uid, f"Co {uname}")
        )


def _login(fdb, uname, role, pw="Test@Pass1"):
    """Tạo user nếu chưa có, login và trả về (svc, auth)."""
    _create_user(fdb, uname, role, pw)
    email = f"{uname}@sp.local"
    SessionManager._instance = None
    auth = AuthService()
    r = auth.login(email, pw)
    assert r.success, f"Login failed for {uname} ({role}): {r.status}"
    return ContractService(), auth


def _ep_id(fdb, uname) -> int:
    return fdb.fetchone(
        "SELECT ep.id FROM expert_profiles ep"
        " JOIN users u ON u.id=ep.user_id WHERE u.username=?", (uname,)
    )["id"]


def _make_active_contract(fdb, comp_u, exp_u):
    """Tạo hợp đồng active, trả về contract_id."""
    _create_user(fdb, comp_u, "company")
    _create_user(fdb, exp_u, "expert")
    # Company invite
    comp_svc, comp_auth = _login(fdb, comp_u, "company")
    r = comp_svc.invite_expert(_ep_id(fdb, exp_u))
    assert r.success, f"invite failed: {r.status}"
    cid = r.contract.id
    comp_auth.logout()
    # Expert accept
    exp_svc, exp_auth = _login(fdb, exp_u, "expert")
    exp_svc.accept_contract(cid)
    exp_auth.logout()
    SessionManager._instance = None
    return cid


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def company_svc(fresh_db):
    """Login as company1, yield (svc, fdb)."""
    svc, auth = _login(fresh_db, "comp1", "company")
    yield svc, fresh_db
    auth.logout()
    SessionManager._instance = None


@pytest.fixture()
def expert_svc(fresh_db):
    """Login as exp1, yield (svc, fdb)."""
    svc, auth = _login(fresh_db, "exp1", "expert")
    yield svc, fresh_db
    auth.logout()
    SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# invite_expert
# ══════════════════════════════════════════════════════════════════════════════

class TestInviteExpert:
    def test_invite_success(self, company_svc):
        svc, fdb = company_svc
        _create_user(fdb, "exp_inv", "expert")
        r = svc.invite_expert(_ep_id(fdb, "exp_inv"))
        assert r.success
        assert r.contract.status == "pending_expert"

    def test_invite_creates_pending_not_active(self, company_svc):
        svc, fdb = company_svc
        _create_user(fdb, "exp_pnd", "expert")
        r = svc.invite_expert(_ep_id(fdb, "exp_pnd"))
        assert r.contract.status == "pending_expert"

    def test_invite_nonexistent_expert(self, company_svc):
        svc, fdb = company_svc
        r = svc.invite_expert(expert_profile_id=9999)
        assert r.status == ContractResult.EXPERT_NOT_FOUND

    def test_invite_unavailable_expert(self, company_svc):
        svc, fdb = company_svc
        _create_user(fdb, "exp_unavail", "expert")
        uid = fdb.fetchone("SELECT id FROM users WHERE username='exp_unavail'")["id"]
        fdb.execute("UPDATE expert_profiles SET availability='unavailable' WHERE user_id=?", (uid,))
        r = svc.invite_expert(_ep_id(fdb, "exp_unavail"))
        assert r.status == ContractResult.EXPERT_UNAVAILABLE

    def test_d4_no_duplicate_active(self, company_svc):
        """D4: không tạo 2 hợp đồng pending/active với cùng Expert."""
        svc, fdb = company_svc
        _create_user(fdb, "exp_d4", "expert")
        ep_id = _ep_id(fdb, "exp_d4")
        r1 = svc.invite_expert(ep_id)
        assert r1.success
        r2 = svc.invite_expert(ep_id)
        assert r2.status == ContractResult.ACTIVE_CONTRACT_EXISTS

    def test_invite_wrong_role(self, expert_svc):
        svc, fdb = expert_svc
        r = svc.invite_expert(1)
        assert r.status == ContractResult.WRONG_ROLE

    def test_invite_not_logged_in(self, fresh_db):
        SessionManager._instance = None
        r = ContractService().invite_expert(1)
        assert r.status == ContractResult.NOT_LOGGED_IN

    def test_contract_code_unique(self, company_svc):
        svc, fdb = company_svc
        _create_user(fdb, "exp_cu1", "expert")
        _create_user(fdb, "exp_cu2", "expert")
        r1 = svc.invite_expert(_ep_id(fdb, "exp_cu1"))
        r2 = svc.invite_expert(_ep_id(fdb, "exp_cu2"))
        assert r1.success and r2.success
        assert r1.contract.contract_code != r2.contract.contract_code

    def test_soft_deleted_company_cannot_invite(self, company_svc):
        svc, fdb = company_svc
        _create_user(fdb, "exp_sdc", "expert")
        # Soft-delete company đang login
        uid = SessionManager.instance().current_user.id
        fdb.execute("UPDATE users SET is_deleted=1 WHERE id=?", (uid,))
        r = svc.invite_expert(_ep_id(fdb, "exp_sdc"))
        assert r.status == ContractResult.WRONG_ROLE
        # Restore
        fdb.execute("UPDATE users SET is_deleted=0 WHERE id=?", (uid,))


# ══════════════════════════════════════════════════════════════════════════════
# State transitions
# ══════════════════════════════════════════════════════════════════════════════

class TestStateTransitions:
    def _pending(self, fdb, comp_u, exp_u):
        """Tạo hợp đồng pending, session là Expert."""
        _create_user(fdb, comp_u, "company")
        _create_user(fdb, exp_u, "expert")
        comp_svc, comp_auth = _login(fdb, comp_u, "company")
        r = comp_svc.invite_expert(_ep_id(fdb, exp_u))
        cid = r.contract.id
        comp_auth.logout()
        exp_svc, exp_auth = _login(fdb, exp_u, "expert")
        return cid, exp_svc, exp_auth

    def test_expert_accept(self, fresh_db):
        cid, svc, auth = self._pending(fresh_db, "c_acc", "e_acc")
        r = svc.accept_contract(cid)
        assert r.success and r.contract.status == "active"
        auth.logout(); SessionManager._instance = None

    def test_expert_reject(self, fresh_db):
        cid, svc, auth = self._pending(fresh_db, "c_rej", "e_rej")
        r = svc.reject_contract(cid, reason="Không phù hợp")
        assert r.success and r.contract.status == "rejected"
        assert r.contract.rejection_reason == "Không phù hợp"
        auth.logout(); SessionManager._instance = None

    def test_company_cancel_pending(self, fresh_db):
        cid, exp_svc, exp_auth = self._pending(fresh_db, "c_can", "e_can")
        exp_auth.logout()
        comp_svc, comp_auth = _login(fresh_db, "c_can", "company")
        r = comp_svc.cancel_pending_contract(cid)
        assert r.success and r.contract.status == "cancelled"
        comp_auth.logout(); SessionManager._instance = None

    def test_complete_contract(self, fresh_db):
        cid = _make_active_contract(fresh_db, "c_cmp", "e_cmp")
        comp_svc, comp_auth = _login(fresh_db, "c_cmp", "company")
        r = comp_svc.complete_contract(cid)
        assert r.success and r.contract.status == "completed"
        comp_auth.logout(); SessionManager._instance = None

    def test_terminate_contract(self, fresh_db):
        cid = _make_active_contract(fresh_db, "c_ter", "e_ter")
        comp_svc, comp_auth = _login(fresh_db, "c_ter", "company")
        r = comp_svc.terminate_contract(cid, reason="Dừng dự án")
        assert r.success and r.contract.status == "terminated"
        comp_auth.logout(); SessionManager._instance = None

    def test_invalid_transition_from_terminal(self, fresh_db):
        cid, svc, auth = self._pending(fresh_db, "c_tm2", "e_tm2")
        svc.reject_contract(cid)
        # Thử accept sau reject
        r = svc.accept_contract(cid)
        assert r.status == ContractResult.INVALID_TRANSITION
        auth.logout(); SessionManager._instance = None

    def test_d3_terminate_auto_cancels_pending_tasks(self, fresh_db):
        """D3: Terminate → task pending bị cancel."""
        from app.services.task_service import TaskService
        cid = _make_active_contract(fresh_db, "c_d3", "e_d3")
        comp_svc, comp_auth = _login(fresh_db, "c_d3", "company")
        ts = TaskService()
        tr = ts.create_task(cid, "Review CV", "review")
        assert tr.success
        task_id = tr.task.id
        cr = comp_svc.terminate_contract(cid, reason="Test D3")
        assert cr.success
        task_row = fresh_db.fetchone("SELECT status FROM tasks WHERE id=?", (task_id,))
        assert task_row["status"] == "cancelled"
        comp_auth.logout(); SessionManager._instance = None

    def test_complete_blocked_by_pending_tasks(self, fresh_db):
        from app.services.task_service import TaskService
        cid = _make_active_contract(fresh_db, "c_blk", "e_blk")
        comp_svc, comp_auth = _login(fresh_db, "c_blk", "company")
        TaskService().create_task(cid, "Grading test", "grading")
        r = comp_svc.complete_contract(cid)
        assert r.status == ContractResult.PENDING_TASKS_EXIST
        comp_auth.logout(); SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# Phân quyền và cross-company isolation
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthorization:
    def test_company_a_cannot_see_b_contract(self, fresh_db):
        comp_a_svc, comp_a_auth = _login(fresh_db, "compA", "company")
        _create_user(fresh_db, "expA", "expert")
        r = comp_a_svc.invite_expert(_ep_id(fresh_db, "expA"))
        cid = r.contract.id
        comp_a_auth.logout()

        _, comp_b_auth = _login(fresh_db, "compB", "company")
        r2 = ContractService().get_contract(cid)
        assert r2.status == ContractResult.FORBIDDEN
        comp_b_auth.logout(); SessionManager._instance = None

    def test_expert_cannot_accept_others_contract(self, fresh_db):
        comp_svc, comp_auth = _login(fresh_db, "compAB", "company")
        _create_user(fresh_db, "expAB_b", "expert")
        r = comp_svc.invite_expert(_ep_id(fresh_db, "expAB_b"))
        cid = r.contract.id
        comp_auth.logout()

        # Expert A — không phải người được invite
        _, exp_a_auth = _login(fresh_db, "expAB_a", "expert")
        r2 = ContractService().accept_contract(cid)
        assert r2.status in (ContractResult.FORBIDDEN, ContractResult.NOT_FOUND)
        exp_a_auth.logout(); SessionManager._instance = None

    def test_list_only_own_contracts(self, fresh_db):
        c1_svc, c1_auth = _login(fresh_db, "comp_own1", "company")
        _create_user(fresh_db, "exp_own", "expert")
        c1_svc.invite_expert(_ep_id(fresh_db, "exp_own"))
        c1_auth.logout()

        _, c2_auth = _login(fresh_db, "comp_own2", "company")
        r = ContractService().list_my_contracts()
        assert r.success
        assert len(r.contracts) == 0
        c2_auth.logout(); SessionManager._instance = None

    def test_sql_injection_in_notes(self, company_svc):
        svc, fdb = company_svc
        _create_user(fdb, "exp_inj", "expert")
        r = svc.invite_expert(
            _ep_id(fdb, "exp_inj"),
            notes="'; DROP TABLE company_expert_contracts;--"
        )
        # DB còn nguyên
        assert r.success or r.status in (ContractResult.DB_ERROR,)
        count = fdb.fetchone("SELECT COUNT(*) as c FROM company_expert_contracts")["c"]
        assert count >= 0


# ══════════════════════════════════════════════════════════════════════════════
# MIG compat
# ══════════════════════════════════════════════════════════════════════════════

class TestMigCompat:
    def test_all_6_status_in_schema(self, fresh_db):
        conn = fresh_db.get_connection()
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='company_expert_contracts'"
        ).fetchone()["sql"]
        for s in ("pending_expert","rejected","active","completed","terminated","cancelled"):
            assert f"'{s}'" in ddl

    def test_contract_table_exists(self, fresh_db):
        row = fresh_db.fetchone(
            "SELECT name FROM sqlite_master WHERE name='company_expert_contracts'"
        )
        assert row is not None
