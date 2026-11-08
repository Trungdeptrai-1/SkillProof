"""
UserModel — Data Transfer Object cho bảng users.
Không chứa business logic. Chỉ map dữ liệu từ DB ra Python object.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

# 6 giá trị role hợp lệ — đồng bộ với CHECK constraint trong schema.py
UserRole = Literal["admin", "instructor", "student", "candidate", "company", "expert"]

# Nhãn hiển thị thân thiện cho từng role
ROLE_LABELS: dict[str, str] = {
    "admin":      "Quản trị viên",
    "instructor": "Giảng viên",
    "student":    "Học viên",
    "candidate":  "Ứng viên",
    "company":    "Doanh nghiệp",
    "expert":     "Chuyên gia",
}

# Icon đại diện cho từng role (emoji — không cần file ảnh)
ROLE_ICONS: dict[str, str] = {
    "admin":      "⚙",
    "instructor": "🎓",
    "student":    "📚",
    "candidate":  "👤",
    "company":    "🏢",
    "expert":     "🏆",
}


@dataclass
class UserModel:
    """
    Đại diện cho một hàng trong bảng users.
    Tất cả trường đều read-only sau khi tạo (frozen=False để tiện test).
    Không lưu mật khẩu dạng plain text ở bất kỳ đâu.
    """

    id:          int
    username:    str
    email:       str
    full_name:   str
    role:        str          # Một trong 6 giá trị UserRole
    avatar_path: str | None
    is_active:   bool
    created_at:  str
    updated_at:  str

    # ── Thuộc tính dẫn xuất ──────────────────────────────────────────────────

    @property
    def role_label(self) -> str:
        """Nhãn hiển thị tiếng Việt của role."""
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def role_icon(self) -> str:
        """Icon emoji của role."""
        return ROLE_ICONS.get(self.role, "👤")

    @property
    def display_name(self) -> str:
        """Tên hiển thị: full_name nếu có, fallback về username."""
        return self.full_name.strip() if self.full_name.strip() else self.username

    # ── Factory methods ───────────────────────────────────────────────────────

    @classmethod
    def from_row(cls, row) -> "UserModel":
        """
        Tạo UserModel từ sqlite3.Row.
        Không nhận trường password — bảo mật.
        """
        return cls(
            id          = row["id"],
            username    = row["username"],
            email       = row["email"],
            full_name   = row["full_name"],
            role        = row["role"],
            avatar_path = row["avatar_path"],
            is_active   = bool(row["is_active"]),
            created_at  = row["created_at"],
            updated_at  = row["updated_at"],
        )

    def __repr__(self) -> str:
        return (
            f"UserModel(id={self.id}, username={self.username!r}, "
            f"role={self.role!r}, active={self.is_active})"
        )
