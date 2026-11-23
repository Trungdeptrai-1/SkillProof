"""Aggregate statistics DTO for administrator dashboards."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class AdminStatisticsModel:
    """Maps aggregate query aliases to current database counts.

    ``total_users`` includes soft-deleted rows. Active and inactive counts
    exclude soft-deleted users; skill counts include active and inactive rows.
    """

    total_users: int
    active_users: int
    inactive_users: int
    deleted_users: int
    total_skills: int
    active_skills: int
    inactive_skills: int
    total_certificates: int
    total_courses: int
    total_enrollments: int
    total_assessments: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> AdminStatisticsModel:
        return cls(
            total_users=int(row["total_users"]),
            active_users=int(row["active_users"]),
            inactive_users=int(row["inactive_users"]),
            deleted_users=int(row["deleted_users"]),
            total_skills=int(row["total_skills"]),
            active_skills=int(row["active_skills"]),
            inactive_skills=int(row["inactive_skills"]),
            total_certificates=int(row["total_certificates"]),
            total_courses=int(row["total_courses"]),
            total_enrollments=int(row["total_enrollments"]),
            total_assessments=int(row["total_assessments"]),
        )
