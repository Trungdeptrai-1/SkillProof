"""
Cửa sổ chính của ứng dụng SkillProof.
Navigation: WelcomeScreen → LoginScreen → DashboardScreen → (logout) → LoginScreen
"""

from __future__ import annotations

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from app.ui.screens.welcome_screen   import WelcomeScreen
from app.ui.screens.login_screen     import LoginScreen
from app.ui.screens.dashboard_screen import DashboardScreen
from app.models.user_model           import UserModel
from app.utils.constants import (
    APP_NAME, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
)


class MainWindow(QMainWindow):
    """Cửa sổ gốc của SkillProof."""

    def __init__(self) -> None:
        super().__init__()
        self._dashboard: DashboardScreen | None = None
        self._setup_window()
        self._setup_central_widget()
        self._show_welcome()

    # ── Cấu hình cửa sổ ──────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
        screen = self.screen().availableGeometry()
        x = (screen.width()  - WINDOW_DEFAULT_WIDTH)  // 2
        y = (screen.height() - WINDOW_DEFAULT_HEIGHT) // 2
        self.move(x, y)

    def _setup_central_widget(self) -> None:
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

    # ── Màn hình chào mừng ───────────────────────────────────────────────────

    def _show_welcome(self) -> None:
        self._welcome = WelcomeScreen()
        self._welcome.on_get_started = self._on_go_to_login
        self._welcome.on_learn_more  = self._on_learn_more
        self._stack.addWidget(self._welcome)
        self._stack.setCurrentWidget(self._welcome)

    # ── Màn hình đăng nhập ───────────────────────────────────────────────────

    def _show_login(self) -> None:
        """Khởi tạo LoginScreen lần đầu hoặc reset nếu đã có."""
        if not hasattr(self, "_login"):
            self._login = LoginScreen()
            self._login.on_login_success = self._on_login_success
            self._login.on_back          = self._on_back_to_welcome
            self._stack.addWidget(self._login)
        else:
            self._login.reset()
        self._stack.setCurrentWidget(self._login)

    # ── Màn hình dashboard ───────────────────────────────────────────────────

    def _show_dashboard(self, user: UserModel) -> None:
        """Tạo mới DashboardScreen mỗi lần đăng nhập (user có thể khác)."""
        # Xóa dashboard cũ nếu có
        if self._dashboard is not None:
            self._stack.removeWidget(self._dashboard)
            self._dashboard.deleteLater()
            self._dashboard = None

        self._dashboard = DashboardScreen(user)
        self._dashboard.on_logout = self._on_logout
        self._stack.addWidget(self._dashboard)
        self._stack.setCurrentWidget(self._dashboard)

    # ── Handlers navigation ───────────────────────────────────────────────────

    def _on_go_to_login(self) -> None:
        """Welcome → Login."""
        self._show_login()

    def _on_back_to_welcome(self) -> None:
        """Login → Welcome."""
        self._stack.setCurrentWidget(self._welcome)

    def _on_login_success(self, user: UserModel) -> None:
        """Login → Dashboard."""
        self._show_dashboard(user)

    def _on_logout(self) -> None:
        """Dashboard → Login (reset form)."""
        self._show_login()

    def _on_learn_more(self) -> None:
        QMessageBox.information(
            self,
            "Về SkillProof",
            (
                f"<b>{APP_NAME}</b><br><br>"
                "Hệ thống quản lý và chứng nhận kỹ năng chuyên nghiệp.<br><br>"
                "<b>Các tính năng chính:</b><br>"
                "• Quản lý hồ sơ kỹ năng cá nhân<br>"
                "• Đánh giá năng lực theo chuẩn<br>"
                "• Cấp và xác thực chứng chỉ<br>"
                "• Theo dõi lộ trình học tập<br>"
                "• Quản lý khoá học và giảng viên"
            ),
        )

    # ── Đóng ứng dụng ────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        from app.database.connection import db
        from app.services.auth_service import auth_service
        auth_service.logout()
        db.close()
        event.accept()
