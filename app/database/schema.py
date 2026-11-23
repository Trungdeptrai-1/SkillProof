"""Backward-compatible alias for the server schema module."""

import sys

from server.database import schema as _implementation
from server.database.schema import (
    SCHEMA_SQL,
    TRIGGERS_SQL,
    SEED_SQL,
    create_all_tables,
    drop_all_tables,
    is_first_run,
    mark_setup_done,
)

__all__ = [
    "SCHEMA_SQL",
    "TRIGGERS_SQL",
    "SEED_SQL",
    "create_all_tables",
    "drop_all_tables",
    "is_first_run",
    "mark_setup_done",
]

sys.modules[__name__] = _implementation
