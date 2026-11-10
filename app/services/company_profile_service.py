"""
CompanyProfileService — Quản lý hồ sơ doanh nghiệp.

Nguyên tắc:
- Chỉ role='company' được sử dụng các phương thức này.
- user_id lấy từ SessionManager, không tin giá trị truyền từ UI.
- Parameterized query — tránh SQL Injection.
- is_verified chỉ Admin mới thay đổi (không qua service này).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from app.database.connection import db
from app.services.auth_service import SessionManager

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DTO
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CompanyProfileModel:
    """Đại diện cho một hàng trong bảng company_profiles."""
    id:           int
    user_id:      int
    company_name: str
    industry:      str | None
    website:       str | None
    description:   str | None
    logo_path:     str | None
    tax_code:      str | None
    address:       str | None
    is_verified:  bool
    created_at:   str
    updated_at:   str

    @classmethod
    def from_row(cls, row) -> "CompanyProfileModel":
        return cls(
            id           = row["id"],
            user_id      = row["user_id"],
            company_name = row["company_name"],
            industry     = row["industry"],
            website      = row["website"],
            description  = row["description"],
            logo_path    = row["logo_path"],
            tax_code     = row["tax_code"],
            address      = row["address"],
            is_verified  = bool(row["is_verified"]),
            created_at   = row["created_at"],
            updated_at   = row["updated_at"],
        )

    def __repr__(self) -> str:
        return (
            f"CompanyProfileModel(id={self.id}, user_id={self.user_id}, "
            f"company_name={self.company_name!r}, verified={self.is_verified})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Result
# ══════════════════════════════════════════════════════════════════════════════

class ProfileResult:
    """Kết quả trả về từ CompanyProfileService."""

    SUCCESS             = "success"
    NOT_LOGGED_IN       = "not_logged_in"
    WRONG_ROLE          = "wrong_role"
    NOT_FOUND           = "not_found"
    ALREADY_EXISTS      = "already_exists"
    EMPTY_COMPANY_NAME  = "empty_company_name"
    INVALID_WEBSITE     = "invalid_website"
    DB_ERROR            = "db_error"

    MESSAGES: dict[str, str] = {
        SUCCESS:            "Thao tác thành công.",
        NOT_LOGGED_IN:      "Vui lòng đăng nhập trước.",
        WRONG_ROLE:         "Chức năng này chỉ dành cho tài khoản doanh nghiệp.",
        NOT_FOUND:          "Chưa có hồ sơ doanh nghiệp. Vui lòng tạo mới.",
        ALREADY_EXISTS:     "Hồ sơ doanh nghiệp đã tồn tại.",
        EMPTY_COMPANY_NAME: "Tên doanh nghiệp không được để trống.",
        INVALID_WEBSITE:    "Địa chỉ website không hợp lệ.",
        DB_ERROR:           "Lỗi cơ sở dữ liệu. Vui lòng thử lại.",
    }

    def __init__(self, status: str, profile: CompanyProfileModel | None = None) -> None:
        self.status  = status
        self.profile = profile
        self.success = (status == self.SUCCESS)
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")

    def __repr__(self) -> str:
        return f"ProfileResult(status={self.status!r}, profile={self.profile!r})"


# ══════════════════════════════════════════════════════════════════════════════
# Service
# ══════════════════════════════════════════════════════════════════════════════

class CompanyProfileService:
    """
    Service quản lý hồ sơ doanh nghiệp.

    Bảo mật:
    - Lấy user_id từ SessionManager.instance().current_user.id
    - Kiểm tra role == 'company' trước mỗi thao tác
    - Không cho phép Candidate/Expert/Admin dùng service này
      (Admin quản lý verification riêng, không qua service này)
    """

    def _get_current_user(self) -> ProfileResult | None:
        """
        Kiểm tra phiên đăng nhập + role.
        Trả về ProfileResult lỗi nếu không hợp lệ, None nếu OK.
        """
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return ProfileResult(ProfileResult.NOT_LOGGED_IN)
        if session.current_user.role != "company":
            return ProfileResult(ProfileResult.WRONG_ROLE)
        return None  # OK

    # ── GET: Xem hồ sơ ────────────────────────────────────────────────────────

    def get_profile(self) -> ProfileResult:
        """Lấy hồ sơ của company đang đăng nhập."""
        err = self._get_current_user()
        if err:
            return err

        user_id = SessionManager.instance().current_user.id
        try:
            row = db.fetchone(
                """SELECT * FROM company_profiles WHERE user_id = ?""",
                (user_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error in get_profile: %s", exc)
            return ProfileResult(ProfileResult.DB_ERROR)

        if row is None:
            return ProfileResult(ProfileResult.NOT_FOUND)

        return ProfileResult(ProfileResult.SUCCESS, profile=CompanyProfileModel.from_row(row))

    # ── CREATE: Tạo hồ sơ lần đầu ─────────────────────────────────────────────

    def create_profile(
        self,
        company_name: str,
        industry: str = "",
        website: str = "",
        description: str = "",
        tax_code: str = "",
        address: str = "",
    ) -> ProfileResult:
        """Tạo hồ sơ doanh nghiệp mới cho user đang đăng nhập."""
        err = self._get_current_user()
        if err:
            return err

        # Validate
        company_name = company_name.strip()
        if not company_name:
            return ProfileResult(ProfileResult.EMPTY_COMPANY_NAME)

        website = website.strip()
        if website and not self._is_valid_website(website):
            return ProfileResult(ProfileResult.INVALID_WEBSITE)

        user_id = SessionManager.instance().current_user.id

        # Kiểm tra đã có profile chưa
        try:
            existing = db.fetchone(
                "SELECT id FROM company_profiles WHERE user_id = ?",
                (user_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error checking existing profile: %s", exc)
            return ProfileResult(ProfileResult.DB_ERROR)

        if existing is not None:
            return ProfileResult(ProfileResult.ALREADY_EXISTS)

        # INSERT
        try:
            db.execute(
                """
                INSERT INTO company_profiles
                    (user_id, company_name, industry, website, description,
                     tax_code, address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, company_name,
                 industry.strip() or None,
                 website or None,
                 description.strip() or None,
                 tax_code.strip() or None,
                 address.strip() or None),
            )
        except sqlite3.IntegrityError:
            # Race condition — profile vừa bị tạo bởi request khác
            return ProfileResult(ProfileResult.ALREADY_EXISTS)
        except sqlite3.Error as exc:
            logger.error("DB error in create_profile: %s", exc)
            return ProfileResult(ProfileResult.DB_ERROR)

        # Lấy profile vừa tạo
        row = db.fetchone(
            "SELECT * FROM company_profiles WHERE user_id = ?",
            (user_id,),
        )
        if row:
            logger.info("Company profile created: user_id=%d", user_id)
            return ProfileResult(ProfileResult.SUCCESS, profile=CompanyProfileModel.from_row(row))

        return ProfileResult(ProfileResult.DB_ERROR)

    # ── UPDATE: Cập nhật hồ sơ ─────────────────────────────────────────────────

    def update_profile(
        self,
        company_name: str,
        industry: str = "",
        website: str = "",
        description: str = "",
        tax_code: str = "",
        address: str = "",
    ) -> ProfileResult:
        """Cập nhật hồ sơ doanh nghiệp của user đang đăng nhập."""
        err = self._get_current_user()
        if err:
            return err

        company_name = company_name.strip()
        if not company_name:
            return ProfileResult(ProfileResult.EMPTY_COMPANY_NAME)

        website = website.strip()
        if website and not self._is_valid_website(website):
            return ProfileResult(ProfileResult.INVALID_WEBSITE)

        user_id = SessionManager.instance().current_user.id

        # Kiểm tra profile tồn tại
        try:
            existing = db.fetchone(
                "SELECT id FROM company_profiles WHERE user_id = ?",
                (user_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error in update_profile check: %s", exc)
            return ProfileResult(ProfileResult.DB_ERROR)

        if existing is None:
            return ProfileResult(ProfileResult.NOT_FOUND)

        # UPDATE — không cho phép cập nhật is_verified qua service này
        try:
            db.execute(
                """
                UPDATE company_profiles SET
                    company_name = ?,
                    industry      = ?,
                    website       = ?,
                    description   = ?,
                    tax_code      = ?,
                    address       = ?,
                    updated_at    = datetime('now','localtime')
                WHERE user_id = ?
                """,
                (company_name,
                 industry.strip() or None,
                 website or None,
                 description.strip() or None,
                 tax_code.strip() or None,
                 address.strip() or None,
                 user_id),
            )
        except sqlite3.Error as exc:
            logger.error("DB error in update_profile: %s", exc)
            return ProfileResult(ProfileResult.DB_ERROR)

        # Lấy profile sau update
        row = db.fetchone(
            "SELECT * FROM company_profiles WHERE user_id = ?",
            (user_id,),
        )
        if row:
            logger.info("Company profile updated: user_id=%d", user_id)
            return ProfileResult(ProfileResult.SUCCESS, profile=CompanyProfileModel.from_row(row))

        return ProfileResult(ProfileResult.DB_ERROR)

    # ── Validate helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _is_valid_website(url: str) -> bool:
        """Kiểm tra website hợp lệ cơ bản."""
        if not url:
            return True  # Empty = optional
        lowered = url.lower()
        return (
            lowered.startswith("http://")
            or lowered.startswith("https://")
            or lowered.startswith("www.")
            or "." in lowered  # Fallback: domain.com
        )


# ── Singleton ──────────────────────────────────────────────────────────────────
company_profile_service = CompanyProfileService()
