"""Data Transfer Object for a row in the app_settings table."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3


@dataclass
class AppSettingModel:
    """Represents one persisted application setting."""

    key: str
    value: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> AppSettingModel:
        return cls(
            key=row["key"],
            value=row["value"],
            updated_at=row["updated_at"],
        )
