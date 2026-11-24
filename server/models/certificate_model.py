"""Certificate data model and verification status helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3


@dataclass(frozen=True, slots=True)
class CertificateModel:
    id: int
    user_id: int
    skill_id: int
    issued_at: str
    expires_at: str | None
    score: float | None
    status: str
    cert_code: str
    revoked_at: str | None
    revoked_by: int | None
    revocation_reason: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CertificateModel:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            skill_id=row["skill_id"],
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
            score=float(row["score"]) if row["score"] is not None else None,
            status=row["status"],
            cert_code=row["cert_code"],
            revoked_at=row["revoked_at"],
            revoked_by=row["revoked_by"],
            revocation_reason=row["revocation_reason"],
        )

    def is_valid_at(self, now: datetime | None = None) -> bool:
        if self.status != "active":
            return False
        if self.expires_at is None:
            return True
        try:
            expiration = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return False
        current = now or datetime.now(expiration.tzinfo)
        if expiration.tzinfo is None and current.tzinfo is not None:
            current = current.replace(tzinfo=None)
        elif expiration.tzinfo is not None and current.tzinfo is None:
            current = current.replace(tzinfo=expiration.tzinfo)
        return current < expiration
