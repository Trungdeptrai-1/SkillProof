"""
AuthService — Xác thực người dùng và quản lý phiên đăng nhập.

Nguyên tắc:
- Không lưu/log mật khẩu dạng plain text.
- Dùng parameterized query — tránh SQL Injection.
- Xử lý mọi ngoại lệ DB — ứng dụng không crash.
- SessionManager lưu trạng thái trong bộ nhớ (in-process singleton).
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Tuple

from app.database.connection import db
from app.models.user_model import UserModel
from app.utils.helpers import verify_password, is_valid_email

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Kết quả xác thực
# ══════════════════════════════════════════════════════════════════════════════

class LoginResult:
    """Kết quả trả về từ AuthService.login()."""

    SUCCESS             = "success"
    EMPTY_EMAIL         = "empty_email"
    EMPTY_PASSWORD      = "empty_password"
    INVALID_EMAIL_FORMAT = "invalid_email_format"
    USER_NOT_FOUND      = "user_not_found"
    WRONG_PASSWORD      = "wrong_password"
    ACCOUNT_INACTIVE    = "account_inactive"
    DB_ERROR            = "db_error"

    # Thông báo lỗi thân thiện (không tiết lộ thông tin nội bộ)
    MESSAGES: dict[str, str] = {
        SUCCESS:              "Đăng nhập thành công.",
        EMPTY_EMAIL:          "Vui lòng nhập địa chỉ email.",
        EMPTY_PASSWORD:       "Vui lòng nhập mật khẩu.",
        INVALID_EMAIL_FORMAT: "Địa chỉ email không đúng định dạng.",
        USER_NOT_FOUND:       "Email hoặc mật khẩu không chính xác.",
        WRONG_PASSWORD:       "Email hoặc mật khẩu không chính xác.",
        ACCOUNT_INACTIVE:     "Tài khoản đã bị vô hiệu hóa. Vui lòng liên hệ quản trị viên.",
        DB_ERROR:             "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại.",
    }

    def __init__(self, status: str, user: UserModel | None = None) -> None:
        self.status  = status
        self.user    = user           # Chỉ có giá trị khi status == SUCCESS
        self.success = (status == self.SUCCESS)
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")

    def __repr__(self) -> str:
        return f"LoginResult(status={self.status!r}, user={self.user!r})"


# ══════════════════════════════════════════════════════════════════════════════
# SessionManager — Singleton lưu trạng thái phiên trong bộ nhớ
# ══════════════════════════════════════════════════════════════════════════════

class SessionManager:
    """
    Quản lý phiên đăng nhập trong bộ nhớ ứng dụng.
    Singleton — dùng SessionManager.instance().
    """

    _instance: "SessionManager | None" = None

    def __new__(cls) -> "SessionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_user: UserModel | None = None
        return cls._instance

    # ── Truy cập ──────────────────────────────────────────────────────────────

    @property
    def current_user(self) -> UserModel | None:
        """Trả về user hiện đang đăng nhập, hoặc None."""
        return self._current_user

    @property
    def is_logged_in(self) -> bool:
        return self._current_user is not None

    @property
    def role(self) -> str | None:
        """Role của user hiện tại."""
        return self._current_user.role if self._current_user else None

    # ── Thao tác ──────────────────────────────────────────────────────────────

    def start_session(self, user: UserModel) -> None:
        """Lưu user vào session sau khi đăng nhập thành công."""
        self._current_user = user
        logger.info(
            "Session started: user_id=%d, role=%s",
            user.id, user.role
        )

    def end_session(self) -> None:
        """Xóa session khi đăng xuất."""
        if self._current_user:
            logger.info(
                "Session ended: user_id=%d, role=%s",
                self._current_user.id, self._current_user.role
            )
        self._current_user = None

    @classmethod
    def instance(cls) -> "SessionManager":
        """Truy cập singleton."""
        return cls()


# ══════════════════════════════════════════════════════════════════════════════
# AuthService — Logic xác thực
# ══════════════════════════════════════════════════════════════════════════════

class AuthService:
    """
    Xử lý đăng nhập: validate đầu vào → truy vấn DB → kiểm tra hash → tạo session.
    Không có state — tất cả phương thức có thể gọi độc lập.
    """

    def login(self, email: str, password: str) -> LoginResult:
        """
        Xác thực email + password.

        Thứ tự kiểm tra:
        1. Validate đầu vào (trống, định dạng)
        2. Truy vấn DB bằng parameterized query
        3. Kiểm tra is_active
        4. Verify password hash
        5. Tạo session nếu thành công

        Trả về LoginResult — không raise exception ra ngoài.
        """
        # 1. Validate đầu vào
        email    = email.strip()
        password = password  # Không strip — mật khẩu có thể có space hợp lệ

        if not email:
            return LoginResult(LoginResult.EMPTY_EMAIL)

        if not password:
            return LoginResult(LoginResult.EMPTY_PASSWORD)

        if not is_valid_email(email):
            return LoginResult(LoginResult.INVALID_EMAIL_FORMAT)

        # 2. Truy vấn DB — parameterized query, tránh SQL Injection
        try:
            row = db.fetchone(
                """
                SELECT id, username, email, password, full_name,
                       role, avatar_path, is_active, created_at, updated_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error during login query: %s", exc)
            return LoginResult(LoginResult.DB_ERROR)
        except Exception as exc:
            logger.exception("Unexpected error during login: %s", exc)
            return LoginResult(LoginResult.DB_ERROR)

        # 3. Không tìm thấy user
        if row is None:
            # Log cảnh báo không tiết lộ chi tiết ra ngoài
            logger.warning("Login attempt: email not found (masked for security)")
            return LoginResult(LoginResult.USER_NOT_FOUND)

        # 4. Kiểm tra tài khoản active TRƯỚC khi verify password
        #    (tránh timing attack tiết lộ tài khoản có tồn tại hay không)
        if not bool(row["is_active"]):
            logger.warning(
                "Login attempt on inactive account: user_id=%d", row["id"]
            )
            return LoginResult(LoginResult.ACCOUNT_INACTIVE)

        # 5. Verify password — KHÔNG log plain password
        stored_hash = row["password"]
        if not verify_password(password, stored_hash):
            logger.warning(
                "Login attempt: wrong password for user_id=%d", row["id"]
            )
            return LoginResult(LoginResult.WRONG_PASSWORD)

        # 6. Thành công — tạo UserModel (không có password)
        user = UserModel.from_row(row)
        SessionManager.instance().start_session(user)
        logger.info(
            "Login successful: user_id=%d, role=%s", user.id, user.role
        )
        return LoginResult(LoginResult.SUCCESS, user=user)

    def logout(self) -> None:
        """Kết thúc phiên hiện tại."""
        SessionManager.instance().end_session()


# ── Singleton shortcut ────────────────────────────────────────────────────────
auth_service = AuthService()
session      = SessionManager.instance()
