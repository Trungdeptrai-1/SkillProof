"""
Stylesheet tập trung cho ứng dụng SkillProof.
Dùng QSS (Qt Style Sheets) – tương tự CSS.
"""

from app.utils.constants import (
    COLOR_NAVY_DARK, COLOR_NAVY, COLOR_NAVY_MID, COLOR_NAVY_LIGHT,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    FONT_FAMILY,
)


# ── Stylesheet toàn cục ───────────────────────────────────────────────────────
GLOBAL_STYLE = f"""
* {{
    font-family: "{FONT_FAMILY}", "Arial", sans-serif;
    outline: none;
}}

QMainWindow, QDialog {{
    background-color: {COLOR_OFF_WHITE};
}}

QWidget {{
    color: {COLOR_TEXT_DARK};
    font-size: 13px;
}}

/* ── Scrollbar ── */
QScrollBar:vertical {{
    background: {COLOR_LIGHT_GRAY};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_NAVY_MID};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* ── Tooltip ── */
QToolTip {{
    background-color: {COLOR_NAVY_DARK};
    color: {COLOR_WHITE};
    border: 1px solid {COLOR_NAVY_MID};
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}}
"""


# ── Button styles ─────────────────────────────────────────────────────────────
def primary_button_style(
    font_size: int = 14,
    padding: str = "12px 40px",
    border_radius: int = 8,
) -> str:
    return f"""
        QPushButton {{
            background-color: {COLOR_ACCENT};
            color: {COLOR_WHITE};
            border: none;
            border-radius: {border_radius}px;
            padding: {padding};
            font-size: {font_size}px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        QPushButton:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {COLOR_NAVY_LIGHT};
        }}
        QPushButton:disabled {{
            background-color: {COLOR_LIGHT_GRAY};
            color: {COLOR_TEXT_MUTED};
        }}
    """


def secondary_button_style(
    font_size: int = 13,
    padding: str = "10px 28px",
    border_radius: int = 8,
) -> str:
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {COLOR_ACCENT};
            border: 2px solid {COLOR_ACCENT};
            border-radius: {border_radius}px;
            padding: {padding};
            font-size: {font_size}px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {COLOR_ACCENT};
            color: {COLOR_WHITE};
        }}
        QPushButton:pressed {{
            background-color: {COLOR_ACCENT_HOVER};
            color: {COLOR_WHITE};
        }}
    """


def ghost_button_style(font_size: int = 13) -> str:
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {COLOR_WHITE};
            border: 2px solid rgba(255,255,255,0.6);
            border-radius: 8px;
            padding: 10px 28px;
            font-size: {font_size}px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            border-color: {COLOR_WHITE};
            background-color: rgba(255,255,255,0.1);
        }}
        QPushButton:pressed {{
            background-color: rgba(255,255,255,0.2);
        }}
    """


# ── Input styles ──────────────────────────────────────────────────────────────
INPUT_STYLE = f"""
    QLineEdit, QTextEdit, QComboBox {{
        background-color: {COLOR_WHITE};
        color: {COLOR_TEXT_DARK};
        border: 1.5px solid {COLOR_LIGHT_GRAY};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
        selection-background-color: {COLOR_ACCENT};
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border-color: {COLOR_ACCENT};
    }}
    QLineEdit:hover, QTextEdit:hover, QComboBox:hover {{
        border-color: {COLOR_NAVY_LIGHT};
    }}
"""

# ── Card / Panel ──────────────────────────────────────────────────────────────
CARD_STYLE = f"""
    QFrame {{
        background-color: {COLOR_WHITE};
        border-radius: 12px;
        border: 1px solid {COLOR_LIGHT_GRAY};
    }}
"""

# ── Status label ──────────────────────────────────────────────────────────────
STATUS_SUCCESS_STYLE = f"color: {COLOR_SUCCESS}; font-size: 12px;"
STATUS_ERROR_STYLE   = f"color: {COLOR_ERROR};   font-size: 12px;"
STATUS_WARNING_STYLE = f"color: {COLOR_WARNING}; font-size: 12px;"
