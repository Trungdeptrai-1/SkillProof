"""Database package — kết nối SQLite và quản lý schema."""

from app.database.connection import db
from app.database.schema import create_all_tables

__all__ = ["db", "create_all_tables"]
