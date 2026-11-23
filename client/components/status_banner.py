"""Reusable status banner for loading, empty, error, and integration states."""

from __future__ import annotations

from typing import Literal

from PySide6.QtWidgets import QLabel, QWidget

from app.utils.constants import (
    COLOR_ERROR,
    COLOR_LIGHT_GRAY,
    COLOR_SUCCESS,
    COLOR_TEXT_DARK,
    COLOR_TEXT_MUTED,
    COLOR_WHITE,
)


StatusKind = Literal["info", "loading", "success", "error", "empty", "unavailable"]


class StatusBanner(QLabel):
    """A styled, accessible status message shared by recruitment views."""

    _COLORS = {
        "info": COLOR_TEXT_DARK,
        "loading": COLOR_TEXT_MUTED,
        "success": COLOR_SUCCESS,
        "error": COLOR_ERROR,
        "empty": COLOR_TEXT_MUTED,
        "unavailable": COLOR_ERROR,
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)
        self.setVisible(False)

    def set_status(self, message: str, kind: StatusKind = "info") -> None:
        color = self._COLORS[kind]
        self.setStyleSheet(
            f"color:{color};background:{COLOR_WHITE};"
            f"border:1px solid {COLOR_LIGHT_GRAY};"
            "border-radius:8px;padding:10px;"
        )
        self.setText(message)
        self.setVisible(bool(message))
        if kind == "loading":
            self.repaint()
