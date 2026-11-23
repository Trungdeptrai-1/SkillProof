"""
AuthService — Xác thực người dùng và quản lý phiên đăng nhập.

Nguyên tắc bảo mật:
- Không lưu/log mật khẩu dạng plain text ở bất kỳ đâu.
- Parameterized query — tránh SQL Injection.
- hmac.compare_digest trong verify_password — tránh timing attack.
- verify_password luôn chạy kể cả khi user không tồn tại (dummy hash)
  để tránh timing difference tiết lộ email có tồn tại hay không.
- is_active check SAU verify_password để đồng đều thời gian phản hồi.
- Lazy rehash: nâng cấp hash cũ (legacy SHA-256) → PBKDF2 ngay khi login thành công.
- SessionManager lưu trạng thái trong bộ nhớ (in-process singleton).
"""

from __future__ import annotations

import logging
import sqlite3

from app.database.connection import db
from app.models.user_model import UserModel
from app.utils.helpers import (
    verify_password, is_valid_email, hash_password, needs_rehash,
)

logger = logging.getLogger(__name__)

# Dummy hash dùng để cân bằng thời gian khi email không tồn tại
# Tránh timing attack phân biệt "email không tồn tại" vs "sai mật khẩu"
_DUMMY_HASH = (
    "pbkdf2:sha256:600000:"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=:"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
)


# ══════════════════════════════════════════════════════════════════════════════
# Kết quả xác thực
# ══════════════════════════════════════════════════════════════════════════════

class LoginResult:
    """Kết quả trả về từ AuthService.login()."""

    SUCCESS              = "success"
    EMPTY_EMAIL          = "empty_email"
    EMPTY_PASSWORD       = "empty_password"
    INVALID_EMAIL_FORMAT = "invalid_email_format"
    USER_NOT_FOUND       = "user_not_found"
    WRONG_PASSWORD       = "wrong_password"
    ACCOUNT_INACTIVE     = "account_inactive"
    DB_ERROR             = "db_error"

    # Thông báo thân thiện — USER_NOT_FOUND và WRONG_PASSWORD cùng thông báo
    # để không tiết lộ email có tồn tại hay không
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
        self.user    = user
        self.success = (status == self.SUCCESS)
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")

    def __repr__(self) -> str:
        return f"LoginResult(status={self.status!r}, user={self.user!r})"


# ══════════════════════════════════════════════════════════════════════════════
# SessionManager — Singleton in-memory
# ══════════════════════════════════════════════════════════════════════════════

class SessionManager:
    """Quản lý phiên đăng nhập trong bộ nhớ — Singleton."""

    _instance: "SessionManager | None" = None

    def __new__(cls) -> "SessionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_user: UserModel | None = None
        return cls._instance

    @property
    def current_user(self) -> UserModel | None:
        return self._current_user

    @property
    def is_logged_in(self) -> bool:
        return self._current_user is not None

    @property
    def role(self) -> str | None:
        return self._current_user.role if self._current_user else None

    def start_session(self, user: UserModel) -> None:
        self._current_user = user
        logger.info("Session started: user_id=%d, role=%s", user.id, user.role)

    def end_session(self) -> None:
        if self._current_user:
            logger.info("Session ended: user_id=%d", self._current_user.id)
        self._current_user = None

    @classmethod
    def instance(cls) -> "SessionManager":
        return cls()


# ══════════════════════════════════════════════════════════════════════════════
# AuthService
# ══════════════════════════════════════════════════════════════════════════════

class AuthService:
    """
    Logic xác thực theo thứ tự:
    1. Validate đầu vào
    2. Truy vấn DB (parameterized)
    3. verify_password (LUÔN chạy — dummy hash nếu user không tồn tại)
    4. Kiểm tra is_active (SAU verify để đồng đều thời gian)
    5. Lazy rehash nếu hash cũ (legacy)
    6. Tạo session
    """

    def login(self, email: str, password: str) -> LoginResult:
        # ── 1. Validate ──────────────────────────────────────────────────────
        email = email.strip()
        if not email:
            return LoginResult(LoginResult.EMPTY_EMAIL)
        if not password:
            return LoginResult(LoginResult.EMPTY_PASSWORD)
        if not is_valid_email(email):
            return LoginResult(LoginResult.INVALID_EMAIL_FORMAT)

        # ── 2. Truy vấn DB ───────────────────────────────────────────────────
        try:
            row = db.fetchone(
                """
                SELECT id, username, email, password, full_name,
                       role, avatar_path, is_active, created_at, updated_at
                FROM users WHERE email = ?
                """,
                (email,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error during login: %s", exc)
            return LoginResult(LoginResult.DB_ERROR)
        except Exception as exc:
            logger.exception("Unexpected login error: %s", exc)
            return LoginResult(LoginResult.DB_ERROR)

        # ── 3. verify_password — LUÔN chạy (dummy nếu không tìm thấy) ───────
        #    Đảm bảo thời gian phản hồi đồng đều, không tiết lộ email tồn tại.
        stored_hash  = row["password"] if row is not None else _DUMMY_HASH
        pw_ok        = verify_password(password, stored_hash)

        # ── 4. Xác định kết quả theo thứ tự ưu tiên ─────────────────────────
        if row is None:
            # Verify đã chạy xong (constant time), giờ mới return
            logger.warning("Login: email not found (masked)")
            return LoginResult(LoginResult.USER_NOT_FOUND)

        if not pw_ok:
            logger.warning("Login: wrong password for user_id=%d", row["id"])
            return LoginResult(LoginResult.WRONG_PASSWORD)

        # is_active check SAU verify — nhất quán thời gian
        if not bool(row["is_active"]):
            logger.warning("Login: inactive account user_id=%d", row["id"])
            return LoginResult(LoginResult.ACCOUNT_INACTIVE)

        # ── 5. Lazy rehash — nâng cấp hash cũ lên PBKDF2 ────────────────────
        if needs_rehash(stored_hash):
            self._rehash_password(row["id"], password)

        # ── 6. Tạo session ───────────────────────────────────────────────────
        user = UserModel.from_row(row)
        SessionManager.instance().start_session(user)
        logger.info("Login successful: user_id=%d, role=%s", user.id, user.role)
        return LoginResult(LoginResult.SUCCESS, user=user)

    def logout(self) -> None:
        """Kết thúc phiên hiện tại."""
        SessionManager.instance().end_session()

    def _rehash_password(self, user_id: int, plain_password: str) -> None:
        """
        Nâng cấp hash cũ (legacy SHA-256) lên PBKDF2-SHA256.
        Gọi sau khi verify thành công — không bao giờ log plain_password.
        """
        try:
            new_hash = hash_password(plain_password)
            db.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (new_hash, user_id),
            )
            logger.info("Password rehashed for user_id=%d (legacy→PBKDF2)", user_id)
        except Exception as exc:
            # Không crash login nếu rehash thất bại — chỉ log warning
            logger.warning("Rehash failed for user_id=%d: %s", user_id, exc)


# ── Singleton shortcuts ───────────────────────────────────────────────────────
auth_service = AuthService()
session      = SessionManager.instance()
