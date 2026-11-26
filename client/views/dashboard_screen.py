"""Role-specific dashboards for authenticated non-admin users."""

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
from server.controllers.auth_controller import auth_controller


# ── Cấu hình dashboard theo role ──────────────────────────────────────────────

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
        "title":       "Không gian ứng viên",
        "description": "Khám phá công việc, theo dõi ứng tuyển và phát triển năng lực.",
        "features": [
            ("👤", "Hồ sơ cá nhân",         "Cập nhật thông tin và kỹ năng"),
            ("🏅", "Kỹ năng của tôi",       "Danh sách và mức độ thành thạo"),
            ("📜", "Chứng chỉ",             "Chứng nhận kỹ năng đã đạt được"),
            ("🔎", "Khám phá cơ hội",       "Tìm kiếm và ứng tuyển vị trí phù hợp"),
            ("📝", "Lời mời làm bài",       "Nhận lời mời, làm bài thi và xem kết quả"),
            ("✍", "Bài tự luận & Coding",  "Bài trả lời dài và lập trình"),
            ("⏱", "Giám sát phiên thi",    "Trạng thái phiên và cảnh báo focus cục bộ"),
            ("🗓", "Phỏng vấn",             "Lịch và trạng thái phỏng vấn"),
        ],
        "accent": "#2E7D32",
    },
    "company": {
        "title":       "Tổng quan tuyển dụng",
        "description": "Quản lý toàn bộ quy trình tuyển dụng và đánh giá ứng viên trên một nền tảng.",
        "features": [
            ("🔎", "Tìm chuyên gia",         "Tìm kiếm và gửi lời mời hợp tác"),
            ("📋", "Hợp đồng của tôi",       "Theo dõi hợp đồng với chuyên gia"),
            ("🎯", "Nhiệm vụ của tôi",       "Tạo và theo dõi nhiệm vụ"),
            ("🏢", "Hồ sơ doanh nghiệp",     "Cập nhật thông tin doanh nghiệp"),
            ("🧑‍💼", "Tuyển dụng & đánh giá", "Vị trí, bài thi, lời mời và kết quả"),
            ("📥", "Hồ sơ ứng tuyển", "Xem đơn ứng tuyển và khám phá nhân tài"),
            ("📝", "Chấm bài tự luận/Coding", "Chấm thủ công khi backend hỗ trợ"),
            ("🗓", "Lịch phỏng vấn",          "Lịch và ghi chú đánh giá"),
            ("📜", "Chứng chỉ",               "Cấp hoặc xác minh theo quyền Controller"),
        ],
        "accent": "#4527A0",
    },
    "expert": {
        "title":       "Không gian chuyên gia",
        "description": "Đánh giá năng lực ứng viên và cấp chứng nhận chuyên môn.",
        "features": [
            ("🏆", "Hồ sơ chuyên gia",      "Cập nhật thông tin chuyên môn"),
            ("📋", "Hợp đồng của tôi",       "Xem và xử lý lời mời hợp tác"),
            ("🎯", "Nhiệm vụ của tôi",       "Theo dõi nhiệm vụ được giao"),
            ("📈", "Thống kê chuyên môn",    "Chưa có báo cáo kết nối Controller"),
            ("📝", "Chấm bài tự luận/Coding", "Chấm thủ công khi backend hỗ trợ"),
            ("🗓", "Lịch phỏng vấn",          "Lịch và ghi chú đánh giá"),
            ("📜", "Chứng chỉ",               "Cấp hoặc xác minh theo quyền Controller"),
        ],
        "accent": "#E65100",
    },
}

EXTENDED_WORKFLOW_ROUTES = {
    "Bài tự luận & Coding": "candidate_specialized",
    "Giám sát phiên thi": "exam_monitor",
    "Chấm bài tự luận/Coding": "manual_grading",
    "Phỏng vấn": "interviews",
    "Lịch phỏng vấn": "interviews",
    "Chứng chỉ": "certificates",
}


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════

class _Sidebar(QWidget):
    """Sidebar navy — thông tin user và menu điều hướng."""

    def __init__(self, user: UserModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(264)
        self._user = user
        self._on_logout_cb = None
        self._on_open_candidate_profile_cb = None
        self._on_open_company_profile_cb = None
        self._on_open_expert_profile_cb = None
        self._on_open_expert_search_cb = None
        self._on_open_contracts_cb = None
        self._on_open_tasks_cb = None
        self._on_open_company_recruitment_cb = None
        self._on_open_candidate_assessments_cb = None
        self._on_open_extended_workflow_cb = None
        self._on_open_marketplace_cb = None
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
        logo_box.setObjectName("BrandIcon")
        logo_box.setStyleSheet(f"QWidget#BrandIcon {{ background:{COLOR_ACCENT}; border-radius:10px; }}")
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
        av_box.setObjectName("SidebarAvatar")
        av_box.setStyleSheet(f"QWidget#SidebarAvatar {{ background:{COLOR_NAVY_LIGHT}; border-radius:22px; }}")
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


        # Company navigation is grouped around the actual recruitment journey.
        # Every entry below already has a MainWindow handler.
        if self._user.role == "company":
            groups = [
                ("TUYỂN DỤNG", [
                    ("▣", "Tuyển dụng & đánh giá", self._handle_open_company_recruitment),
                    ("◉", "Hồ sơ ứng tuyển", self._handle_open_marketplace),
                    ("◷", "Phỏng vấn", lambda: self._handle_open_extended_workflow("interviews")),
                    ("▤", "Chấm bài đánh giá", lambda: self._handle_open_extended_workflow("manual_grading")),
                ]),
                ("HỒ SƠ", [
                    ("▦", "Hồ sơ doanh nghiệp", self._handle_open_company_profile),
                ]),
                ("HỢP TÁC CHUYÊN MÔN", [
                    ("⌕", "Tìm chuyên gia", self._handle_open_expert_search),
                    ("▣", "Hợp đồng của tôi", self._handle_open_contracts),
                    ("✓", "Nhiệm vụ của tôi", self._handle_open_tasks),
                ]),
            ]
            for section, items in groups:
                caption = QLabel(section)
                caption.setStyleSheet(
                    "QLabel { background: transparent; border: none; color: #AFC2D8;"
                    " font-size: 10px; font-weight: 700; padding-left: 8px; }"
                )
                layout.addWidget(caption)
                layout.addSpacing(7)
                for icon, label, handler in items:
                    btn = self._make_menu_item(icon, label)
                    btn.clicked.connect(handler)
                    layout.addWidget(btn)
                    layout.addSpacing(3)
                layout.addSpacing(12)
        else:
            cfg = ROLE_CONFIG.get(self._user.role, ROLE_CONFIG["candidate"])
            linked = {
                "candidate": {"Hồ sơ cá nhân", "Lời mời làm bài", "Khám phá cơ hội",
                              "Bài tự luận & Coding", "Giám sát phiên thi", "Phỏng vấn", "Chứng chỉ"},
                "expert": {"Hồ sơ chuyên gia", "Hợp đồng của tôi", "Nhiệm vụ của tôi",
                           "Chấm bài tự luận/Coding", "Lịch phỏng vấn", "Chứng chỉ"},
            }
            for icon, label, _ in cfg["features"]:
                if label not in linked.get(self._user.role, set()):
                    continue
                btn = self._make_menu_item(icon, label)
                if self._user.role == "candidate" and label == "Hồ sơ cá nhân":
                    btn.clicked.connect(self._handle_open_candidate_profile)
                elif self._user.role == "candidate" and label == "Lời mời làm bài":
                    btn.clicked.connect(self._handle_open_candidate_assessments)
                elif self._user.role == "candidate" and label == "Khám phá cơ hội":
                    btn.clicked.connect(self._handle_open_marketplace)
                elif self._user.role == "expert" and label == "Hồ sơ chuyên gia":
                    btn.clicked.connect(self._handle_open_expert_profile)
                elif self._user.role == "expert" and label == "Hợp đồng của tôi":
                    btn.clicked.connect(self._handle_open_contracts)
                elif self._user.role == "expert" and label == "Nhiệm vụ của tôi":
                    btn.clicked.connect(self._handle_open_tasks)
                elif label in EXTENDED_WORKFLOW_ROUTES:
                    btn.clicked.connect(
                        lambda checked=False, route=EXTENDED_WORKFLOW_ROUTES[label]:
                        self._handle_open_extended_workflow(route)
                    )
                layout.addWidget(btn)
                layout.addSpacing(3)

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
        btn.setFixedHeight(36)
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

    @property
    def on_open_candidate_profile(self):
        return self._on_open_candidate_profile_cb

    @on_open_candidate_profile.setter
    def on_open_candidate_profile(self, cb):
        self._on_open_candidate_profile_cb = cb

    def _handle_open_candidate_profile(self) -> None:
        if callable(self._on_open_candidate_profile_cb):
            self._on_open_candidate_profile_cb()

    @property
    def on_open_company_profile(self):
        return self._on_open_company_profile_cb

    @on_open_company_profile.setter
    def on_open_company_profile(self, cb):
        self._on_open_company_profile_cb = cb

    def _handle_open_company_profile(self) -> None:
        if callable(self._on_open_company_profile_cb):
            self._on_open_company_profile_cb()

    @property
    def on_open_expert_profile(self):
        return self._on_open_expert_profile_cb

    @on_open_expert_profile.setter
    def on_open_expert_profile(self, cb):
        self._on_open_expert_profile_cb = cb

    def _handle_open_expert_profile(self) -> None:
        if callable(self._on_open_expert_profile_cb):
            self._on_open_expert_profile_cb()

    @property
    def on_open_expert_search(self):
        return self._on_open_expert_search_cb

    @on_open_expert_search.setter
    def on_open_expert_search(self, cb):
        self._on_open_expert_search_cb = cb

    def _handle_open_expert_search(self) -> None:
        if callable(self._on_open_expert_search_cb):
            self._on_open_expert_search_cb()

    @property
    def on_open_contracts(self):
        return self._on_open_contracts_cb

    @on_open_contracts.setter
    def on_open_contracts(self, cb):
        self._on_open_contracts_cb = cb

    def _handle_open_contracts(self) -> None:
        if callable(self._on_open_contracts_cb):
            self._on_open_contracts_cb()

    @property
    def on_open_tasks(self):
        return self._on_open_tasks_cb

    @on_open_tasks.setter
    def on_open_tasks(self, cb):
        self._on_open_tasks_cb = cb

    def _handle_open_tasks(self) -> None:
        if callable(self._on_open_tasks_cb):
            self._on_open_tasks_cb()

    @property
    def on_open_company_recruitment(self):
        return self._on_open_company_recruitment_cb

    @on_open_company_recruitment.setter
    def on_open_company_recruitment(self, cb):
        self._on_open_company_recruitment_cb = cb

    def _handle_open_company_recruitment(self) -> None:
        if callable(self._on_open_company_recruitment_cb):
            self._on_open_company_recruitment_cb()

    @property
    def on_open_candidate_assessments(self):
        return self._on_open_candidate_assessments_cb

    @on_open_candidate_assessments.setter
    def on_open_candidate_assessments(self, cb):
        self._on_open_candidate_assessments_cb = cb

    def _handle_open_candidate_assessments(self) -> None:
        if callable(self._on_open_candidate_assessments_cb):
            self._on_open_candidate_assessments_cb()

    @property
    def on_open_marketplace(self):
        return getattr(self, "_on_open_marketplace_cb", None)

    @on_open_marketplace.setter
    def on_open_marketplace(self, cb):
        self._on_open_marketplace_cb = cb

    def _handle_open_marketplace(self) -> None:
        cb = getattr(self, "_on_open_marketplace_cb", None)
        if callable(cb):
            cb()

    @property
    def on_open_extended_workflow(self):
        return self._on_open_extended_workflow_cb

    @on_open_extended_workflow.setter
    def on_open_extended_workflow(self, callback):
        self._on_open_extended_workflow_cb = callback

    def _handle_open_extended_workflow(self, route: str) -> None:
        if callable(self._on_open_extended_workflow_cb):
            self._on_open_extended_workflow_cb(route)


# ══════════════════════════════════════════════════════════════════════════════
# Content area
# ══════════════════════════════════════════════════════════════════════════════

class _ContentArea(QWidget):
    """Vùng nội dung chính, phân biệt tính năng đã nối và chưa tích hợp."""

    def __init__(self, user: UserModel, parent: QWidget | None = None, on_action=None) -> None:
        super().__init__(parent)
        self._on_action = on_action
        self.setObjectName("DashboardContent")
        self.setStyleSheet(f"QWidget#DashboardContent {{ background-color: {COLOR_OFF_WHITE}; }}")
        self._user = user
        self._setup_ui()

    def _setup_ui(self) -> None:
        if self._user.role == "company":
            self._setup_company_ui()
            return
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(0)

        cfg = ROLE_CONFIG.get(self._user.role, ROLE_CONFIG["candidate"])
        accent = cfg["accent"]

        # ── Header ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("DashboardHeader")
        header.setStyleSheet(f"""
            QWidget#DashboardHeader {{
                background-color: {COLOR_WHITE};
                border-radius: 14px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
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
        features_title = QLabel("Các tính năng đang sử dụng")
        features_title.setStyleSheet(f"color:{COLOR_NAVY_DARK}; font-size:15px; font-weight:700; margin-bottom:12px;")
        layout.addWidget(features_title)
        layout.addSpacing(8)

        # Grid 2x2
        grid_widget = QWidget()
        grid_widget.setObjectName("DashboardFeatureGrid")
        grid_widget.setStyleSheet("QWidget#DashboardFeatureGrid { background: transparent; }")
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout(grid_widget)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)

        active_features = {
            "candidate": {
                "Hồ sơ cá nhân",
                "Khám phá cơ hội",
                "Lời mời làm bài",
                "Bài tự luận & Coding",
                "Giám sát phiên thi",
                "Phỏng vấn",
                "Chứng chỉ",
            },
            "company": {
                "Tìm chuyên gia",
                "Hợp đồng của tôi",
                "Nhiệm vụ của tôi",
                "Hồ sơ doanh nghiệp",
                "Tuyển dụng & đánh giá",
                "Hồ sơ ứng tuyển",
                "Chấm bài tự luận/Coding",
                "Lịch phỏng vấn",
                "Chứng chỉ",
            },
            "expert": {
                "Hồ sơ chuyên gia",
                "Hợp đồng của tôi",
                "Nhiệm vụ của tôi",
                "Chấm bài tự luận/Coding",
                "Lịch phỏng vấn",
                "Chứng chỉ",
            },
        }
        available_items = [
            item for item in cfg["features"]
            if item[1] in active_features.get(self._user.role, set())
        ]
        for i, (icon, label, desc) in enumerate(available_items):
            card = self._make_feature_card(
                icon,
                label,
                desc,
                accent,
                available=label in active_features.get(self._user.role, set()),
            )
            grid.addWidget(card, i // 2, i % 2)

        layout.addWidget(grid_widget)
        layout.addSpacing(24)

        # Keep the overview focused on available features; unfinished modules
        # must not look like clickable product functionality.

        layout.addStretch()

    def _setup_company_ui(self) -> None:
        """Real, actionable recruiting homepage. No dead-end decorative tiles."""
        from PySide6.QtWidgets import QGridLayout

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.addWidget(scroll)

        body = QWidget()
        body.setObjectName("CompanyDashboardBody")
        body.setStyleSheet("QWidget#CompanyDashboardBody { background: #F5F8FC; }")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(34, 30, 34, 32)
        layout.setSpacing(18)

        eyebrow = QLabel(f"XIN CHÀO, {self._user.display_name.upper()}")
        eyebrow.setStyleSheet(
            "QLabel { color: #3569A2; background: transparent; font-size: 11px;"
            " font-weight: 700; }"
        )
        layout.addWidget(eyebrow)
        title = QLabel(ROLE_CONFIG[self._user.role]["title"])
        title.setWordWrap(True)
        title.setStyleSheet(
            "QLabel { color: #142B45; background: transparent;"
            " font-size: 27px; font-weight: 700; }"
        )
        layout.addWidget(title)
        description = QLabel(
            "Từ đăng tuyển, tiếp nhận ứng viên đến phỏng vấn và đưa ra quyết định."
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "QLabel { color: #62748B; background: transparent; font-size: 13px; }"
        )
        layout.addWidget(description)
        layout.addSpacing(9)

        heading = QLabel("Quy trình tuyển dụng")
        heading.setStyleSheet(
            "QLabel { color: #142B45; background: transparent;"
            " font-size: 18px; font-weight: 700; }"
        )
        layout.addWidget(heading)

        processes = [
            ("01", "Quản lý vị trí tuyển dụng",
             "Tạo tin tuyển dụng, cập nhật trạng thái và thiết lập bài đánh giá.",
             "positions"),
            ("02", "Tiếp nhận hồ sơ ứng viên",
             "Xem hồ sơ ứng tuyển, tìm kiếm ứng viên và gửi lời mời.",
             "applicants"),
            ("03", "Phỏng vấn ứng viên",
             "Theo dõi lịch hẹn, trạng thái và nội dung đánh giá.",
             "interviews"),
            ("04", "Đánh giá bài làm",
             "Chấm bài tự luận, coding và công bố kết quả theo phân quyền.",
             "grading"),
        ]
        grid_holder = QWidget()
        grid_holder.setObjectName("CompanyActionGrid")
        grid_holder.setStyleSheet(
            "QWidget#CompanyActionGrid { background: transparent; }"
        )
        grid = QGridLayout(grid_holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(16)

        for i, (number, name, explanation, route) in enumerate(processes):
            card = QFrame()
            card.setObjectName("CompanyActionCard")
            card.setMinimumHeight(176)
            card.setStyleSheet(
                "QFrame#CompanyActionCard { background: #FFFFFF;"
                " border: 1px solid #DEE7F1; border-radius: 14px; }"
            )
            panel = QVBoxLayout(card)
            panel.setContentsMargins(20, 17, 20, 17)
            panel.setSpacing(9)
            step = QLabel(f"BƯỚC {number}")
            step.setStyleSheet(
                "QLabel { color: #2563A6; background: transparent;"
                " font-size: 11px; font-weight: 700; }"
            )
            panel.addWidget(step)
            name_label = QLabel(name)
            name_label.setWordWrap(True)
            name_label.setStyleSheet(
                "QLabel { color: #132D4D; background: transparent;"
                " font-size: 16px; font-weight: 700; }"
            )
            panel.addWidget(name_label)
            desc = QLabel(explanation)
            desc.setWordWrap(True)
            desc.setStyleSheet(
                "QLabel { color: #66768B; background: transparent; font-size: 12px; }"
            )
            panel.addWidget(desc)
            panel.addStretch()
            action = QPushButton("Mở chức năng")
            action.setObjectName("CompanyAction")
            action.setCursor(Qt.CursorShape.PointingHandCursor)
            action.setStyleSheet(
                "QPushButton#CompanyAction { background: #2367B1; color: white;"
                " border: none; border-radius: 8px; padding: 9px 14px;"
                " font-size: 12px; font-weight: 700; }"
                "QPushButton#CompanyAction:hover { background: #174F8C; }"
            )
            action.clicked.connect(
                lambda checked=False, target=route: self._open_company_action(target)
            )
            panel.addWidget(action, alignment=Qt.AlignmentFlag.AlignRight)
            grid.addWidget(card, i // 2, i % 2)

        layout.addWidget(grid_holder)
        footer = QLabel(
            "Các chức năng hỗ trợ chuyên môn được sắp xếp riêng trong menu bên trái."
        )
        footer.setWordWrap(True)
        footer.setStyleSheet(
            "QLabel { color: #697B92; background: transparent; font-size: 12px; }"
        )
        layout.addWidget(footer)
        layout.addStretch()

    def _open_company_action(self, route: str) -> None:
        if callable(self._on_action):
            self._on_action(route)

    def _make_feature_card(
        self,
        icon: str,
        label: str,
        desc: str,
        accent: str,
        available: bool = False,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("DashboardFeatureCard")
        card.setStyleSheet(f"""
            QFrame#DashboardFeatureCard {{
                background-color: {COLOR_WHITE};
                border-radius: 12px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        card.setMinimumHeight(104)
        cl = QHBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(16)

        icon_box = QWidget()
        icon_box.setFixedSize(44, 44)
        icon_box.setObjectName("FeatureIconBox")
        icon_box.setStyleSheet("QWidget#FeatureIconBox { background: #EAF2FD; border-radius: 12px; }")
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

        status = QLabel("Trong menu" if available else "")
        status.setStyleSheet(f"""
            color: {COLOR_TEXT_MUTED};
            font-size: 10px;
            background: {COLOR_LIGHT_GRAY};
            border-radius: 6px;
            padding: 2px 8px;
        """)
        cl.addWidget(status)

        return card


# ══════════════════════════════════════════════════════════════════════════════
# DashboardScreen
# ══════════════════════════════════════════════════════════════════════════════

class DashboardScreen(QWidget):
    """Dashboard for non-admin roles with callbacks for supported routes."""

    def __init__(self, user: UserModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._user = user
        self._on_logout_cb = None
        self._on_open_candidate_profile_cb = None
        self._on_open_company_profile_cb = None
        self._on_open_expert_profile_cb = None
        self._on_open_expert_search_cb = None
        self._on_open_contracts_cb = None
        self._on_open_tasks_cb = None
        self._on_open_company_recruitment_cb = None
        self._on_open_candidate_assessments_cb = None
        self._on_open_marketplace_cb = None
        self._on_open_extended_workflow_cb = None
        self._setup_ui()
        QTimer.singleShot(80, self._animate_in)

    @property
    def on_logout(self):
        return self._on_logout_cb

    @on_logout.setter
    def on_logout(self, cb):
        self._on_logout_cb = cb

    @property
    def on_open_candidate_profile(self):
        return self._on_open_candidate_profile_cb

    @on_open_candidate_profile.setter
    def on_open_candidate_profile(self, cb):
        self._on_open_candidate_profile_cb = cb
        if self._sidebar:
            self._sidebar.on_open_candidate_profile = cb

    @property
    def on_open_company_profile(self):
        return self._on_open_company_profile_cb

    @on_open_company_profile.setter
    def on_open_company_profile(self, cb):
        self._on_open_company_profile_cb = cb
        if self._sidebar:
            self._sidebar.on_open_company_profile = cb

    @property
    def on_open_expert_profile(self):
        return self._on_open_expert_profile_cb

    @on_open_expert_profile.setter
    def on_open_expert_profile(self, cb):
        self._on_open_expert_profile_cb = cb
        if self._sidebar:
            self._sidebar.on_open_expert_profile = cb

    @property
    def on_open_expert_search(self):
        return self._on_open_expert_search_cb

    @on_open_expert_search.setter
    def on_open_expert_search(self, cb):
        self._on_open_expert_search_cb = cb
        if self._sidebar:
            self._sidebar.on_open_expert_search = cb

    @property
    def on_open_contracts(self):
        return self._on_open_contracts_cb

    @on_open_contracts.setter
    def on_open_contracts(self, cb):
        self._on_open_contracts_cb = cb
        if self._sidebar:
            self._sidebar.on_open_contracts = cb

    @property
    def on_open_tasks(self):
        return self._on_open_tasks_cb

    @on_open_tasks.setter
    def on_open_tasks(self, cb):
        self._on_open_tasks_cb = cb
        if self._sidebar:
            self._sidebar.on_open_tasks = cb

    @property
    def on_open_company_recruitment(self):
        return self._on_open_company_recruitment_cb

    @on_open_company_recruitment.setter
    def on_open_company_recruitment(self, cb):
        self._on_open_company_recruitment_cb = cb
        if self._sidebar:
            self._sidebar.on_open_company_recruitment = cb

    @property
    def on_open_candidate_assessments(self):
        return self._on_open_candidate_assessments_cb

    @on_open_candidate_assessments.setter
    def on_open_candidate_assessments(self, cb):
        self._on_open_candidate_assessments_cb = cb
        if self._sidebar:
            self._sidebar.on_open_candidate_assessments = cb

    @property
    def on_open_marketplace(self):
        return self._on_open_marketplace_cb

    @on_open_marketplace.setter
    def on_open_marketplace(self, callback):
        self._on_open_marketplace_cb = callback
        if self._sidebar:
            self._sidebar.on_open_marketplace = self._handle_open_marketplace

    @property
    def on_open_extended_workflow(self):
        return self._on_open_extended_workflow_cb

    @on_open_extended_workflow.setter
    def on_open_extended_workflow(self, callback):
        self._on_open_extended_workflow_cb = callback
        if self._sidebar:
            self._sidebar.on_open_extended_workflow = self._handle_open_extended_workflow

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = _Sidebar(self._user)
        self._sidebar.on_logout = self._handle_logout
        self._sidebar.on_open_candidate_profile = self._handle_open_candidate_profile
        self._sidebar.on_open_company_profile = self._handle_open_company_profile
        self._sidebar.on_open_expert_profile = self._handle_open_expert_profile
        self._sidebar.on_open_expert_search = self._handle_open_expert_search
        self._sidebar.on_open_contracts = self._handle_open_contracts
        self._sidebar.on_open_tasks = self._handle_open_tasks
        self._sidebar.on_open_company_recruitment = self._handle_open_company_recruitment
        self._sidebar.on_open_candidate_assessments = self._handle_open_candidate_assessments
        self._sidebar.on_open_marketplace = self._handle_open_marketplace
        self._sidebar.on_open_extended_workflow = self._handle_open_extended_workflow

        self._content = _ContentArea(self._user, on_action=self._open_company_action)

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

    def _open_company_action(self, route: str) -> None:
        actions = {
            "positions": self._handle_open_company_recruitment,
            "applicants": self._handle_open_marketplace,
            "interviews": lambda: self._handle_open_extended_workflow("interviews"),
            "grading": lambda: self._handle_open_extended_workflow("manual_grading"),
        }
        action = actions.get(route)
        if action is not None:
            action()

    def _handle_logout(self) -> None:
        auth_controller.logout()
        if callable(self._on_logout_cb):
            self._on_logout_cb()

    def _handle_open_candidate_profile(self) -> None:
        if callable(self._on_open_candidate_profile_cb):
            self._on_open_candidate_profile_cb()

    def _handle_open_company_profile(self) -> None:
        if callable(self._on_open_company_profile_cb):
            self._on_open_company_profile_cb()

    def _handle_open_expert_profile(self) -> None:
        if callable(self._on_open_expert_profile_cb):
            self._on_open_expert_profile_cb()

    def _handle_open_expert_search(self) -> None:
        if callable(self._on_open_expert_search_cb):
            self._on_open_expert_search_cb()

    def _handle_open_contracts(self) -> None:
        if callable(self._on_open_contracts_cb):
            self._on_open_contracts_cb()

    def _handle_open_tasks(self) -> None:
        if callable(self._on_open_tasks_cb):
            self._on_open_tasks_cb()

    def _handle_open_company_recruitment(self) -> None:
        if callable(self._on_open_company_recruitment_cb):
            self._on_open_company_recruitment_cb()

    def _handle_open_candidate_assessments(self) -> None:
        if callable(self._on_open_candidate_assessments_cb):
            self._on_open_candidate_assessments_cb()

    def _handle_open_marketplace(self) -> None:
        if callable(self._on_open_marketplace_cb):
            self._on_open_marketplace_cb()

    def _handle_open_extended_workflow(self, route: str) -> None:
        if callable(self._on_open_extended_workflow_cb):
            self._on_open_extended_workflow_cb(route)
