# -*- coding: utf-8 -*-
"""
Regression tests: Giai đoạn 00 + 01 vẫn hoạt động sau Giai đoạn 01.1.
"""

import pytest
from app.utils.helpers import (
    hash_password, verify_password, needs_rehash,
    is_valid_email, is_valid_phone, is_strong_password,
    now_str, format_date,
)
from app.utils.constants import (
    APP_NAME, APP_VERSION, COLOR_ACCENT, FONT_FAMILY,
    WINDOW_MIN_WIDTH, WINDOW_DEFAULT_WIDTH,
)
from app.utils.styles import (
    GLOBAL_STYLE, INPUT_STYLE, CARD_STYLE,
    primary_button_style, secondary_button_style, ghost_button_style,
    STATUS_SUCCESS_STYLE, STATUS_ERROR_STYLE,
)
from app.models.user_model import UserModel, ROLE_LABELS, ROLE_ICONS
from datetime import datetime


class TestPhase00Helpers:
    def test_format_date_none(self):
        assert format_date(None) == "—"

    def test_format_date_value(self):
        dt = datetime(2024, 1, 15)
        assert format_date(dt) == "15/01/2024"

    def test_now_str_iso(self):
        s = now_str()
        datetime.fromisoformat(s)

    def test_is_valid_email_valid(self):
        assert is_valid_email("user@example.com")
        assert is_valid_email("a.b+c@sub.domain.org")

    def test_is_valid_email_invalid(self):
        assert not is_valid_email("bad")
        assert not is_valid_email("@domain.com")
        assert not is_valid_email("user@")

    def test_is_valid_phone_valid(self):
        assert is_valid_phone("0912345678")
        assert is_valid_phone("0312345678")

    def test_is_valid_phone_invalid(self):
        assert not is_valid_phone("123")
        assert not is_valid_phone("1912345678")
        assert not is_valid_phone("09123456789")

    def test_is_strong_password_valid(self):
        ok, msg = is_strong_password("Abc12345")
        assert ok and msg == ""

    def test_is_strong_password_too_short(self):
        ok, msg = is_strong_password("Ab1")
        assert not ok and "8" in msg

    def test_is_strong_password_no_upper(self):
        ok, msg = is_strong_password("abc12345")
        assert not ok and "hoa" in msg

    def test_is_strong_password_no_digit(self):
        ok, msg = is_strong_password("AbcDefGh")
        assert not ok and "số" in msg


class TestPhase00Constants:
    def test_app_name(self):
        assert APP_NAME == "SkillProof"

    def test_app_version(self):
        assert APP_VERSION == "1.0.0"

    def test_color_accent(self):
        assert COLOR_ACCENT.startswith("#")

    def test_window_sizes(self):
        assert WINDOW_MIN_WIDTH == 1024
        assert WINDOW_DEFAULT_WIDTH > WINDOW_MIN_WIDTH


class TestPhase00Styles:
    def test_global_style_contains_font(self):
        assert "Segoe UI" in GLOBAL_STYLE

    def test_primary_button_style(self):
        s = primary_button_style()
        assert "QPushButton" in s
        assert "background-color" in s

    def test_secondary_button_style(self):
        s = secondary_button_style()
        assert "QPushButton" in s
        assert "border" in s

    def test_ghost_button_style(self):
        s = ghost_button_style()
        assert "QPushButton" in s

    def test_status_styles(self):
        assert "color" in STATUS_SUCCESS_STYLE
        assert "color" in STATUS_ERROR_STYLE

    def test_input_style(self):
        assert "QLineEdit" in INPUT_STYLE

    def test_card_style(self):
        assert "QFrame" in CARD_STYLE


class TestPhase01UserModel:
    def _mock_row(self, role="candidate"):
        class Row(dict):
            def __getitem__(self, k):
                return super().__getitem__(k)
        return Row({
            "id": 1, "username": "u", "email": "u@t.com",
            "full_name": "User Test", "role": role,
            "avatar_path": None, "is_active": 1,
            "created_at": "2026-01-01", "updated_at": "2026-01-01",
        })

    def test_from_row(self):
        u = UserModel.from_row(self._mock_row())
        assert u.email == "u@t.com"
        assert u.is_active is True

    def test_no_password_field(self):
        u = UserModel.from_row(self._mock_row())
        assert not hasattr(u, "password")

    def test_role_label(self):
        assert ROLE_LABELS["admin"] == "Quản trị viên"
        assert ROLE_LABELS["candidate"] == "Ứng viên"
        assert ROLE_LABELS["company"] == "Doanh nghiệp"
        assert ROLE_LABELS["expert"] == "Chuyên gia"

    def test_role_icon(self):
        assert ROLE_ICONS["admin"] == "⚙"
        for role in ["admin","instructor","student","candidate","company","expert"]:
            assert role in ROLE_ICONS

    def test_display_name_full(self):
        u = UserModel.from_row(self._mock_row())
        assert u.display_name == "User Test"

    def test_display_name_fallback(self):
        row = self._mock_row()
        row["full_name"] = "   "
        u = UserModel.from_row(row)
        assert u.display_name == "u"

    @pytest.mark.parametrize("role", [
        "admin","instructor","student","candidate","company","expert"
    ])
    def test_all_roles_have_label_and_icon(self, role):
        u = UserModel.from_row(self._mock_row(role))
        assert u.role_label != ""
        assert u.role_icon != ""


class TestPhase01PasswordHashing:
    """Regression: hash mới backward compat với legacy."""

    LEGACY_HASH = "67fc4c2b5fd9ce86517e9028decd7bf466cea58e256de52616597978d1270e56"

    def test_new_hash_verifies(self):
        h = hash_password("Test@Pass1")
        assert verify_password("Test@Pass1", h)

    def test_legacy_hash_still_verifies(self):
        assert verify_password("admin", self.LEGACY_HASH)

    def test_needs_rehash_new(self):
        assert not needs_rehash(hash_password("x"))

    def test_needs_rehash_legacy(self):
        assert needs_rehash(self.LEGACY_HASH)
