"""Backward-compatible alias for the server SQLite connection module."""

import sys

from server.database import connection as _implementation
from server.database.connection import DB_PATH, DATA_DIR, DatabaseConnection, db

__all__ = ["DB_PATH", "DATA_DIR", "DatabaseConnection", "db"]

# Keep monkeypatches and singleton state shared with the implementation module.
sys.modules[__name__] = _implementation
