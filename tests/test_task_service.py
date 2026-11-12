# -*- coding: utf-8 -*-
"""Tests: TaskService — phân công nhiệm vụ."""

import pytest
from app.services.task_service import TaskService, TaskResult, TASK_TYPES
from app.services.contract_service import ContractService
from app.services.auth_service import AuthService, SessionManager
from app.utils.helpers import hash_password


def _create_user(fdb, uname, role, pw="Test@Pass1"):
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
            " VALUES(?,?,'available')", (uid, f"Expert {uname}")
        )
    elif role == "company":
        uid = fdb.fetchone("SELECT id FROM users WHERE username=?", (uname,))["id"]
        fdb.execute(
            "INSERT OR IGNORE INTO company_profiles(user_id,company_name)"
            " VALUES(?,?)", (uid, f"Co {uname}")
        )


def _login(fdb, uname, role, pw="Test@Pass1"):
    _create_user(fdb, uname, role, pw)
    email = f"{uname}@sp.local"
    SessionManager._instance = None
    auth = AuthService()
    r = auth.login(email, pw)
    assert r.success, f"Login failed for {uname} ({role}): {r.status}"
    return auth


def _ep_id(fdb, uname):
    return fdb.fetchone(
        "SELECT ep.id FROM expert_profiles ep JOIN users u ON u.id=ep.user_id"
        " WHERE u.username=?", (uname,)
    )["id"]


def _active_contract(fdb, comp_u, exp_u):
    """Tạo contract active, session sạch sau đó."""
    _create_user(fdb, comp_u, "company")
    _create_user(fdb, exp_u, "expert")
    comp_auth = _login(fdb, comp_u, "company")
    r = ContractService().invite_expert(_ep_id(fdb, exp_u))
    cid = r.contract.id
    comp_auth.logout()
    exp_auth = _login(fdb, exp_u, "expert")
    ContractService().accept_contract(cid)
    exp_auth.logout()
    SessionManager._instance = None
    return cid


def _make_task(fdb, comp_u, exp_u, title="Task", task_type="review"):
    """Tạo contract active + task, trả về (task_id, contract_id)."""
    cid = _active_contract(fdb, comp_u, exp_u)
    comp_auth = _login(fdb, comp_u, "company")
    tr = TaskService().create_task(cid, title, task_type)
    comp_auth.logout(); SessionManager._instance = None
    assert tr.success, f"create_task failed: {tr.status}"
    return tr.task.id, cid


# ══════════════════════════════════════════════════════════════════════════════
# Create task
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateTask:
    def test_create_success(self, fresh_db):
        cid = _active_contract(fresh_db, "c_cr", "e_cr")
        comp_auth = _login(fresh_db, "c_cr", "company")
        r = TaskService().create_task(cid, "Review hồ sơ", "review")
        assert r.success
        assert r.task.status == "pending"
        assert r.task.contract_id == cid
        comp_auth.logout(); SessionManager._instance = None

    def test_create_requires_active_contract(self, fresh_db):
        _create_user(fresh_db, "c_pnd", "company")
        _create_user(fresh_db, "e_pnd", "expert")
        comp_auth = _login(fresh_db, "c_pnd", "company")
        r_inv = ContractService().invite_expert(_ep_id(fresh_db, "e_pnd"))
        cid = r_inv.contract.id
        # Chưa accept — pending_expert
        tr = TaskService().create_task(cid, "Test", "review")
        assert tr.status == TaskResult.CONTRACT_NOT_ACTIVE
        comp_auth.logout(); SessionManager._instance = None

    def test_create_empty_title(self, fresh_db):
        cid = _active_contract(fresh_db, "c_etl", "e_etl")
        comp_auth = _login(fresh_db, "c_etl", "company")
        r = TaskService().create_task(cid, "   ", "review")
        assert r.status == TaskResult.EMPTY_TITLE
        comp_auth.logout(); SessionManager._instance = None

    def test_create_invalid_task_type(self, fresh_db):
        cid = _active_contract(fresh_db, "c_tty", "e_tty")
        comp_auth = _login(fresh_db, "c_tty", "company")
        r = TaskService().create_task(cid, "Task", "invalid_type")
        assert r.status == TaskResult.INVALID_TASK_TYPE
        comp_auth.logout(); SessionManager._instance = None

    def test_create_invalid_priority(self, fresh_db):
        cid = _active_contract(fresh_db, "c_pri", "e_pri")
        comp_auth = _login(fresh_db, "c_pri", "company")
        r = TaskService().create_task(cid, "Task", "review", priority="super_urgent")
        assert r.status == TaskResult.INVALID_PRIORITY
        comp_auth.logout(); SessionManager._instance = None

    def test_create_wrong_role_expert(self, fresh_db):
        cid = _active_contract(fresh_db, "c_wr", "e_wr")
        exp_auth = _login(fresh_db, "e_wr", "expert")
        r = TaskService().create_task(cid, "Task", "review")
        assert r.status == TaskResult.WRONG_ROLE
        exp_auth.logout(); SessionManager._instance = None

    def test_all_task_types_valid(self, fresh_db):
        cid = _active_contract(fresh_db, "c_all", "e_all")
        comp_auth = _login(fresh_db, "c_all", "company")
        for tt in TASK_TYPES:
            r = TaskService().create_task(cid, f"Task {tt}", tt)
            assert r.success, f"task_type={tt} phải hợp lệ"
        comp_auth.logout(); SessionManager._instance = None

    def test_not_logged_in(self, fresh_db):
        SessionManager._instance = None
        r = TaskService().create_task(1, "Task", "review")
        assert r.status == TaskResult.NOT_LOGGED_IN


# ══════════════════════════════════════════════════════════════════════════════
# State transitions
# ══════════════════════════════════════════════════════════════════════════════

class TestTaskStateTransitions:
    def test_expert_start(self, fresh_db):
        tid, _ = _make_task(fresh_db, "c_st", "e_st")
        exp_auth = _login(fresh_db, "e_st", "expert")
        r = TaskService().start_task(tid)
        assert r.success and r.task.status == "in_progress"
        exp_auth.logout(); SessionManager._instance = None

    def test_expert_complete(self, fresh_db):
        tid, _ = _make_task(fresh_db, "c_co", "e_co")
        exp_auth = _login(fresh_db, "e_co", "expert")
        TaskService().start_task(tid)
        r = TaskService().complete_task(tid)
        assert r.success and r.task.status == "completed"
        assert r.task.completed_at is not None
        exp_auth.logout(); SessionManager._instance = None

    def test_company_cancel_pending(self, fresh_db):
        tid, _ = _make_task(fresh_db, "c_cp", "e_cp")
        comp_auth = _login(fresh_db, "c_cp", "company")
        r = TaskService().cancel_task(tid)
        assert r.success and r.task.status == "cancelled"
        comp_auth.logout(); SessionManager._instance = None

    def test_expert_cancel_in_progress(self, fresh_db):
        tid, _ = _make_task(fresh_db, "c_ec", "e_ec")
        exp_auth = _login(fresh_db, "e_ec", "expert")
        TaskService().start_task(tid)
        r = TaskService().cancel_task(tid)
        assert r.success and r.task.status == "cancelled"
        exp_auth.logout(); SessionManager._instance = None

    def test_cannot_start_completed_task(self, fresh_db):
        tid, _ = _make_task(fresh_db, "c_nc", "e_nc")
        exp_auth = _login(fresh_db, "e_nc", "expert")
        TaskService().start_task(tid)
        TaskService().complete_task(tid)
        r = TaskService().start_task(tid)
        assert r.status == TaskResult.INVALID_TRANSITION
        exp_auth.logout(); SessionManager._instance = None

    def test_cannot_complete_pending(self, fresh_db):
        tid, _ = _make_task(fresh_db, "c_ncp", "e_ncp")
        exp_auth = _login(fresh_db, "e_ncp", "expert")
        r = TaskService().complete_task(tid)
        assert r.status == TaskResult.INVALID_TRANSITION
        exp_auth.logout(); SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# Authorization
# ══════════════════════════════════════════════════════════════════════════════

class TestTaskAuthorization:
    def test_expert_a_cannot_start_b_task(self, fresh_db):
        tid, _ = _make_task(fresh_db, "c_ab", "e_ab")
        # Expert A (khác với e_ab)
        exp_a_auth = _login(fresh_db, "e_ab_other", "expert")
        r = TaskService().start_task(tid)
        assert r.status == TaskResult.FORBIDDEN
        exp_a_auth.logout(); SessionManager._instance = None

    def test_company_a_cannot_cancel_b_task(self, fresh_db):
        tid, _ = _make_task(fresh_db, "c_a_perm", "e_a_perm")
        # Company B (khác với c_a_perm)
        cb_auth = _login(fresh_db, "c_b_perm", "company")
        r = TaskService().cancel_task(tid)
        assert r.status == TaskResult.FORBIDDEN
        cb_auth.logout(); SessionManager._instance = None

    def test_candidate_cannot_create(self, fresh_db):
        _create_user(fresh_db, "cand_tsk", "candidate")
        cand_auth = _login(fresh_db, "cand_tsk", "candidate")
        r = TaskService().create_task(1, "Hack", "review")
        assert r.status == TaskResult.WRONG_ROLE
        cand_auth.logout(); SessionManager._instance = None

    def test_sql_injection_in_title(self, fresh_db):
        cid = _active_contract(fresh_db, "c_sqli", "e_sqli")
        comp_auth = _login(fresh_db, "c_sqli", "company")
        payload = "'; DROP TABLE tasks;--"
        r = TaskService().create_task(cid, payload, "review")
        count = fresh_db.fetchone("SELECT COUNT(*) as c FROM tasks")["c"]
        assert count >= 0
        comp_auth.logout(); SessionManager._instance = None

    def test_list_only_own_tasks(self, fresh_db):
        c1id = _active_contract(fresh_db, "c_own1t", "e_own1t")
        comp_auth = _login(fresh_db, "c_own1t", "company")
        TaskService().create_task(c1id, "Task Own1", "review")
        comp_auth.logout()

        cb_auth = _login(fresh_db, "c_own2t", "company")
        r = TaskService().list_my_tasks()
        assert r.success and len(r.tasks) == 0
        cb_auth.logout(); SessionManager._instance = None


# ══════════════════════════════════════════════════════════════════════════════
# MIG compat
# ══════════════════════════════════════════════════════════════════════════════

class TestTaskMigCompat:
    def test_tasks_table_exists(self, fresh_db):
        row = fresh_db.fetchone("SELECT name FROM sqlite_master WHERE name='tasks'")
        assert row is not None

    def test_task_model_fields(self, fresh_db):
        cid = _active_contract(fresh_db, "c_mig", "e_mig")
        comp_auth = _login(fresh_db, "c_mig", "company")
        r = TaskService().create_task(cid, "MIG test", "grading", priority="high")
        assert r.success
        t = r.task
        for f in ["id","company_id","expert_id","contract_id","title",
                   "task_type","status","priority","assigned_at"]:
            assert hasattr(t, f)
        assert t.task_type_label == "Chấm điểm"
        assert t.priority_label == "Cao"
        comp_auth.logout(); SessionManager._instance = None
