"""Shared header for workflow screens."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.utils.constants import COLOR_NAVY_DARK
from app.utils.styles import secondary_button_style


def add_workflow_header(
    layout: QVBoxLayout, title: str, on_back: Callable[[], None]
) -> QPushButton:
    header = QHBoxLayout()
    title_label = QLabel(title)
    title_label.setStyleSheet(
        f"color:{COLOR_NAVY_DARK};font-size:23px;font-weight:700;"
    )
    back_button = QPushButton("← Quay lại Dashboard")
    back_button.setStyleSheet(secondary_button_style(font_size=12))
    back_button.clicked.connect(on_back)
    header.addWidget(title_label)
    header.addStretch()
    header.addWidget(back_button)
    layout.addLayout(header)
    return back_button
