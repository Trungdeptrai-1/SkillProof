# -*- coding: utf-8 -*-
"""
Tests: SessionManager — singleton, start/end, role access.
"""

import pytest
from app.services.auth_service import SessionManager
from app.models.user_model import UserModel


def _make_user(role: str = "candidate") -> UserModel:
    return UserModel(
        id=1, username="test", email="test@sp.local",
        full_name="Test User", role=role,
        avatar_path=None, is_active=True,
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )


@pytest.fixture(autouse=True)
def reset_session():
    """Reset singleton trước và sau mỗi test."""
    SessionManager._instance = None
    yield
    mgr = SessionManager._instance
    if mgr:
        mgr.end_session()
    SessionManager._instance = None


class TestSessionManagerSingleton:
    def test_same_instance(self):
        s1 = SessionManager()
        s2 = SessionManager()
        assert id(s1) == id(s2)

    def test_instance_method(self):
        s = SessionManager.instance()
        assert isinstance(s, SessionManager)
        assert id(s) == id(SessionManager())


class TestSessionState:
    def test_initially_not_logged_in(self):
        s = SessionManager.instance()
        assert not s.is_logged_in
        assert s.current_user is None
        assert s.role is None

    def test_start_session(self):
        s = SessionManager.instance()
        user = _make_user("admin")
        s.start_session(user)
        assert s.is_logged_in
        assert s.current_user is user
        assert s.role == "admin"

    def test_end_session(self):
        s = SessionManager.instance()
        s.start_session(_make_user())
        s.end_session()
        assert not s.is_logged_in
        assert s.current_user is None
        assert s.role is None

    def test_end_session_when_not_logged_in(self):
        s = SessionManager.instance()
        s.end_session()  # Không crash
        assert not s.is_logged_in

    def test_replace_session(self):
        s = SessionManager.instance()
        u1 = _make_user("admin")
        u2 = _make_user("candidate")
        s.start_session(u1)
        s.start_session(u2)  # Ghi đè
        assert s.current_user is u2


class TestSessionRoles:
    @pytest.mark.parametrize("role", [
        "admin", "instructor", "student", "candidate", "company", "expert"
    ])
    def test_all_roles(self, role):
        s = SessionManager.instance()
        s.start_session(_make_user(role))
        assert s.role == role
