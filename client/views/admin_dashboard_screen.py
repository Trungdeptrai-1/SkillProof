"""Administrative landing page with explicit status for unavailable features."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.user_model import UserModel
from server.controllers.auth_controller import auth_controller
from app.utils.constants import (
    APP_NAME,
    COLOR_LIGHT_GRAY,
    COLOR_NAVY_DARK,
    COLOR_NAVY_MID,
    COLOR_OFF_WHITE,
    COLOR_TEXT_DARK,
    COLOR_TEXT_MUTED,
    COLOR_WHITE,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from app.utils.styles import primary_button_style


class AdminStatisticsData(Protocol):
    total_users: int
    active_users: int
    inactive_users: int
    deleted_users: int
    candidate_profiles: int
    company_profiles: int
    expert_profiles: int
    total_skills: int
    active_skills: int
    inactive_skills: int


class AdminStatisticsResult(Protocol):
    success: bool
    message: str
    statistics: AdminStatisticsData | None


class AdminDashboardController(Protocol):
    def get_statistics(self) -> AdminStatisticsResult: ...


class AdminDashboardScreen(QWidget):
    """Admin dashboard backed by the administrator Controller."""

    def __init__(
        self,
        user: UserModel,
        parent: QWidget | None = None,
        controller: AdminDashboardController | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._user = user
        self._controller = controller
        self._on_logout_cb: Callable[[], None] | None = None
        self._on_open_users_cb: Callable[[], None] | None = None
        self._on_open_skills_cb: Callable[[], None] | None = None
        self._on_open_certificates_cb: Callable[[], None] | None = None
        self._setup_ui()

    @property
    def on_logout(self) -> Callable[[], None] | None:
        return self._on_logout_cb

    @on_logout.setter
    def on_logout(self, callback: Callable[[], None] | None) -> None:
        self._on_logout_cb = callback

    @property
    def on_open_users(self) -> Callable[[], None] | None:
        return self._on_open_users_cb

    @on_open_users.setter
    def on_open_users(self, callback: Callable[[], None] | None) -> None:
        self._on_open_users_cb = callback

    @property
    def on_open_skills(self) -> Callable[[], None] | None:
        return self._on_open_skills_cb

    @on_open_skills.setter
    def on_open_skills(self, callback: Callable[[], None] | None) -> None:
        self._on_open_skills_cb = callback

    @property
    def on_open_certificates(self) -> Callable[[], None] | None:
        return self._on_open_certificates_cb

    @on_open_certificates.setter
    def on_open_certificates(
        self, callback: Callable[[], None] | None
    ) -> None:
        self._on_open_certificates_cb = callback

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())

        content = QWidget()
        content.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 28, 32, 28)
        content_layout.setSpacing(16)

        header = QFrame()
        header.setStyleSheet(
            f"background:{COLOR_WHITE};border:1px solid {COLOR_LIGHT_GRAY};"
            "border-radius:12px;"
        )
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 20)
        greeting = QLabel(f"Xin chào, {self._user.display_name}")
        greeting.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:13px;")
        title = QLabel("Tổng quan quản trị")
        title.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:24px;font-weight:700;"
        )
        subtitle = QLabel(
            "Quản lý các khu vực có giao diện sẵn sàng; dữ liệu chỉ hiển thị "
            "khi được cung cấp bởi Controller."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:13px;")
        header_layout.addWidget(greeting)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        self._statistics_status = QLabel("")
        self._statistics_status.setWordWrap(True)
        header_layout.addWidget(self._statistics_status)
        self._refresh_statistics_button = QPushButton("Làm mới thống kê")
        self._refresh_statistics_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self._refresh_statistics_button.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._refresh_statistics_button.clicked.connect(self.refresh_statistics)
        header_layout.addWidget(
            self._refresh_statistics_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        content_layout.addWidget(header)

        statistics = QHBoxLayout()
        statistics.setSpacing(16)
        users_statistics, self._users_statistics_label = self._statistics_card(
            "Tài khoản"
        )
        profiles_statistics, self._profiles_statistics_label = (
            self._statistics_card("Hồ sơ")
        )
        skills_statistics, self._skills_statistics_label = self._statistics_card(
            "Kỹ năng"
        )
        statistics.addWidget(users_statistics)
        statistics.addWidget(profiles_statistics)
        statistics.addWidget(skills_statistics)
        content_layout.addLayout(statistics)

        cards = QHBoxLayout()
        cards.setSpacing(16)
        users_card, self._users_card_button = self._action_card(
            "Quản lý người dùng",
            "Tìm, lọc và cập nhật trạng thái tài khoản.",
            "Mở giao diện",
            self._open_users,
        )
        skills_card, self._skills_card_button = self._action_card(
            "Quản lý kỹ năng",
            "Tạo, chỉnh sửa và kích hoạt hoặc ngừng sử dụng kỹ năng.",
            "Mở giao diện",
            self._open_skills,
        )
        certificates_card, self._certificates_card_button = self._action_card(
            "Chứng chỉ",
            "Tra cứu, cấp hoặc xác minh theo quyền do Controller cấp.",
            "Mở giao diện",
            self._open_certificates,
        )
        cards.addWidget(users_card)
        cards.addWidget(skills_card)
        cards.addWidget(certificates_card)
        content_layout.addLayout(cards)

        note = QLabel(
            "Số liệu được cập nhật trực tiếp từ hệ thống. "
            "Chọn một chức năng quản trị để tiếp tục."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color:{COLOR_TEXT_DARK};background:{COLOR_WHITE};"
            f"border:1px solid {COLOR_LIGHT_GRAY};border-radius:10px;padding:16px;"
        )
        content_layout.addWidget(note)
        content_layout.addStretch()
        layout.addWidget(content, stretch=1)
        self.refresh_statistics()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(252)
        sidebar.setObjectName("AdminSidebar")
        sidebar.setStyleSheet(
            "QWidget#AdminSidebar{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {COLOR_NAVY_DARK},stop:1 {COLOR_NAVY_MID});}}"
        )
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 28, 20, 20)
        title = QLabel(f"✓  {APP_NAME}")
        title.setStyleSheet(
            f"color:{COLOR_WHITE};font-size:16px;font-weight:700;"
        )
        layout.addWidget(title)
        layout.addSpacing(28)

        identity = QLabel(
            f"{self._user.display_name}\n"
            f"{self._user.email}\nQuản trị viên"
        )
        identity.setWordWrap(True)
        identity.setStyleSheet(
            f"color:{COLOR_WHITE};background:rgba(255,255,255,0.08);"
            "border-radius:8px;padding:12px;"
        )
        layout.addWidget(identity)
        layout.addSpacing(20)

        self._users_nav_button = QPushButton("  Người dùng")
        self._users_nav_button.clicked.connect(self._open_users)
        self._skills_nav_button = QPushButton("  Danh mục kỹ năng")
        self._skills_nav_button.clicked.connect(self._open_skills)
        self._certificates_nav_button = QPushButton("  Chứng chỉ")
        self._certificates_nav_button.clicked.connect(self._open_certificates)
        for button in (
            self._users_nav_button,
            self._skills_nav_button,
            self._certificates_nav_button,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton{background:transparent;color:rgba(255,255,255,0.85);"
                "border:0;text-align:left;padding:10px;border-radius:8px;}"
                "QPushButton:hover{background:rgba(255,255,255,0.12);}"
            )
            layout.addWidget(button)
        layout.addStretch()

        self._logout_button = QPushButton("  Đăng xuất")
        self._logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._logout_button.setStyleSheet(
            "QPushButton{background:rgba(231,76,60,0.15);color:#FF8888;"
            "border:1px solid rgba(231,76,60,0.4);border-radius:8px;"
            "text-align:left;padding:10px;}"
            "QPushButton:hover{background:rgba(231,76,60,0.3);}"
        )
        self._logout_button.clicked.connect(self._logout)
        layout.addWidget(self._logout_button)
        return sidebar

    def _action_card(
        self,
        title: str,
        description: str,
        button_text: str,
        callback: Callable[[], None],
    ) -> tuple[QFrame, QPushButton]:
        card = QFrame()
        card.setObjectName("AdminActionCard")
        card.setMinimumHeight(190)
        card.setStyleSheet(
            f"QFrame#AdminActionCard {{ background:{COLOR_WHITE};border:1px solid {COLOR_LIGHT_GRAY};"
            "border-radius:14px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:16px;font-weight:700;"
        )
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet(
            f"color:{COLOR_TEXT_MUTED};font-size:12px;"
        )
        button = QPushButton(button_text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(primary_button_style(font_size=12, padding="8px 14px"))
        button.clicked.connect(callback)
        card_layout.addWidget(title_label)
        card_layout.addWidget(description_label)
        card_layout.addStretch()
        card_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        return card, button

    @staticmethod
    def _statistics_card(title: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("AdminMetricCard")
        card.setMinimumHeight(130)
        card.setStyleSheet(
            f"QFrame#AdminMetricCard {{ background:{COLOR_WHITE};border:1px solid {COLOR_LIGHT_GRAY};"
            "border-radius:14px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:15px;font-weight:700;"
        )
        value_label = QLabel("Đang tải...")
        value_label.setWordWrap(True)
        value_label.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:12px;")
        layout.addWidget(title_label)
        layout.addWidget(value_label, stretch=1)
        return card, value_label

    def refresh_statistics(self) -> None:
        if self._controller is None:
            self._show_statistics_error(
                "Chưa có Admin Controller để tải thống kê."
            )
            return

        result = self._controller.get_statistics()
        if not result.success or result.statistics is None:
            self._show_statistics_error(
                result.message or "Không thể tải thống kê quản trị."
            )
            return

        statistics = result.statistics
        self._users_statistics_label.setText(
            f"Tổng chưa xóa: {statistics.total_users} | Đang hoạt động: "
            f"{statistics.active_users} | Đã khóa: {statistics.inactive_users} "
            f"| Đã xóa: {statistics.deleted_users}"
        )
        self._profiles_statistics_label.setText(
            f"Candidate: {statistics.candidate_profiles} | "
            f"Company: {statistics.company_profiles} | "
            f"Expert: {statistics.expert_profiles}"
        )
        self._skills_statistics_label.setText(
            f"Tổng: {statistics.total_skills} | Đang dùng: "
            f"{statistics.active_skills} | Ngừng dùng: "
            f"{statistics.inactive_skills}"
        )
        self._statistics_status.setStyleSheet(
            f"color:{COLOR_TEXT_MUTED};font-size:12px;"
        )
        self._statistics_status.setText("Thống kê đã được cập nhật.")

    def _show_statistics_error(self, message: str) -> None:
        self._statistics_status.setStyleSheet(
            "color:#B42318;font-size:12px;font-weight:600;"
        )
        self._statistics_status.setText(message)

    def _open_users(self) -> None:
        if self._on_open_users_cb is not None:
            self._on_open_users_cb()

    def _open_skills(self) -> None:
        if self._on_open_skills_cb is not None:
            self._on_open_skills_cb()

    def _open_certificates(self) -> None:
        if self._on_open_certificates_cb is not None:
            self._on_open_certificates_cb()

    def _logout(self) -> None:
        auth_controller.logout()
        if self._on_logout_cb is not None:
            self._on_logout_cb()
