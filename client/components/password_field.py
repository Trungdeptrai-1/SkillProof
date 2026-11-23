"""Password input widget with an inline visibility toggle."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QPushButton, QWidget

from app.utils.constants import (
    COLOR_ACCENT,
    COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK,
    COLOR_TEXT_MUTED,
    COLOR_WHITE,
)


class PasswordField(QFrame):
    """A styled password input and visibility toggle."""

    def __init__(
        self,
        placeholder: str,
        height: int = 42,
        toggle_size: int = 30,
        toggle_font_size: int = 15,
        focus_border: bool = False,
        tooltip: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        focus_style = (
            f"QFrame:focus-within {{ border-color: {COLOR_ACCENT}; }}"
            if focus_border
            else ""
        )
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_WHITE};
                border: 1.5px solid {COLOR_LIGHT_GRAY};
                border-radius: 8px;
            }}
            {focus_style}
        """)
        self.setFixedHeight(height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(0)

        self.line_edit = QLineEdit()
        self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.line_edit.setPlaceholderText(placeholder)
        self.set_text_color(COLOR_TEXT_DARK)
        layout.addWidget(self.line_edit)

        self.toggle_button = QPushButton("👁")
        self.toggle_button.setFixedSize(toggle_size, toggle_size)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-size: {toggle_font_size}px;
                color: {COLOR_TEXT_MUTED};
                border-radius: 6px;
            }}
            QPushButton:hover {{ color: {COLOR_ACCENT}; }}
        """)
        if tooltip:
            self.toggle_button.setToolTip(tooltip)
        self.toggle_button.clicked.connect(self.toggle_visibility)
        layout.addWidget(self.toggle_button)
        self._visible = False

    def set_text_color(self, color: str) -> None:
        self.line_edit.setStyleSheet(f"""
            QLineEdit {{
                border: none;
                background: transparent;
                font-size: 13px;
                color: {color};
                padding: 0;
            }}
        """)

    def toggle_visibility(self) -> None:
        self._visible = not self._visible
        self.line_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if self._visible
            else QLineEdit.EchoMode.Password
        )
        self.toggle_button.setText("🙈" if self._visible else "👁")

    def reset_visibility(self) -> None:
        self._visible = False
        self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_button.setText("👁")
