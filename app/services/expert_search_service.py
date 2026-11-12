"""
ExpertSearchService — Company tìm kiếm chuyên gia.

D2: Trả về profile_id (expert_profiles.id), không trả về user_id.
Thông tin hiển thị: title, specialization, availability, hourly_rate, is_verified.
Thông tin ẩn: email, full_name, users.id (trước khi hợp tác).

Khi Company gửi đề nghị qua ContractService.invite_expert(expert_profile_id),
service sẽ ánh xạ profile_id → user_id nội bộ.

Chỉ trả về Expert:
  - is_active=1, is_deleted=0
  - Chưa có hợp đồng pending/active với Company đang tìm
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.database.connection import db
from app.services.auth_service import SessionManager

logger = logging.getLogger(__name__)


@dataclass
class ExpertSearchResult:
    """DTO kết quả tìm kiếm — không chứa user_id (D2)."""
    profile_id:      int         # expert_profiles.id — dùng để invite
    title:           str
    specialization:  Optional[str]
    availability:    str
    hourly_rate:     Optional[float]
    is_verified:     bool

    @classmethod
    def from_row(cls, row) -> "ExpertSearchResult":
        rate = row["hourly_rate"]
        return cls(
            profile_id     = row["profile_id"],
            title          = row["title"],
            specialization = row["specialization"],
            availability   = row["availability"],
            hourly_rate    = round(float(rate)) if rate is not None and math.isfinite(float(rate)) else None,
            is_verified    = bool(row["is_verified"]),
        )

    @property
    def hourly_rate_display(self) -> str:
        if self.hourly_rate is None:
            return "Thỏa thuận"
        return f"{int(self.hourly_rate):,} VNĐ/giờ".replace(",", ".")


class SearchResult:
    SUCCESS      = "success"
    NOT_LOGGED_IN = "not_logged_in"
    WRONG_ROLE   = "wrong_role"
    DB_ERROR     = "db_error"

    MESSAGES: dict[str, str] = {
        SUCCESS:       "Tìm kiếm thành công.",
        NOT_LOGGED_IN: "Vui lòng đăng nhập trước.",
        WRONG_ROLE:    "Chức năng này chỉ dành cho tài khoản doanh nghiệp.",
        DB_ERROR:      "Lỗi cơ sở dữ liệu. Vui lòng thử lại.",
    }

    def __init__(self, status: str, experts: list[ExpertSearchResult] | None = None) -> None:
        self.status  = status
        self.experts = experts or []
        self.success = (status == self.SUCCESS)
        self.message = self.MESSAGES.get(status, "Lỗi không xác định.")


class ExpertSearchService:
    """
    Tìm kiếm chuyên gia cho Company.
    Ẩn thông tin cá nhân, chỉ trả về dữ liệu chuyên môn công khai.
    """

    def search(
        self,
        specialization: str = "",
        availability: str | None = None,
        min_rate: float | None = None,
        max_rate: float | None = None,
        verified_only: bool = False,
    ) -> SearchResult:
        """
        Tìm kiếm Expert theo tiêu chí.
        Chỉ trả về Expert active, không bị soft-delete,
        chưa có hợp đồng pending/active với Company đang tìm.
        """
        s = SessionManager.instance()
        if not s.is_logged_in or s.current_user is None:
            return SearchResult(SearchResult.NOT_LOGGED_IN)
        if s.current_user.role != "company":
            return SearchResult(SearchResult.WRONG_ROLE)

        company_id = s.current_user.id

        # Build WHERE
        conditions = [
            "u.is_active = 1",
            "u.is_deleted = 0",
            # Loại trừ Expert đã có hợp đồng pending/active với Company này
            """NOT EXISTS (
                SELECT 1 FROM company_expert_contracts c
                WHERE c.company_id = ? AND c.expert_id = ep.user_id
                  AND c.status IN ('pending_expert','active')
            )""",
        ]
        params: list = [company_id]

        if specialization.strip():
            conditions.append("LOWER(ep.specialization) LIKE LOWER(?)")
            params.append(f"%{specialization.strip()}%")

        if availability and availability in ("available", "busy", "unavailable"):
            conditions.append("ep.availability = ?")
            params.append(availability)

        if min_rate is not None and math.isfinite(min_rate) and min_rate >= 0:
            conditions.append("(ep.hourly_rate IS NULL OR ep.hourly_rate >= ?)")
            params.append(round(min_rate))

        if max_rate is not None and math.isfinite(max_rate) and max_rate >= 0:
            conditions.append("(ep.hourly_rate IS NULL OR ep.hourly_rate <= ?)")
            params.append(round(max_rate))

        if verified_only:
            conditions.append("ep.is_verified = 1")

        where = " AND ".join(conditions)

        try:
            rows = db.fetchall(
                f"""
                SELECT
                    ep.id          AS profile_id,
                    ep.title,
                    ep.specialization,
                    ep.availability,
                    ep.hourly_rate,
                    ep.is_verified
                FROM expert_profiles ep
                JOIN users u ON u.id = ep.user_id
                WHERE {where}
                ORDER BY ep.is_verified DESC, ep.hourly_rate ASC
                """,
                tuple(params),
            )
        except sqlite3.Error as exc:
            logger.error("DB error in expert search: %s", exc)
            return SearchResult(SearchResult.DB_ERROR)

        experts = [ExpertSearchResult.from_row(r) for r in rows]
        return SearchResult(SearchResult.SUCCESS, experts=experts)


# ── Singleton ──────────────────────────────────────────────────────────────────
expert_search_service = ExpertSearchService()
