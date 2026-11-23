"""Data Transfer Object for a row in the skills table."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3


@dataclass
class SkillModel:
    """Represents a skill that can be enabled or disabled by an administrator."""

    id: int
    name: str
    description: str | None
    category: str | None
    level: str
    is_active: bool
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> SkillModel:
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            category=row["category"],
            level=row["level"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )
