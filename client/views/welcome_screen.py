"""
Màn hình chào mừng SkillProof.
Thiết kế hai cột: panel navy bên trái (brand) + panel trắng bên phải (action).
"""

from __future__ import annotations

from PySide6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PySide6.QtGui     import (
    QColor, QLinearGradient, QPainter, QPainterPath,
    QBrush,
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSizePolicy, QFrame,
    QGraphicsOpacityEffect,
)

from app.utils.constants import (
    APP_NAME, APP_VERSION, APP_DESCRIPTION,
    COLOR_NAVY_DARK, COLOR_NAVY, COLOR_NAVY_MID, COLOR_NAVY_LIGHT,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED,
    WELCOME_WIDTH, WELCOME_HEIGHT,
)
from app.utils.styles import primary_button_style, ghost_button_style


class _BrandPanel(QWidget):
    """Panel navy bên trái – logo, tên app, tagline."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(380)
        self._setup_ui()

    def paintEvent(self, event):  # noqa: N802
        """Vẽ gradient navy làm nền."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(COLOR_NAVY_DARK))
        gradient.setColorAt(0.5, QColor(COLOR_NAVY))
        gradient.setColorAt(1.0, QColor(COLOR_NAVY_MID))

        path = QPainterPath()
        path.addRect(0, 0, self.width(), self.height())
        painter.fillPath(path, QBrush(gradient))

        # Vẽ các vòng tròn trang trí bán trong suốt
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 12)))
        painter.drawEllipse(-80, -80, 340, 340)
        painter.setBrush(QBrush(QColor(255, 255, 255, 8)))
        painter.drawEllipse(self.width() - 160, self.height() - 200, 300, 300)
        painter.setBrush(QBrush(QColor(46, 134, 222, 40)))
        painter.drawEllipse(40, self.height() - 120, 180, 180)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 50, 40, 40)
        layout.setSpacing(0)

        # ── Logo icon (SVG-style, vẽ bằng QLabel + stylesheet) ───────────────
        logo_container = QWidget()
        logo_container.setFixedSize(72, 72)
        logo_container.setStyleSheet(f"""
            background-color: {COLOR_ACCENT};
            border-radius: 20px;
        """)
        logo_inner = QVBoxLayout(logo_container)
        logo_inner.setContentsMargins(0, 0, 0, 0)
        logo_lbl = QLabel("✓")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet(f"""
            color: {COLOR_WHITE};
            font-size: 34px;
            font-weight: 700;
            background: transparent;
        """)
        logo_inner.addWidget(logo_lbl)
        layout.addWidget(logo_container)

        layout.addSpacing(28)

        # ── Tên ứng dụng ──────────────────────────────────────────────────────
        title_lbl = QLabel(APP_NAME)
        title_lbl.setStyleSheet(f"""
            color: {COLOR_WHITE};
            font-size: 38px;
            font-weight: 700;
            letter-spacing: 1px;
            background: transparent;
        """)
        layout.addWidget(title_lbl)

        # ── Version badge ─────────────────────────────────────────────────────
        version_lbl = QLabel(f"v{APP_VERSION}")
        version_lbl.setStyleSheet(f"""
            color: rgba(255,255,255,0.55);
            font-size: 12px;
            font-weight: 400;
            background: transparent;
            margin-top: 2px;
        """)
        layout.addWidget(version_lbl)

        layout.addSpacing(24)

        # ── Tagline ───────────────────────────────────────────────────────────
        tagline = QLabel("Chứng nhận kỹ năng.\nKhẳng định năng lực.")
        tagline.setStyleSheet(f"""
            color: rgba(255,255,255,0.9);
            font-size: 22px;
            font-weight: 600;
            line-height: 1.4;
            background: transparent;
        """)
        tagline.setWordWrap(True)
        layout.addWidget(tagline)

        layout.addSpacing(16)

        # ── Mô tả ─────────────────────────────────────────────────────────────
        desc_lbl = QLabel(APP_DESCRIPTION)
        desc_lbl.setStyleSheet(f"""
            color: rgba(255,255,255,0.65);
            font-size: 13px;
            line-height: 1.6;
            background: transparent;
        """)
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        layout.addStretch()

        # ── Footer ────────────────────────────────────────────────────────────
        footer_lbl = QLabel("© 2024 SkillProof Team")
        footer_lbl.setStyleSheet(f"""
            color: rgba(255,255,255,0.35);
            font-size: 11px;
            background: transparent;
        """)
        layout.addWidget(footer_lbl)


class _ActionPanel(QWidget):
    """Panel trắng bên phải – nút hành động và thông tin nhanh."""

    # Signal-like callback attributes
    on_get_started: object = None   # callable() | None
    on_learn_more: object  = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {COLOR_OFF_WHITE};")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 60, 50, 40)
        layout.setSpacing(0)

        layout.addStretch(2)

        # ── Tiêu đề ───────────────────────────────────────────────────────────
        welcome_lbl = QLabel("Xin chào! 👋")
        welcome_lbl.setStyleSheet(f"""
            color: {COLOR_TEXT_MUTED};
            font-size: 14px;
            font-weight: 500;
        """)
        layout.addWidget(welcome_lbl)

        layout.addSpacing(6)

        heading = QLabel("Bắt đầu hành trình\nphát triển kỹ năng")
        heading.setStyleSheet(f"""
            color: {COLOR_NAVY_DARK};
            font-size: 26px;
            font-weight: 700;
            line-height: 1.3;
        """)
        layout.addWidget(heading)

        layout.addSpacing(12)

        sub_lbl = QLabel(
            "Quản lý, đánh giá và cấp chứng nhận kỹ năng một cách\n"
            "chuyên nghiệp và minh bạch."
        )
        sub_lbl.setStyleSheet(f"""
            color: {COLOR_TEXT_MUTED};
            font-size: 13px;
            line-height: 1.5;
        """)
        layout.addWidget(sub_lbl)

        layout.addSpacing(36)

        # ── Nút Bắt đầu ───────────────────────────────────────────────────────
        self.btn_start = QPushButton("  Bắt đầu sử dụng  →")
        self.btn_start.setFixedHeight(48)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet(primary_button_style(font_size=15, padding="12px 36px"))
        self.btn_start.clicked.connect(self._on_start)
        layout.addWidget(self.btn_start)

        layout.addSpacing(12)

        # ── Divider ───────────────────────────────────────────────────────────
        divider_layout = QHBoxLayout()
        for _ in range(2):
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet(f"color: {COLOR_LIGHT_GRAY};")
            divider_layout.addWidget(line)
        or_lbl = QLabel("  hoặc  ")
        or_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px;")
        divider_layout.insertWidget(1, or_lbl)
        layout.addLayout(divider_layout)

        layout.addSpacing(12)

        # ── Nút Tìm hiểu thêm ────────────────────────────────────────────────
        self.btn_learn = QPushButton("Tìm hiểu thêm")
        self.btn_learn.setFixedHeight(44)
        self.btn_learn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_learn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_ACCENT};
                border: 1.5px solid {COLOR_ACCENT};
                border-radius: 8px;
                padding: 10px 28px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT};
                color: {COLOR_WHITE};
            }}
        """)
        self.btn_learn.clicked.connect(self._on_learn)
        layout.addWidget(self.btn_learn)

        layout.addStretch(2)

        # ── Feature badges ────────────────────────────────────────────────────
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(12)
        for icon, text in [("🎯", "Đánh giá\nnăng lực"), ("📜", "Cấp chứng\nnhận"), ("📊", "Theo dõi\ntiến độ")]:
            badge = self._make_badge(icon, text)
            badges_layout.addWidget(badge)
        layout.addLayout(badges_layout)

        layout.addSpacing(20)

        # ── Footer status ─────────────────────────────────────────────────────
        self._status_lbl = QLabel("● Hệ thống sẵn sàng")
        self._status_lbl.setStyleSheet(f"color: #27AE60; font-size: 11px;")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_lbl)

    def _make_badge(self, icon: str, text: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_WHITE};
                border: 1.5px solid {COLOR_LIGHT_GRAY};
                border-radius: 10px;
            }}
        """)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        frame.setFixedHeight(80)

        inner = QVBoxLayout(frame)
        inner.setContentsMargins(8, 10, 8, 10)
        inner.setSpacing(4)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        inner.addWidget(icon_lbl)

        text_lbl = QLabel(text)
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_lbl.setStyleSheet(f"""
            color: {COLOR_TEXT_DARK};
            font-size: 10px;
            font-weight: 500;
            background: transparent;
            border: none;
        """)
        inner.addWidget(text_lbl)

        return frame

    # ── Handlers ─────────────────────────────────────────────────────────────
    def _on_start(self) -> None:
        if callable(self.on_get_started):
            self.on_get_started()

    def _on_learn(self) -> None:
        if callable(self.on_learn_more):
            self.on_learn_more()


# ── Màn hình chào mừng chính ─────────────────────────────────────────────────

class WelcomeScreen(QWidget):
    """
    Màn hình chào mừng gồm hai panel.
    Kết nối callback:
        screen.on_get_started = lambda: ...
        screen.on_learn_more  = lambda: ...
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WELCOME_WIDTH, WELCOME_HEIGHT)
        self._setup_ui()
        QTimer.singleShot(100, self._animate_in)

    # ── Thuộc tính callback ───────────────────────────────────────────────────

    @property
    def on_get_started(self):
        return self._action_panel.on_get_started

    @on_get_started.setter
    def on_get_started(self, cb):
        self._action_panel.on_get_started = cb

    @property
    def on_learn_more(self):
        return self._action_panel.on_learn_more

    @on_learn_more.setter
    def on_learn_more(self, cb):
        self._action_panel.on_learn_more = cb

    # ── Setup UI ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._brand_panel  = _BrandPanel()
        self._action_panel = _ActionPanel()

        main_layout.addWidget(self._brand_panel,  stretch=4)
        main_layout.addWidget(self._action_panel, stretch=5)

    # ── Hiệu ứng fade-in ─────────────────────────────────────────────────────

    def _animate_in(self) -> None:
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(600)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()
