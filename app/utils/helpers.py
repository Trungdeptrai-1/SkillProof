"""
Các hàm tiện ích dùng chung trong ứng dụng SkillProof.
"""

import os
import re
import hashlib
import logging
from datetime import datetime


logger = logging.getLogger(__name__)


# ── Định dạng chuỗi & ngày tháng ─────────────────────────────────────────────

def format_date(dt: datetime | None, fmt: str = "%d/%m/%Y") -> str:
    """Chuyển datetime sang chuỗi hiển thị."""
    if dt is None:
        return "—"
    return dt.strftime(fmt)


def format_datetime(dt: datetime | None) -> str:
    """Chuyển datetime sang chuỗi ngày giờ đầy đủ."""
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M")


def now_str() -> str:
    """Trả về chuỗi thời gian hiện tại chuẩn ISO 8601."""
    return datetime.now().isoformat(timespec="seconds")


# ── Bảo mật ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """
    Băm mật khẩu bằng SHA-256 với salt cứng.
    Lưu ý: trong production nên dùng bcrypt/argon2.
    """
    salt = "skillproof_salt_2024"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    """Kiểm tra mật khẩu với hash đã lưu."""
    return hash_password(plain) == hashed


# ── Kiểm tra dữ liệu đầu vào ─────────────────────────────────────────────────

def is_valid_email(email: str) -> bool:
    """Kiểm tra định dạng email cơ bản."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def is_valid_phone(phone: str) -> bool:
    """Kiểm tra số điện thoại Việt Nam (10 chữ số, bắt đầu 0)."""
    pattern = r"^0\d{9}$"
    return bool(re.match(pattern, phone.strip()))


def is_strong_password(password: str) -> tuple[bool, str]:
    """
    Kiểm tra độ mạnh mật khẩu.
    Trả về (True, "") nếu hợp lệ, (False, lý_do) nếu không.
    """
    if len(password) < 8:
        return False, "Mật khẩu phải có ít nhất 8 ký tự."
    if not re.search(r"[A-Z]", password):
        return False, "Mật khẩu phải có ít nhất 1 chữ hoa."
    if not re.search(r"[0-9]", password):
        return False, "Mật khẩu phải có ít nhất 1 chữ số."
    return True, ""


# ── File & thư mục ────────────────────────────────────────────────────────────

def ensure_dir(path: str) -> None:
    """Tạo thư mục nếu chưa tồn tại."""
    os.makedirs(path, exist_ok=True)


def get_resource_path(relative_path: str) -> str:
    """
    Trả về đường dẫn tuyệt đối tới tài nguyên trong thư mục assets/.
    Tương thích khi đóng gói bằng PyInstaller.
    """
    import sys
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", relative_path)


# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging(log_dir: str, level: int = logging.INFO) -> None:
    """Khởi tạo logging ra file và console."""
    ensure_dir(log_dir)
    log_file = os.path.join(log_dir, f"skillproof_{datetime.now():%Y%m%d}.log")

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.getLogger(__name__).info("Logging khởi tạo thành công.")
