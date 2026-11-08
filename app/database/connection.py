"""
Quản lý kết nối SQLite cho SkillProof.
Sử dụng pattern Singleton để đảm bảo chỉ có một kết nối duy nhất.
"""

import sqlite3
import logging
import os

from app.utils.constants import DB_PATH, DATA_DIR

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Singleton quản lý kết nối SQLite."""

    _instance: "DatabaseConnection | None" = None
    _connection: sqlite3.Connection | None = None

    def __new__(cls) -> "DatabaseConnection":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ── Kết nối / Ngắt kết nối ───────────────────────────────────────────────

    def connect(self) -> sqlite3.Connection:
        """Mở kết nối tới CSDL, tạo file nếu chưa tồn tại."""
        if self._connection is None:
            os.makedirs(DATA_DIR, exist_ok=True)
            self._connection = sqlite3.connect(
                DB_PATH,
                check_same_thread=False,
            )
            # Trả về dict thay vì tuple khi fetch rows
            self._connection.row_factory = sqlite3.Row
            # Bật foreign key constraints
            self._connection.execute("PRAGMA foreign_keys = ON;")
            self._connection.execute("PRAGMA journal_mode = WAL;")
            logger.info("Đã kết nối SQLite: %s", DB_PATH)
        return self._connection

    def close(self) -> None:
        """Đóng kết nối CSDL."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Đã đóng kết nối SQLite.")

    def get_connection(self) -> sqlite3.Connection:
        """Trả về kết nối hiện tại, tự mở nếu chưa có."""
        if self._connection is None:
            return self.connect()
        return self._connection

    # ── Tiện ích ─────────────────────────────────────────────────────────────

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Thực thi câu lệnh SQL không trả dữ liệu (INSERT/UPDATE/DELETE)."""
        conn = self.get_connection()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Thực thi SELECT, trả về tất cả hàng."""
        conn = self.get_connection()
        cursor = conn.execute(sql, params)
        return cursor.fetchall()

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        """Thực thi SELECT, trả về một hàng duy nhất."""
        conn = self.get_connection()
        cursor = conn.execute(sql, params)
        return cursor.fetchone()


# Shortcut singleton
db = DatabaseConnection()
