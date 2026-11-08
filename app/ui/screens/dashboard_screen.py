"""
DashboardScreen — Màn hình placeholder sau đăng nhập.
Hiển thị thông tin user và role, chờ triển khai nghiệp vụ ở giai đoạn sau.
Hỗ trợ đầy đủ 6 roles: admin, instructor, student, candidate, company, expert.
"""

from __future__ import annotations

from PySide6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui     import QColor, QLinearGradient, QPainter, QPainterPath, QBrush
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy, QGraphicsOpacityEffect,
    QScrollArea,
)

from app.utils.constants import (
    APP_NAME,
    COLOR_NAVY_DARK, COLOR_NAVY, COLOR_NAVY_MID, COLOR_NAVY_LIGHT,
    COLOR_ACCENT, COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED, COLOR_SUCCESS,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
)
from app.utils.styles import primary_button_style, secondary_button_style
from app.models.user_model import UserModel, ROLE_LABELS, ROLE_ICONS
from app.services.auth_service import session, auth_service


# ── Cấu hình màn hình placeholder theo role ───────────────────────────────────

ROLE_CONFIG: dict[str, dict] = {
    "admin": {
        "title":       "Tổng quan hệ thống",
        "description": "Quản lý toàn bộ người dùng, kỹ năng, khoá học và chứng chỉ.",
        "features": [
            ("👥", "Quản lý người dùng",    "Xem, thêm, sửa, khoá tài khoản"),
            ("📋", "Quản lý kỹ năng",       "Tạo và phân loại danh mục kỹ năng"),
            ("📊", "Thống kê hệ thống",     "Báo cáo tổng quan hoạt động"),
            ("⚙",  "Cài đặt ứng dụng",     "Cấu hình và tuỳ chỉnh hệ thống"),
        ],
        "accent": COLOR_NAVY_MID,
    },
    "instructor": {
        "title":       "Không gian giảng dạy",
        "description": "Tạo và quản lý khoá học, theo dõi tiến độ học viên.",
        "features": [
            ("📚", "Khoá học của tôi",      "Tạo và quản lý nội dung khoá học"),
            ("👩‍🎓", "Học viên",             "Danh sách và tiến độ học viên"),
            ("📝", "Bài đánh giá",          "Tạo và chấm điểm bài kiểm tra"),
            ("📈", "Thống kê khoá học",     "Hiệu quả và phản hồi từ học viên"),
        ],
        "accent": "#1565C0",
    },
    "student": {
        "title":       "Không gian học tập",
        "description": "Khám phá khoá học, theo dõi tiến độ và nhận chứng chỉ.",
        "features": [
            ("📖", "Khoá học đã đăng ký",   "Tiếp tục học các khoá đang học"),
            ("🔍", "Khám phá khoá học",     "Tìm kiếm và đăng ký khoá học mới"),
            ("📜", "Chứng chỉ của tôi",     "Xem và tải chứng chỉ đã nhận"),
            ("🎯", "Mục tiêu học tập",      "Đặt và theo dõi mục tiêu cá nhân"),
        ],
        "accent": "#00695C",
    },
    "candidate": {
        "title":       "Hồ sơ ứng viên",
        "description": "Xây dựng hồ sơ kỹ năng và tìm kiếm cơ hội phù hợp.",
        "features": [
            ("👤", "Hồ sơ cá nhân",         "Cập nhật thông tin và kỹ năng"),
            ("🏅", "Kỹ năng của tôi",       "Danh sách và mức độ thành thạo"),
            ("📜", "Chứng chỉ",             "Chứng nhận kỹ năng đã đạt được"),
            ("🔎", "Khám phá cơ hội",       "Tìm kiếm vị trí phù hợp năng lực"),
        ],
        "accent": "#2E7D32",
    },
    "company": {
        "title":       "Cổng doanh nghiệp",
        "description": "Tìm kiếm và xác minh ứng viên dựa trên kỹ năng chứng nhận.",
        "features": [
            ("🔍", "Tìm kiếm ứng viên",    "Lọc theo kỹ năng và chứng nhận"),
            ("✅", "Xác minh chứng chỉ",    "Kiểm tra tính xác thực chứng chỉ"),
            ("📢", "Đăng tin tuyển dụng",   "Đăng nhu cầu tuyển dụng"),
            ("📊", "Báo cáo nhân sự",       "Phân tích thị trường kỹ năng"),
        ],
        "accent": "#4527A0",
    },
    "expert": {
        "title":       "Không gian chuyên gia",
        "description": "Đánh giá năng lực ứng viên và cấp chứng nhận chuyên môn.",
        "features": [
            ("🎯", "Đánh giá kỹ năng",     "Thực hiện và ghi nhận đánh giá"),
            ("📜", "Cấp chứng nhận",        "Xét duyệt và cấp chứng chỉ"),
            ("👥", "Hồ sơ ứng viên",       "Xem lịch sử và kết quả đánh giá"),
            ("📈", "Báo cáo chuyên môn",   "Tổng kết hoạt động đánh giá"),
        ],
        "accent": "#E65100",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════

class _Sidebar(QWidget):
    """Sidebar navy — thông tin user và menu điều hướng."""

    def __init__(self, user: UserModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(240)
        self._user = user
        self._on_logout_cb = None
        self._setup_ui()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(COLOR_NAVY_DARK))
        gradient.setColorAt(1.0, QColor(COLOR_NAVY_MID))
        path = QPainterPath()
        path.addRect(0, 0, self.width(), self.height())
        painter.fillPath(path, QBrush(gradient))

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 28, 20, 20)
        layout.setSpacing(0)

        # Logo & App name
        logo_row = QHBoxLayout()
        logo_box = QWidget()
        logo_box.setFixedSize(36, 36)
        logo_box.setStyleSheet(f"background:{COLOR_ACCENT}; border-radius:10px;")
        ll = QVBoxLayout(logo_box)
        ll.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("✓")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color:{COLOR_WHITE}; font-size:18px; font-weight:700; background:transparent;")
        ll.addWidget(lbl)
        logo_row.addWidget(logo_box)
        logo_row.addSpacing(8)
        app_lbl = QLabel(APP_NAME)
        app_lbl.setStyleSheet(f"color:{COLOR_WHITE}; font-size:16px; font-weight:700; background:transparent;")
        logo_row.addWidget(app_lbl)
        logo_row.addStretch()
        layout.addLayout(logo_row)

        layout.addSpacing(28)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("color: rgba(255,255,255,0.15);")
        layout.addWidget(div1)

        layout.addSpacing(20)

        # Avatar placeholder
        avatar_row = QHBoxLayout()
        av_box = QWidget()
        av_box.setFixedSize(44, 44)
        av_box.setStyleSheet(f"background:{COLOR_NAVY_LIGHT}; border-radius:22px;")
        av_l = QVBoxLayout(av_box)
        av_l.setContentsMargins(0, 0, 0, 0)
        av_icon = QLabel(ROLE_ICONS.get(self._user.role, "👤"))
        av_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av_icon.setStyleSheet("font-size:20px; background:transparent;")
        av_l.addWidget(av_icon)
        avatar_row.addWidget(av_box)
        avatar_row.addSpacing(10)

        user_info = QVBoxLayout()
        user_info.setSpacing(2)
        name_lbl = QLabel(self._user.display_name)
        name_lbl.setStyleSheet(f"color:{COLOR_WHITE}; font-size:13px; font-weight:600; background:transparent;")
        name_lbl.setWordWrap(True)
        role_lbl = QLabel(ROLE_LABELS.get(self._user.role, self._user.role))
        role_lbl.setStyleSheet(f"color:rgba(255,255,255,0.6); font-size:11px; background:transparent;")
        user_info.addWidget(name_lbl)
        user_info.addWidget(role_lbl)
        avatar_row.addLayout(user_info)
        avatar_row.addStretch()
        layout.addLayout(avatar_row)

        layout.addSpacing(24)

        # Menu items (placeholder — chưa có action thực)
        cfg = ROLE_CONFIG.get(self._user.role, ROLE_CONFIG["candidate"])
        for icon, label, _ in cfg["features"]:
            btn = self._make_menu_item(icon, label)
            layout.addWidget(btn)
            layout.addSpacing(4)

        layout.addStretch()

        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet("color: rgba(255,255,255,0.15);")
        layout.addWidget(div2)

        layout.addSpacing(12)

        # Nút đăng xuất
        logout_btn = QPushButton("  ⏻  Đăng xuất")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setFixedHeight(40)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(231,76,60,0.15);
                color: #FF6B6B;
                border: 1px solid rgba(231,76,60,0.4);
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                text-align: left;
                padding-left: 12px;
            }}
            QPushButton:hover {{
                background: rgba(231,76,60,0.3);
                color: #FF8888;
            }}
        """)
        logout_btn.clicked.connect(self._on_logout)
        layout.addWidget(logout_btn)

    def _make_menu_item(self, icon: str, label: str) -> QPushButton:
        btn = QPushButton(f"  {icon}  {label}")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(38)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: rgba(255,255,255,0.75);
                border: none;
                border-radius: 8px;
                font-size: 12px;
                text-align: left;
                padding-left: 8px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.1);
                color: {COLOR_WHITE};
            }}
        """)
        return btn

    @property
    def on_logout(self):
        return self._on_logout_cb

    @on_logout.setter
    def on_logout(self, cb):
        self._on_logout_cb = cb

    def _on_logout(self) -> None:
        if callable(self._on_logout_cb):
            self._on_logout_cb()


# ══════════════════════════════════════════════════════════════════════════════
# Content area
# ══════════════════════════════════════════════════════════════════════════════

class _ContentArea(QWidget):
    """Vùng nội dung chính — placeholder theo role."""

    def __init__(self, user: UserModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {COLOR_OFF_WHITE};")
        self._user = user
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(0)

        cfg = ROLE_CONFIG.get(self._user.role, ROLE_CONFIG["candidate"])
        accent = cfg["accent"]

        # ── Header ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(f"""
            background-color: {COLOR_WHITE};
            border-radius: 12px;
            border: 1px solid {COLOR_LIGHT_GRAY};
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 20, 24, 20)

        left_info = QVBoxLayout()
        greeting = QLabel(f"Xin chào, {self._user.display_name}! {ROLE_ICONS.get(self._user.role,'')}")
        greeting.setStyleSheet(f"color:{COLOR_TEXT_MUTED}; font-size:13px; font-weight:500;")
        title_lbl = QLabel(cfg["title"])
        title_lbl.setStyleSheet(f"color:{COLOR_NAVY_DARK}; font-size:22px; font-weight:700; margin-top:2px;")
        desc_lbl = QLabel(cfg["description"])
        desc_lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED}; font-size:13px; margin-top:4px;")
        desc_lbl.setWordWrap(True)
        left_info.addWidget(greeting)
        left_info.addWidget(title_lbl)
        left_info.addWidget(desc_lbl)
        left_info.setSpacing(0)

        hl.addLayout(left_info)
        hl.addStretch()

        # Role badge
        badge = QLabel(f"{ROLE_ICONS.get(self._user.role,'')}  {ROLE_LABELS.get(self._user.role,'')}")
        badge.setStyleSheet(f"""
            background-color: {accent};
            color: {COLOR_WHITE};
            border-radius: 12px;
            padding: 6px 16px;
            font-size: 12px;
            font-weight: 600;
        """)
        hl.addWidget(badge)

        layout.addWidget(header)
        layout.addSpacing(24)

        # ── Feature cards ──────────────────────────────────────────────────────
        features_title = QLabel("Tính năng")
        features_title.setStyleSheet(f"color:{COLOR_NAVY_DARK}; font-size:15px; font-weight:700; margin-bottom:12px;")
        layout.addWidget(features_title)
        layout.addSpacing(8)

        # Grid 2x2
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout(grid_widget)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)

        for i, (icon, label, desc) in enumerate(cfg["features"]):
            card = self._make_feature_card(icon, label, desc, accent)
            grid.addWidget(card, i // 2, i % 2)

        layout.addWidget(grid_widget)
        layout.addSpacing(24)

        # ── Placeholder notice ─────────────────────────────────────────────────
        notice = QFrame()
        notice.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(46,134,222,0.08);
                border: 1.5px dashed {COLOR_ACCENT};
                border-radius: 10px;
            }}
        """)
        nl = QHBoxLayout(notice)
        nl.setContentsMargins(20, 16, 20, 16)
        notice_icon = QLabel("🚧")
        notice_icon.setStyleSheet("font-size:24px; background:transparent; border:none;")
        notice_text = QLabel(
            "<b>Đang phát triển</b><br>"
            "Các tính năng nghiệp vụ sẽ được triển khai ở giai đoạn tiếp theo.<br>"
            "Hệ thống xác thực và điều hướng theo vai trò đã sẵn sàng."
        )
        notice_text.setStyleSheet(f"color:{COLOR_TEXT_DARK}; font-size:12px; background:transparent; border:none;")
        notice_text.setWordWrap(True)
        nl.addWidget(notice_icon)
        nl.addSpacing(12)
        nl.addWidget(notice_text)
        nl.addStretch()
        layout.addWidget(notice)

        layout.addStretch()

    def _make_feature_card(self, icon: str, label: str, desc: str, accent: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_WHITE};
                border-radius: 12px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        card.setFixedHeight(100)
        cl = QHBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(16)

        icon_box = QWidget()
        icon_box.setFixedSize(44, 44)
        icon_box.setStyleSheet(f"background: rgba(46,134,222,0.1); border-radius: 12px;")
        ib_l = QVBoxLayout(icon_box)
        ib_l.setContentsMargins(0, 0, 0, 0)
        ic_lbl = QLabel(icon)
        ic_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic_lbl.setStyleSheet("font-size:20px; background:transparent;")
        ib_l.addWidget(ic_lbl)
        cl.addWidget(icon_box)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{COLOR_NAVY_DARK}; font-size:13px; font-weight:600;")
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED}; font-size:11px;")
        desc_lbl.setWordWrap(True)
        text_col.addWidget(lbl)
        text_col.addWidget(desc_lbl)
        cl.addLayout(text_col)
        cl.addStretch()

        coming_soon = QLabel("Sắp có")
        coming_soon.setStyleSheet(f"""
            color: {COLOR_TEXT_MUTED};
            font-size: 10px;
            background: {COLOR_LIGHT_GRAY};
            border-radius: 6px;
            padding: 2px 8px;
        """)
        cl.addWidget(coming_soon)

        return card


# ══════════════════════════════════════════════════════════════════════════════
# DashboardScreen
# ══════════════════════════════════════════════════════════════════════════════

class DashboardScreen(QWidget):
    """
    Dashboard placeholder cho 6 roles.
    Kết nối:
        screen.on_logout = lambda: ...
    """

    def __init__(self, user: UserModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._user = user
        self._on_logout_cb = None
        self._setup_ui()
        QTimer.singleShot(80, self._animate_in)

    @property
    def on_logout(self):
        return self._on_logout_cb

    @on_logout.setter
    def on_logout(self, cb):
        self._on_logout_cb = cb
        if self._sidebar:
            self._sidebar.on_logout = cb

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = _Sidebar(self._user)
        self._sidebar.on_logout = self._handle_logout

        self._content = _ContentArea(self._user)

        layout.addWidget(self._sidebar)
        layout.addWidget(self._content, stretch=1)

    def _animate_in(self) -> None:
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def _handle_logout(self) -> None:
        auth_service.logout()
        if callable(self._on_logout_cb):
            self._on_logout_cb()
