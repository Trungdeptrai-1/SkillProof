"""
Hằng số toàn cục của ứng dụng SkillProof.
"""

# ── Thông tin ứng dụng ────────────────────────────────────────────────────────
APP_NAME = "SkillProof"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = (
    "Hệ thống quản lý và chứng nhận kỹ năng chuyên nghiệp.\n"
    "Theo dõi lộ trình học tập, đánh giá năng lực và cấp chứng chỉ."
)
APP_AUTHOR = "SkillProof Team"

# ── Kích thước cửa sổ ────────────────────────────────────────────────────────
WINDOW_MIN_WIDTH = 1024
WINDOW_MIN_HEIGHT = 680
WINDOW_DEFAULT_WIDTH = 1280
WINDOW_DEFAULT_HEIGHT = 800

WELCOME_WIDTH = 960
WELCOME_HEIGHT = 620

# ── Màu sắc chủ đạo (Navy & White) ───────────────────────────────────────────
COLOR_NAVY_DARK   = "#0A1628"   # navy đậm nhất – header/sidebar
COLOR_NAVY        = "#0D2137"   # navy chính
COLOR_NAVY_MID    = "#1A3A5C"   # navy trung
COLOR_NAVY_LIGHT  = "#1E4D7B"   # navy nhạt – accent
COLOR_ACCENT      = "#2E86DE"   # xanh cobalt – button/highlight
COLOR_ACCENT_HOVER = "#1A73C8"  # hover state
COLOR_WHITE       = "#FFFFFF"
COLOR_OFF_WHITE   = "#F4F7FB"   # nền sáng
COLOR_LIGHT_GRAY  = "#E8EDF4"   # border/divider
COLOR_TEXT_DARK   = "#0A1628"   # text trên nền trắng
COLOR_TEXT_MUTED  = "#6B7F99"   # text phụ
COLOR_SUCCESS     = "#27AE60"
COLOR_WARNING     = "#F39C12"
COLOR_ERROR       = "#E74C3C"

# ── Phông chữ ────────────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_SIZE_TITLE   = 32
FONT_SIZE_HEADING = 22
FONT_SIZE_SUBHEAD = 16
FONT_SIZE_BODY    = 13
FONT_SIZE_SMALL   = 11

# ── Cơ sở dữ liệu ────────────────────────────────────────────────────────────
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH  = os.path.join(DATA_DIR, "skillproof.db")
