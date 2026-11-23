"""First-run administrator setup service."""

from __future__ import annotations

import logging
import sqlite3

from app.database.connection import db
from app.database.schema import mark_setup_done
from app.utils.helpers import hash_password, is_strong_password, is_valid_email

logger = logging.getLogger(__name__)


class AdminSetupResult:
    SUCCESS = "success"
    EMPTY_FULL_NAME = "empty_full_name"
    INVALID_EMAIL = "invalid_email"
    WEAK_PASSWORD = "weak_password"
    PASSWORD_MISMATCH = "password_mismatch"
    EMAIL_ALREADY_USED = "email_already_used"
    DB_ERROR = "db_error"

    MESSAGES = {
        SUCCESS: "Thiết lập hoàn tất! Đang chuyển sang đăng nhập...",
        EMPTY_FULL_NAME: "Vui lòng nhập họ và tên.",
        INVALID_EMAIL: "Địa chỉ email không hợp lệ.",
        WEAK_PASSWORD: "Mật khẩu không đủ mạnh.",
        PASSWORD_MISMATCH: "Mật khẩu xác nhận không khớp.",
        EMAIL_ALREADY_USED: "Email này đã được sử dụng.",
        DB_ERROR: "Không thể hoàn tất thiết lập admin. Vui lòng thử lại.",
    }

    def __init__(self, status: str) -> None:
        self.status = status
        self.success = status == self.SUCCESS
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")


class AdminSetupService:
    """Create the initial admin account and mark setup complete atomically."""

    def create_admin(
        self,
        full_name: str,
        email: str,
        password: str,
        confirm_password: str,
    ) -> AdminSetupResult:
        full_name = full_name.strip()
        email = email.strip()

        if not full_name:
            return AdminSetupResult(AdminSetupResult.EMPTY_FULL_NAME)
        if not is_valid_email(email):
            return AdminSetupResult(AdminSetupResult.INVALID_EMAIL)
        is_strong, _reason = is_strong_password(password)
        if not is_strong:
            return AdminSetupResult(AdminSetupResult.WEAK_PASSWORD)
        if password != confirm_password:
            return AdminSetupResult(AdminSetupResult.PASSWORD_MISMATCH)

        try:
            if db.fetchone("SELECT id FROM users WHERE email = ?", (email,)):
                return AdminSetupResult(AdminSetupResult.EMAIL_ALREADY_USED)

            username = email.split("@", 1)[0]
            if db.fetchone("SELECT id FROM users WHERE username = ?", (username,)):
                username = f"{username}_admin"

            connection = db.get_connection()
            with connection:
                connection.execute(
                    """
                    INSERT INTO users
                        (username, email, password, full_name, role, is_active)
                    VALUES (?, ?, ?, ?, 'admin', 1)
                    """,
                    (username, email, hash_password(password), full_name),
                )
                mark_setup_done(connection)
        except sqlite3.IntegrityError as exc:
            logger.warning("Admin setup rejected by database constraint: %s", exc)
            return AdminSetupResult(AdminSetupResult.DB_ERROR)
        except sqlite3.Error as exc:
            logger.error("Database error during admin setup: %s", exc)
            return AdminSetupResult(AdminSetupResult.DB_ERROR)

        logger.info("First-run admin setup completed.")
        return AdminSetupResult(AdminSetupResult.SUCCESS)
