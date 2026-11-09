"""
UserService — Quản lý tài khoản người dùng (đăng ký, cập nhật hồ sơ).

Nguyên tắc:
- Không lưu/log mật khẩu dạng plain text.
- Parameterized query — tránh SQL Injection.
- Role mặc định là 'candidate' — người dùng không tự chọn role.
- Xử lý mọi ngoại lệ DB — ứng dụng không crash.
"""

from __future__ import annotations

import logging
import sqlite3

from app.database.connection import db
from app.models.user_model import UserModel
from app.utils.helpers import hash_password, is_valid_email, is_strong_password

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Kết quả đăng ký
# ══════════════════════════════════════════════════════════════════════════════

class RegisterResult:
    """Kết quả trả về từ UserService.register()."""

    SUCCESS              = "success"
    EMPTY_FULL_NAME      = "empty_full_name"
    EMPTY_EMAIL          = "empty_email"
    EMPTY_PASSWORD       = "empty_password"
    EMPTY_CONFIRM        = "empty_confirm"
    INVALID_EMAIL_FORMAT = "invalid_email_format"
    WEAK_PASSWORD        = "weak_password"
    PASSWORD_MISMATCH    = "password_mismatch"
    EMAIL_ALREADY_USED   = "email_already_used"
    DB_ERROR             = "db_error"

    MESSAGES: dict[str, str] = {
        SUCCESS:              "Đăng ký thành công! Vui lòng đăng nhập.",
        EMPTY_FULL_NAME:      "Vui lòng nhập họ và tên.",
        EMPTY_EMAIL:          "Vui lòng nhập địa chỉ email.",
        EMPTY_PASSWORD:       "Vui lòng nhập mật khẩu.",
        EMPTY_CONFIRM:        "Vui lòng xác nhận mật khẩu.",
        INVALID_EMAIL_FORMAT: "Địa chỉ email không đúng định dạng.",
        WEAK_PASSWORD:        "Mật khẩu không đủ mạnh.",
        PASSWORD_MISMATCH:    "Mật khẩu xác nhận không khớp.",
        EMAIL_ALREADY_USED:   "Email này đã được sử dụng. Vui lòng chọn email khác.",
        DB_ERROR:             "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại.",
    }

    def __init__(self, status: str, user: UserModel | None = None) -> None:
        self.status  = status
        self.user    = user
        self.success = (status == self.SUCCESS)
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")

    def __repr__(self) -> str:
        return f"RegisterResult(status={self.status!r}, user={self.user!r})"


# ══════════════════════════════════════════════════════════════════════════════
# UserService
# ══════════════════════════════════════════════════════════════════════════════

class UserService:
    """
    Service quản lý tài khoản người dùng.

    register(): tạo tài khoản ứng viên (candidate).
    Không cho phép người dùng tự chọn role — luôn là 'candidate'.
    """

    def register(
        self,
        full_name: str,
        email: str,
        password: str,
        confirm_password: str,
    ) -> RegisterResult:
        """
        Đăng ký tài khoản ứng viên mới.

        Thứ tự kiểm tra:
        1. Validate đầu vào (trống, định dạng, độ mạnh, khớp)
        2. Kiểm tra email đã tồn tại trong DB
        3. Hash mật khẩu (PBKDF2-SHA256)
        4. INSERT vào users với role='candidate'
        5. Trả về RegisterResult

        Trả về RegisterResult — không raise exception ra ngoài.
        """
        # ── 1. Validate đầu vào ────────────────────────────────────────────────
        full_name = full_name.strip()
        email     = email.strip()
        password  = password  # Không strip — mật khẩu có thể có space
        confirm   = confirm_password

        if not full_name:
            return RegisterResult(RegisterResult.EMPTY_FULL_NAME)

        if not email:
            return RegisterResult(RegisterResult.EMPTY_EMAIL)

        if not password:
            return RegisterResult(RegisterResult.EMPTY_PASSWORD)

        if not confirm:
            return RegisterResult(RegisterResult.EMPTY_CONFIRM)

        if not is_valid_email(email):
            return RegisterResult(RegisterResult.INVALID_EMAIL_FORMAT)

        ok_pw, pw_reason = is_strong_password(password)
        if not ok_pw:
            return RegisterResult(RegisterResult.WEAK_PASSWORD, )

        if password != confirm:
            return RegisterResult(RegisterResult.PASSWORD_MISMATCH)

        # ── 2. Kiểm tra email trùng ────────────────────────────────────────────
        try:
            existing = db.fetchone(
                "SELECT id FROM users WHERE email = ?",
                (email,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error during register check: %s", exc)
            return RegisterResult(RegisterResult.DB_ERROR)
        except Exception as exc:
            logger.exception("Unexpected error during register: %s", exc)
            return RegisterResult(RegisterResult.DB_ERROR)

        if existing is not None:
            logger.warning("Register: email already used (masked)")
            return RegisterResult(RegisterResult.EMAIL_ALREADY_USED)

        # ── 3. Hash mật khẩu ───────────────────────────────────────────────────
        pw_hash = hash_password(password)

        # ── 4. Tạo username từ email (phần trước @) ────────────────────────────
        username = email.split("@")[0]
        # Đảm bảo username unique — thêm suffix nếu trùng
        try:
            uname_check = db.fetchone(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            )
        except Exception:
            uname_check = None

        if uname_check is not None:
            username = f"{username}_{db.fetchone('SELECT COALESCE(MAX(id),0)+1 FROM users').fetchone()[0]}"

        # ── 5. INSERT vào DB ────────────────────────────────────────────────────
        try:
            db.execute(
                """
                INSERT INTO users (username, email, password, full_name, role, is_active)
                VALUES (?, ?, ?, ?, 'candidate', 1)
                """,
                (username, email, pw_hash, full_name),
            )
        except sqlite3.IntegrityError as exc:
            # Race condition: email hoặc username bị trùng giữa check và insert
            logger.warning("Register: integrity error (race condition): %s", exc)
            return RegisterResult(RegisterResult.EMAIL_ALREADY_USED)
        except sqlite3.Error as exc:
            logger.error("DB error during register insert: %s", exc)
            return RegisterResult(RegisterResult.DB_ERROR)
        except Exception as exc:
            logger.exception("Unexpected error during register insert: %s", exc)
            return RegisterResult(RegisterResult.DB_ERROR)

        # ── 6. Lấy user vừa tạo để trả về ──────────────────────────────────────
        try:
            row = db.fetchone(
                """
                SELECT id, username, email, full_name, role,
                       avatar_path, is_active, created_at, updated_at
                FROM users WHERE email = ?
                """,
                (email,),
            )
            user = UserModel.from_row(row) if row else None
        except Exception:
            user = None

        logger.info(
            "Register successful: email=%s, role=candidate (user_id logged separately)"
        )
        # Log user_id nếu có, không log email/password
        if user:
            logger.info("New candidate registered: user_id=%d", user.id)

        return RegisterResult(RegisterResult.SUCCESS, user=user)


# ── Singleton shortcut ────────────────────────────────────────────────────────
user_service = UserService()
