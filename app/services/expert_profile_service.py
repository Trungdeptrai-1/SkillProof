"""
ExpertProfileService — Quản lý hồ sơ chuyên gia.

Nguyên tắc:
- Chỉ role='expert' được sử dụng các phương thức này.
- user_id lấy từ SessionManager, không tin giá trị truyền từ UI.
- Parameterized query — tránh SQL Injection.
- is_verified chỉ Admin mới thay đổi (không qua service này).
- hourly_rate là REAL trong DB; kiểm tra NaN/Infinity/âm trước khi lưu.
- availability: 'available' | 'busy' | 'unavailable' — đúng CHECK constraint.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass

from app.database.connection import db
from app.services.auth_service import SessionManager

logger = logging.getLogger(__name__)

# Hằng số nghiệp vụ
AVAILABILITY_VALUES = ("available", "busy", "unavailable")
AVAILABILITY_LABELS = {
    "available":   "Sẵn sàng",
    "busy":        "Đang bận",
    "unavailable": "Không khả dụng",
}
TITLE_MAX_LEN    = 200
BIO_MAX_LEN      = 2000
SPEC_MAX_LEN     = 300
MAX_HOURLY_RATE  = 100_000_000  # 100 triệu VNĐ — giới hạn hợp lý


# ══════════════════════════════════════════════════════════════════════════════
# DTO
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExpertProfileModel:
    """Đại diện cho một hàng trong bảng expert_profiles + thông tin user."""
    id:             int
    user_id:        int
    title:          str
    bio:            str | None
    specialization: str | None
    hourly_rate:    float | None
    availability:   str
    is_verified:    bool
    created_at:     str
    updated_at:     str
    # Read-only từ bảng users
    full_name:      str
    email:          str

    @classmethod
    def from_row(cls, row) -> "ExpertProfileModel":
        return cls(
            id             = row["id"],
            user_id        = row["user_id"],
            title          = row["title"],
            bio            = row["bio"],
            specialization = row["specialization"],
            hourly_rate    = float(row["hourly_rate"]) if row["hourly_rate"] is not None else None,
            availability   = row["availability"],
            is_verified    = bool(row["is_verified"]),
            created_at     = row["created_at"],
            updated_at     = row["updated_at"],
            full_name      = row["full_name"],
            email          = row["email"],
        )

    @property
    def availability_label(self) -> str:
        return AVAILABILITY_LABELS.get(self.availability, self.availability)

    @property
    def hourly_rate_display(self) -> str:
        """Định dạng mức phí để hiển thị, tránh lỗi số thực."""
        if self.hourly_rate is None:
            return "Chưa cập nhật"
        # Làm tròn tới đơn vị VNĐ (không có phần thập phân)
        rate = round(self.hourly_rate)
        return f"{rate:,} VNĐ/giờ".replace(",", ".")

    def __repr__(self) -> str:
        return (
            f"ExpertProfileModel(id={self.id}, user_id={self.user_id}, "
            f"title={self.title!r}, availability={self.availability!r})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Result
# ══════════════════════════════════════════════════════════════════════════════

class ExpertProfileResult:
    """Kết quả trả về từ ExpertProfileService."""

    SUCCESS              = "success"
    NOT_LOGGED_IN        = "not_logged_in"
    WRONG_ROLE           = "wrong_role"
    NOT_FOUND            = "not_found"
    ALREADY_EXISTS       = "already_exists"
    EMPTY_TITLE          = "empty_title"
    TITLE_TOO_LONG       = "title_too_long"
    INVALID_HOURLY_RATE  = "invalid_hourly_rate"
    NEGATIVE_HOURLY_RATE = "negative_hourly_rate"
    INVALID_AVAILABILITY = "invalid_availability"
    DB_ERROR             = "db_error"

    MESSAGES: dict[str, str] = {
        SUCCESS:              "Thao tác thành công.",
        NOT_LOGGED_IN:        "Vui lòng đăng nhập trước.",
        WRONG_ROLE:           "Chức năng này chỉ dành cho tài khoản chuyên gia.",
        NOT_FOUND:            "Chưa có hồ sơ chuyên gia. Vui lòng tạo mới.",
        ALREADY_EXISTS:       "Hồ sơ chuyên gia đã tồn tại.",
        EMPTY_TITLE:          "Tiêu đề chuyên môn không được để trống.",
        TITLE_TOO_LONG:       f"Tiêu đề chuyên môn không được vượt quá {TITLE_MAX_LEN} ký tự.",
        INVALID_HOURLY_RATE:  "Mức phí theo giờ không hợp lệ (phải là số hữu hạn, không âm).",
        NEGATIVE_HOURLY_RATE: "Mức phí theo giờ không được âm.",
        INVALID_AVAILABILITY: "Trạng thái không hợp lệ. Chọn: Sẵn sàng / Đang bận / Không khả dụng.",
        DB_ERROR:             "Lỗi cơ sở dữ liệu. Vui lòng thử lại.",
    }

    def __init__(self, status: str, profile: ExpertProfileModel | None = None) -> None:
        self.status  = status
        self.profile = profile
        self.success = (status == self.SUCCESS)
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")

    def __repr__(self) -> str:
        return f"ExpertProfileResult(status={self.status!r}, profile={self.profile!r})"


# ══════════════════════════════════════════════════════════════════════════════
# Service
# ══════════════════════════════════════════════════════════════════════════════

class ExpertProfileService:
    """
    Service quản lý hồ sơ chuyên gia.

    Bảo mật:
    - Lấy user_id từ SessionManager.instance().current_user.id
    - Kiểm tra role == 'expert' trước mỗi thao tác
    - Không cho phép Candidate/Company/Admin dùng service này
    - is_verified, user_id không thể thay đổi qua service này
    - hourly_rate: kiểm tra NaN/Infinity/âm trước khi lưu
    """

    def _get_current_user(self) -> ExpertProfileResult | None:
        """Kiểm tra phiên đăng nhập + role."""
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return ExpertProfileResult(ExpertProfileResult.NOT_LOGGED_IN)
        if session.current_user.role != "expert":
            return ExpertProfileResult(ExpertProfileResult.WRONG_ROLE)
        return None

    def _validate_inputs(
        self,
        title: str,
        hourly_rate: float | None,
        availability: str,
    ) -> ExpertProfileResult | None:
        """
        Validate đầu vào. Trả về Result lỗi hoặc None nếu OK.
        """
        # title
        title = title.strip()
        if not title:
            return ExpertProfileResult(ExpertProfileResult.EMPTY_TITLE)
        if len(title) > TITLE_MAX_LEN:
            return ExpertProfileResult(ExpertProfileResult.TITLE_TOO_LONG)

        # hourly_rate — kiểm tra NaN, Infinity, âm
        if hourly_rate is not None:
            try:
                rate = float(hourly_rate)
            except (TypeError, ValueError):
                return ExpertProfileResult(ExpertProfileResult.INVALID_HOURLY_RATE)
            if not math.isfinite(rate):
                return ExpertProfileResult(ExpertProfileResult.INVALID_HOURLY_RATE)
            if rate < 0:
                return ExpertProfileResult(ExpertProfileResult.NEGATIVE_HOURLY_RATE)
            if rate > MAX_HOURLY_RATE:
                return ExpertProfileResult(ExpertProfileResult.INVALID_HOURLY_RATE)

        # availability
        if availability not in AVAILABILITY_VALUES:
            return ExpertProfileResult(ExpertProfileResult.INVALID_AVAILABILITY)

        return None

    def _fetch_profile(self, user_id: int) -> ExpertProfileModel | None:
        """Truy vấn profile + user info, trả về model hoặc None."""
        row = db.fetchone(
            """
            SELECT ep.*, u.full_name, u.email
            FROM expert_profiles ep
            JOIN users u ON ep.user_id = u.id
            WHERE ep.user_id = ?
            """,
            (user_id,),
        )
        return ExpertProfileModel.from_row(row) if row else None

    # ── GET ───────────────────────────────────────────────────────────────────

    def get_profile(self) -> ExpertProfileResult:
        """Lấy hồ sơ của expert đang đăng nhập."""
        err = self._get_current_user()
        if err:
            return err

        user_id = SessionManager.instance().current_user.id
        try:
            profile = self._fetch_profile(user_id)
        except sqlite3.Error as exc:
            logger.error("DB error in get_profile: %s", exc)
            return ExpertProfileResult(ExpertProfileResult.DB_ERROR)

        if profile is None:
            return ExpertProfileResult(ExpertProfileResult.NOT_FOUND)

        return ExpertProfileResult(ExpertProfileResult.SUCCESS, profile=profile)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def create_profile(
        self,
        title: str,
        bio: str = "",
        specialization: str = "",
        hourly_rate: float | None = None,
        availability: str = "available",
    ) -> ExpertProfileResult:
        """Tạo hồ sơ chuyên gia mới."""
        err = self._get_current_user()
        if err:
            return err

        title = title.strip()
        bio = bio.strip()
        specialization = specialization.strip()

        err = self._validate_inputs(title, hourly_rate, availability)
        if err:
            return err

        user_id = SessionManager.instance().current_user.id

        # Kiểm tra trùng
        try:
            existing = db.fetchone(
                "SELECT id FROM expert_profiles WHERE user_id = ?",
                (user_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error checking existing expert profile: %s", exc)
            return ExpertProfileResult(ExpertProfileResult.DB_ERROR)

        if existing is not None:
            return ExpertProfileResult(ExpertProfileResult.ALREADY_EXISTS)

        # Chuẩn hóa hourly_rate — làm tròn tới VNĐ nguyên
        rate_to_save = round(float(hourly_rate)) if hourly_rate is not None else None

        try:
            db.execute(
                """
                INSERT INTO expert_profiles
                    (user_id, title, bio, specialization, hourly_rate, availability)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id,
                 title,
                 bio or None,
                 specialization or None,
                 rate_to_save,
                 availability),
            )
        except sqlite3.IntegrityError:
            return ExpertProfileResult(ExpertProfileResult.ALREADY_EXISTS)
        except sqlite3.Error as exc:
            logger.error("DB error in create_profile: %s", exc)
            return ExpertProfileResult(ExpertProfileResult.DB_ERROR)

        try:
            profile = self._fetch_profile(user_id)
        except Exception:
            return ExpertProfileResult(ExpertProfileResult.DB_ERROR)

        if profile:
            logger.info("Expert profile created: user_id=%d", user_id)
            return ExpertProfileResult(ExpertProfileResult.SUCCESS, profile=profile)

        return ExpertProfileResult(ExpertProfileResult.DB_ERROR)

    # ── UPDATE ────────────────────────────────────────────────────────────────

    def update_profile(
        self,
        title: str,
        bio: str = "",
        specialization: str = "",
        hourly_rate: float | None = None,
        availability: str = "available",
    ) -> ExpertProfileResult:
        """Cập nhật hồ sơ chuyên gia. Không cho phép thay đổi is_verified."""
        err = self._get_current_user()
        if err:
            return err

        title = title.strip()
        bio = bio.strip()
        specialization = specialization.strip()

        err = self._validate_inputs(title, hourly_rate, availability)
        if err:
            return err

        user_id = SessionManager.instance().current_user.id

        # Kiểm tra profile tồn tại
        try:
            existing = db.fetchone(
                "SELECT id FROM expert_profiles WHERE user_id = ?",
                (user_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error in update_profile check: %s", exc)
            return ExpertProfileResult(ExpertProfileResult.DB_ERROR)

        if existing is None:
            return ExpertProfileResult(ExpertProfileResult.NOT_FOUND)

        rate_to_save = round(float(hourly_rate)) if hourly_rate is not None else None

        # UPDATE — KHÔNG cập nhật is_verified, user_id
        try:
            db.execute(
                """
                UPDATE expert_profiles SET
                    title          = ?,
                    bio            = ?,
                    specialization = ?,
                    hourly_rate    = ?,
                    availability   = ?,
                    updated_at     = datetime('now','localtime')
                WHERE user_id = ?
                """,
                (title,
                 bio or None,
                 specialization or None,
                 rate_to_save,
                 availability,
                 user_id),
            )
        except sqlite3.Error as exc:
            logger.error("DB error in update_profile: %s", exc)
            return ExpertProfileResult(ExpertProfileResult.DB_ERROR)

        try:
            profile = self._fetch_profile(user_id)
        except Exception:
            return ExpertProfileResult(ExpertProfileResult.DB_ERROR)

        if profile:
            logger.info("Expert profile updated: user_id=%d", user_id)
            return ExpertProfileResult(ExpertProfileResult.SUCCESS, profile=profile)

        return ExpertProfileResult(ExpertProfileResult.DB_ERROR)


# ── Singleton ──────────────────────────────────────────────────────────────────
expert_profile_service = ExpertProfileService()
