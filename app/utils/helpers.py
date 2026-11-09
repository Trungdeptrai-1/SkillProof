"""
Các hàm tiện ích dùng chung trong ứng dụng SkillProof.

Password hashing: PBKDF2-SHA256 với per-user salt ngẫu nhiên.
  Format lưu DB: "pbkdf2:sha256:<iterations>:<base64_salt>:<base64_hash>"
  Backward compat: hash cũ (SHA-256 + salt cố định, 64 ký tự hex) vẫn verify được.
"""

import os
import re
import hmac
import hashlib
import base64
import logging
from datetime import datetime


logger = logging.getLogger(__name__)

# ── PBKDF2 parameters ────────────────────────────────────────────────────────
_PBKDF2_ALGO       = "sha256"
_PBKDF2_ITERATIONS = 600_000   # OWASP 2023 minimum cho PBKDF2-SHA256
_PBKDF2_SALT_BYTES = 32        # 256-bit random salt per user
_PBKDF2_HASH_BYTES = 32        # 256-bit output
_PBKDF2_PREFIX     = "pbkdf2"

# ── Legacy SHA-256 constant (chỉ dùng để nhận dạng hash cũ) ─────────────────
_LEGACY_SALT = "skillproof_salt_2024"


# ══════════════════════════════════════════════════════════════════════════════
# Password hashing (PBKDF2-SHA256, per-user salt)
# ══════════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """
    Hash mật khẩu bằng PBKDF2-SHA256 với salt ngẫu nhiên 32 bytes.

    Returns:
        Chuỗi lưu DB: "pbkdf2:sha256:600000:<b64_salt>:<b64_hash>"
        Không bao giờ trả về plain password.
    """
    salt   = os.urandom(_PBKDF2_SALT_BYTES)
    dk     = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"),
                                  salt, _PBKDF2_ITERATIONS, _PBKDF2_HASH_BYTES)
    b64s   = base64.b64encode(salt).decode("ascii")
    b64h   = base64.b64encode(dk).decode("ascii")
    return f"{_PBKDF2_PREFIX}:{_PBKDF2_ALGO}:{_PBKDF2_ITERATIONS}:{b64s}:{b64h}"


def verify_password(plain: str, stored: str) -> bool:
    """
    Kiểm tra mật khẩu với hash đã lưu.

    Hỗ trợ hai định dạng:
    - Mới: "pbkdf2:sha256:<iter>:<b64_salt>:<b64_hash>"
    - Cũ (legacy): chuỗi hex 64 ký tự = SHA-256(salt_cố_định + password)

    Luôn dùng hmac.compare_digest để tránh timing attack.
    """
    if not stored or not plain:
        return False

    if stored.startswith(_PBKDF2_PREFIX + ":"):
        return _verify_pbkdf2(plain, stored)
    else:
        return _verify_legacy(plain, stored)


def needs_rehash(stored: str) -> bool:
    """
    Trả về True nếu hash cũ (legacy) và cần nâng cấp lên PBKDF2.
    Dùng trong auth_service sau khi verify thành công để lazy-migrate.
    """
    return not stored.startswith(_PBKDF2_PREFIX + ":")


def _verify_pbkdf2(plain: str, stored: str) -> bool:
    """Xác minh hash định dạng PBKDF2."""
    try:
        parts = stored.split(":")
        if len(parts) != 5 or parts[0] != _PBKDF2_PREFIX:
            return False
        _, algo, iterations_str, b64_salt, b64_hash = parts
        iterations = int(iterations_str)
        salt       = base64.b64decode(b64_salt)
        expected   = base64.b64decode(b64_hash)
        dk         = hashlib.pbkdf2_hmac(
            algo, plain.encode("utf-8"), salt, iterations, len(expected)
        )
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def _verify_legacy(plain: str, stored: str) -> bool:
    """
    Xác minh hash cũ: SHA-256(salt_cố_định + password).
    Chỉ dùng khi migrate — không dùng cho hash mới.
    """
    try:
        computed = hashlib.sha256(
            f"{_LEGACY_SALT}{plain}".encode()
        ).hexdigest()
        return hmac.compare_digest(computed, stored)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Định dạng chuỗi & ngày tháng
# ══════════════════════════════════════════════════════════════════════════════

def format_date(dt: datetime | None, fmt: str = "%d/%m/%Y") -> str:
    """Chuyển datetime sang chuỗi hiển thị."""
    if dt is None:
        return "\u2014"
    return dt.strftime(fmt)


def format_datetime(dt: datetime | None) -> str:
    """Chuyển datetime sang chuỗi ngày giờ đầy đủ."""
    if dt is None:
        return "\u2014"
    return dt.strftime("%d/%m/%Y %H:%M")


def now_str() -> str:
    """Trả về chuỗi thời gian hiện tại chuẩn ISO 8601."""
    return datetime.now().isoformat(timespec="seconds")


# ══════════════════════════════════════════════════════════════════════════════
# Kiểm tra dữ liệu đầu vào
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# File & thư mục
# ══════════════════════════════════════════════════════════════════════════════

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
        base = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    return os.path.join(base, "assets", relative_path)


# ══════════════════════════════════════════════════════════════════════════════
# Logging
# ══════════════════════════════════════════════════════════════════════════════

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
