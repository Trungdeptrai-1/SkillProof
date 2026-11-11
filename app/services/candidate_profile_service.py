"""
CandidateProfileService — Quản lý hồ sơ ứng viên.

Nguyên tắc:
- Chỉ role='candidate' được sử dụng các phương thức này.
- user_id lấy từ SessionManager, không tin giá trị truyền từ UI.
- Parameterized query — tránh SQL Injection.
- Email và full_name từ bảng users — chỉ đọc, không cho phép thay đổi.
- CV (resume_path) lưu đường dẫn file PDF trong data/cvs/.
"""

from __future__ import annotations

import logging
import sqlite3
import os
import shutil
from dataclasses import dataclass

from app.database.connection import db
from app.services.auth_service import SessionManager
from app.utils import constants as consts

logger = logging.getLogger(__name__)

# ── CV storage ────────────────────────────────────────────────────────────────
MAX_CV_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CV_EXTENSIONS = {".pdf"}


# ══════════════════════════════════════════════════════════════════════════════
# DTO
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CandidateProfileModel:
    """Đại diện cho một hàng trong bảng candidate_profiles + thông tin user."""
    id:               int
    user_id:          int
    headline:         str | None
    bio:              str | None
    resume_path:      str | None
    portfolio_url:    str | None
    years_experience: int | None
    created_at:       str
    updated_at:        str
    # Read-only từ bảng users
    full_name:        str
    email:            str

    @classmethod
    def from_row(cls, row) -> "CandidateProfileModel":
        return cls(
            id               = row["id"],
            user_id          = row["user_id"],
            headline         = row["headline"],
            bio              = row["bio"],
            resume_path      = row["resume_path"],
            portfolio_url    = row["portfolio_url"],
            years_experience = row["years_experience"],
            created_at       = row["created_at"],
            updated_at       = row["updated_at"],
            full_name        = row["full_name"],
            email            = row["email"],
        )

    def __repr__(self) -> str:
        return (
            f"CandidateProfileModel(id={self.id}, user_id={self.user_id}, "
            f"headline={self.headline!r}, email={self.email!r})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Result
# ══════════════════════════════════════════════════════════════════════════════

class CandidateProfileResult:
    """Kết quả trả về từ CandidateProfileService."""

    SUCCESS              = "success"
    NOT_LOGGED_IN        = "not_logged_in"
    WRONG_ROLE           = "wrong_role"
    NOT_FOUND            = "not_found"
    ALREADY_EXISTS       = "already_exists"
    INVALID_PORTFOLIO    = "invalid_portfolio"
    INVALID_YEARS        = "invalid_years"
    CV_INVALID_FORMAT    = "cv_invalid_format"
    CV_TOO_LARGE         = "cv_too_large"
    CV_SAVE_ERROR        = "cv_save_error"
    DB_ERROR             = "db_error"

    MESSAGES: dict[str, str] = {
        SUCCESS:           "Thao tác thành công.",
        NOT_LOGGED_IN:     "Vui lòng đăng nhập trước.",
        WRONG_ROLE:        "Chức năng này chỉ dành cho tài khoản ứng viên.",
        NOT_FOUND:         "Chưa có hồ sơ ứng viên. Vui lòng tạo mới.",
        ALREADY_EXISTS:    "Hồ sơ ứng viên đã tồn tại.",
        INVALID_PORTFOLIO:  "Địa chỉ portfolio không hợp lệ.",
        INVALID_YEARS:     "Số năm kinh nghiệm phải là số không âm.",
        CV_INVALID_FORMAT: "Chỉ chấp nhận file PDF.",
        CV_TOO_LARGE:      "File CV vượt quá giới hạn 10MB.",
        CV_SAVE_ERROR:     "Không thể lưu file CV. Vui lòng thử lại.",
        DB_ERROR:          "Lỗi cơ sở dữ liệu. Vui lòng thử lại.",
    }

    def __init__(self, status: str, profile: CandidateProfileModel | None = None) -> None:
        self.status  = status
        self.profile = profile
        self.success = (status == self.SUCCESS)
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")

    def __repr__(self) -> str:
        return f"CandidateProfileResult(status={self.status!r}, profile={self.profile!r})"


# ══════════════════════════════════════════════════════════════════════════════
# Service
# ══════════════════════════════════════════════════════════════════════════════

class CandidateProfileService:
    """
    Service quản lý hồ sơ ứng viên.

    Bảo mật:
    - Lấy user_id từ SessionManager.instance().current_user.id
    - Kiểm tra role == 'candidate' trước mỗi thao tác
    - Không cho phép Company/Expert/Admin dùng service này
    - Email và full_name chỉ đọc — không cho phép thay đổi
    """

    def _get_current_user(self) -> CandidateProfileResult | None:
        """Kiểm tra phiên đăng nhập + role. Trả về Result lỗi hoặc None nếu OK."""
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return CandidateProfileResult(CandidateProfileResult.NOT_LOGGED_IN)
        if session.current_user.role != "candidate":
            return CandidateProfileResult(CandidateProfileResult.WRONG_ROLE)
        return None

    # ── GET: Xem hồ sơ ────────────────────────────────────────────────────────

    def get_profile(self) -> CandidateProfileResult:
        """Lấy hồ sơ của candidate đang đăng nhập + thông tin user (full_name, email)."""
        err = self._get_current_user()
        if err:
            return err

        user_id = SessionManager.instance().current_user.id
        try:
            row = db.fetchone(
                """
                SELECT cp.*, u.full_name, u.email
                FROM candidate_profiles cp
                JOIN users u ON cp.user_id = u.id
                WHERE cp.user_id = ?
                """,
                (user_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error in get_profile: %s", exc)
            return CandidateProfileResult(CandidateProfileResult.DB_ERROR)

        if row is None:
            return CandidateProfileResult(CandidateProfileResult.NOT_FOUND)

        return CandidateProfileResult(
            CandidateProfileResult.SUCCESS,
            profile=CandidateProfileModel.from_row(row),
        )

    # ── CREATE: Tạo hồ sơ lần đầu ─────────────────────────────────────────────

    def create_profile(
        self,
        headline: str = "",
        bio: str = "",
        portfolio_url: str = "",
        years_experience: int | None = None,
    ) -> CandidateProfileResult:
        """Tạo hồ sơ ứng viên mới cho user đang đăng nhập."""
        err = self._get_current_user()
        if err:
            return err

        # Validate
        portfolio_url = portfolio_url.strip()
        if portfolio_url and not self._is_valid_url(portfolio_url):
            return CandidateProfileResult(CandidateProfileResult.INVALID_PORTFOLIO)

        if years_experience is not None and years_experience < 0:
            return CandidateProfileResult(CandidateProfileResult.INVALID_YEARS)

        user_id = SessionManager.instance().current_user.id

        # Kiểm tra đã có profile chưa
        try:
            existing = db.fetchone(
                "SELECT id FROM candidate_profiles WHERE user_id = ?",
                (user_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error checking existing profile: %s", exc)
            return CandidateProfileResult(CandidateProfileResult.DB_ERROR)

        if existing is not None:
            return CandidateProfileResult(CandidateProfileResult.ALREADY_EXISTS)

        # INSERT
        try:
            db.execute(
                """
                INSERT INTO candidate_profiles
                    (user_id, headline, bio, portfolio_url, years_experience)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id,
                 headline.strip() or None,
                 bio.strip() or None,
                 portfolio_url or None,
                 years_experience),
            )
        except sqlite3.IntegrityError:
            return CandidateProfileResult(CandidateProfileResult.ALREADY_EXISTS)
        except sqlite3.Error as exc:
            logger.error("DB error in create_profile: %s", exc)
            return CandidateProfileResult(CandidateProfileResult.DB_ERROR)

        # Lấy profile vừa tạo
        row = db.fetchone(
            """
            SELECT cp.*, u.full_name, u.email
            FROM candidate_profiles cp
            JOIN users u ON cp.user_id = u.id
            WHERE cp.user_id = ?
            """,
            (user_id,),
        )
        if row:
            logger.info("Candidate profile created: user_id=%d", user_id)
            return CandidateProfileResult(
                CandidateProfileResult.SUCCESS,
                profile=CandidateProfileModel.from_row(row),
            )

        return CandidateProfileResult(CandidateProfileResult.DB_ERROR)

    # ── UPDATE: Cập nhật hồ sơ ─────────────────────────────────────────────────

    def update_profile(
        self,
        headline: str = "",
        bio: str = "",
        portfolio_url: str = "",
        years_experience: int | None = None,
    ) -> CandidateProfileResult:
        """Cập nhật hồ sơ ứng viên của user đang đăng nhập."""
        err = self._get_current_user()
        if err:
            return err

        portfolio_url = portfolio_url.strip()
        if portfolio_url and not self._is_valid_url(portfolio_url):
            return CandidateProfileResult(CandidateProfileResult.INVALID_PORTFOLIO)

        if years_experience is not None and years_experience < 0:
            return CandidateProfileResult(CandidateProfileResult.INVALID_YEARS)

        user_id = SessionManager.instance().current_user.id

        # Kiểm tra profile tồn tại
        try:
            existing = db.fetchone(
                "SELECT id FROM candidate_profiles WHERE user_id = ?",
                (user_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error in update_profile check: %s", exc)
            return CandidateProfileResult(CandidateProfileResult.DB_ERROR)

        if existing is None:
            return CandidateProfileResult(CandidateProfileResult.NOT_FOUND)

        # UPDATE — không cho phép cập nhật email, full_name, role, is_active
        try:
            db.execute(
                """
                UPDATE candidate_profiles SET
                    headline         = ?,
                    bio              = ?,
                    portfolio_url    = ?,
                    years_experience = ?,
                    updated_at       = datetime('now','localtime')
                WHERE user_id = ?
                """,
                (headline.strip() or None,
                 bio.strip() or None,
                 portfolio_url or None,
                 years_experience,
                 user_id),
            )
        except sqlite3.Error as exc:
            logger.error("DB error in update_profile: %s", exc)
            return CandidateProfileResult(CandidateProfileResult.DB_ERROR)

        # Lấy profile sau update
        row = db.fetchone(
            """
            SELECT cp.*, u.full_name, u.email
            FROM candidate_profiles cp
            JOIN users u ON cp.user_id = u.id
            WHERE cp.user_id = ?
            """,
            (user_id,),
        )
        if row:
            logger.info("Candidate profile updated: user_id=%d", user_id)
            return CandidateProfileResult(
                CandidateProfileResult.SUCCESS,
                profile=CandidateProfileModel.from_row(row),
            )

        return CandidateProfileResult(CandidateProfileResult.DB_ERROR)

    # ── CV Management ──────────────────────────────────────────────────────────

    def save_cv(self, source_file_path: str) -> CandidateProfileResult:
        """
        Lưu file CV (PDF) vào data/cvs/ và cập nhật resume_path trong DB.

        - Kiểm tra định dạng PDF
        - Kiểm tra dung lượng ≤ 10MB
        - Copy file vào data/cvs/{user_id}_{timestamp}.pdf
        - Cập nhật resume_path trong candidate_profiles
        - Xóa CV cũ nếu có
        """
        err = self._get_current_user()
        if err:
            return err

        user_id = SessionManager.instance().current_user.id

        # Validate file format
        ext = os.path.splitext(source_file_path)[1].lower()
        if ext not in ALLOWED_CV_EXTENSIONS:
            return CandidateProfileResult(CandidateProfileResult.CV_INVALID_FORMAT)

        # Validate file size
        try:
            file_size = os.path.getsize(source_file_path)
        except OSError:
            return CandidateProfileResult(CandidateProfileResult.CV_SAVE_ERROR)

        if file_size > MAX_CV_SIZE:
            return CandidateProfileResult(CandidateProfileResult.CV_TOO_LARGE)

        if file_size == 0:
            return CandidateProfileResult(CandidateProfileResult.CV_INVALID_FORMAT)

        # Tạo thư mục CV nếu chưa có
        cv_dir = os.path.join(consts.DATA_DIR, "cvs")
        os.makedirs(cv_dir, exist_ok=True)

        # Lấy resume_path cũ để xóa sau
        old_cv_path = None
        try:
            row = db.fetchone(
                "SELECT resume_path FROM candidate_profiles WHERE user_id = ?",
                (user_id,),
            )
            if row and row["resume_path"]:
                old_cv_path = os.path.join(consts.DATA_DIR, row["resume_path"]) \
                    if not os.path.isabs(row["resume_path"]) else row["resume_path"]
        except Exception:
            pass

        # Tạo tên file mới: {user_id}_{timestamp}.pdf
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        new_filename = f"{user_id}_{timestamp}.pdf"
        dest_path = os.path.join(cv_dir, new_filename)

        # Copy file
        try:
            shutil.copy2(source_file_path, dest_path)
        except Exception as exc:
            logger.error("CV copy failed: %s", exc)
            return CandidateProfileResult(CandidateProfileResult.CV_SAVE_ERROR)

        # Lưu đường dẫn tương đối vào DB
        rel_path = os.path.relpath(dest_path, consts.DATA_DIR)
        try:
            db.execute(
                "UPDATE candidate_profiles SET resume_path = ?, updated_at = datetime('now','localtime') WHERE user_id = ?",
                (rel_path, user_id),
            )
        except sqlite3.Error as exc:
            logger.error("DB error saving CV path: %s", exc)
            # Xóa file đã copy vì không lưu được DB
            try:
                os.remove(dest_path)
            except Exception:
                pass
            return CandidateProfileResult(CandidateProfileResult.DB_ERROR)

        # Xóa CV cũ
        if old_cv_path and os.path.exists(old_cv_path):
            try:
                os.remove(old_cv_path)
            except Exception:
                logger.warning("Could not delete old CV: %s", old_cv_path)

        logger.info("CV saved: user_id=%d, file=%s", user_id, new_filename)
        return self.get_profile()

    def get_cv_path(self) -> str | None:
        """Trả về đường dẫn tuyệt đối tới file CV của user đang đăng nhập, hoặc None."""
        err = self._get_current_user()
        if err:
            return None

        user_id = SessionManager.instance().current_user.id
        try:
            row = db.fetchone(
                "SELECT resume_path FROM candidate_profiles WHERE user_id = ?",
                (user_id,),
            )
        except Exception:
            return None

        if not row or not row["resume_path"]:
            return None

        path = row["resume_path"]
        if os.path.isabs(path):
            return path if os.path.exists(path) else None
        abs_path = os.path.join(consts.DATA_DIR, path)
        return abs_path if os.path.exists(abs_path) else None

    # ── Validate helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Kiểm tra URL hợp lệ cơ bản."""
        if not url:
            return True
        lowered = url.lower()
        return (
            lowered.startswith("http://")
            or lowered.startswith("https://")
            or lowered.startswith("www.")
            or "." in lowered
        )


# ── Singleton ──────────────────────────────────────────────────────────────────
candidate_profile_service = CandidateProfileService()
