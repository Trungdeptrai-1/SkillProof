"""Reusable, privacy-safe candidate discovery cards.

Only use fields already exposed by the opt-in Marketplace API. The illustrated
avatar is generated locally from initials; it is not a photograph or a claim
about the candidate's appearance.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


def candidate_initials(name: str) -> str:
    words = [part for part in str(name or "").split() if part]
    if not words:
        return "UV"
    return "".join(part[0].upper() for part in words[-2:])


def candidate_avatar(name: str, size: int = 72) -> QPixmap:
    """Draw an appealing placeholder without inventing a person's portrait."""
    canvas = QPixmap(size, size)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    palette = ["#DCEBFF", "#DFF5EE", "#EEE8FE", "#FFEADB", "#E0EFF3"]
    index = sum(ord(char) for char in name) % len(palette)
    painter.setBrush(QColor(palette[index]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size - 1, size - 1, 19, 19)
    font = QFont("Segoe UI", max(12, int(size * 0.28)))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#25476E"))
    painter.drawText(canvas.rect(), Qt.AlignmentFlag.AlignCenter, candidate_initials(name))
    painter.end()
    return canvas


def experience_label(value: object) -> str:
    try:
        years = float(value)
    except (TypeError, ValueError):
        return "Chưa cập nhật kinh nghiệm"
    if years < 0:
        return "Chưa cập nhật kinh nghiệm"
    return f"{years:g} năm kinh nghiệm"


def candidate_card(candidate: dict) -> QWidget:
    """Compact feed card; outer QListWidget keeps keyboard selection."""
    name = str(candidate.get("full_name") or "Ứng viên")
    headline = str(candidate.get("headline") or "Chưa cập nhật vị trí mong muốn")
    bio = " ".join(str(candidate.get("bio") or "").split())
    root = QFrame()
    root.setObjectName("TalentCard")
    root.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    layout = QHBoxLayout(root)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(15)

    avatar = QLabel()
    avatar.setFixedSize(64, 64)
    avatar.setPixmap(candidate_avatar(name, 64))
    layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

    text = QVBoxLayout()
    text.setSpacing(5)
    title = QLabel(name)
    title.setObjectName("TalentCardName")
    title.setWordWrap(True)
    text.addWidget(title)

    position = QLabel(headline)
    position.setObjectName("TalentCardHeadline")
    position.setWordWrap(True)
    text.addWidget(position)

    meta = QLabel(experience_label(candidate.get("years_experience")))
    meta.setObjectName("TalentCardMeta")
    text.addWidget(meta)

    if bio:
        summary = QLabel(bio[:140] + ("…" if len(bio) > 140 else ""))
        summary.setObjectName("TalentCardBio")
        summary.setWordWrap(True)
        text.addWidget(summary)
    layout.addLayout(text, 1)
    return root
