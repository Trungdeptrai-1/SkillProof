"""
Cửa sổ chính SkillProof.
Navigation: FirstRunSetup (nếu cần) → Welcome → Login → Dashboard → Logout
"""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from app.ui.screens.welcome_screen    import WelcomeScreen
from app.ui.screens.login_screen      import LoginScreen
from app.ui.screens.register_screen   import RegisterScreen
from app.ui.screens.dashboard_screen  import DashboardScreen
from app.ui.screens.first_run_screen  import FirstRunScreen
from app.ui.screens.company_profile_screen import CompanyProfileScreen
from app.models.user_model            import UserModel
from app.utils.constants import (
    APP_NAME,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
)


class MainWindow(QMainWindow):
    """Cửa sổ gốc SkillProof."""

    def __init__(self) -> None:
        super().__init__()
        self._dashboard: DashboardScreen | None = None
        self._first_run: FirstRunScreen | None  = None
        self._register:  RegisterScreen | None  = None
        self._company_profile: CompanyProfileScreen | None = None
        self._setup_window()
        self._setup_central_widget()
        self._route_initial()

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

    # ── Routing ban đầu ───────────────────────────────────────────────────────

    def _route_initial(self) -> None:
        """Kiểm tra setup_done để chọn màn hình đầu tiên."""
        from app.database.schema import is_first_run
        if is_first_run():
            self._show_first_run()
        else:
            self._show_welcome()

    # ── FirstRun Setup ────────────────────────────────────────────────────────

    def _show_first_run(self) -> None:
        self._first_run = FirstRunScreen()
        self._first_run.on_setup_complete = self._on_first_run_done
        self._stack.addWidget(self._first_run)
        self._stack.setCurrentWidget(self._first_run)

    def _on_first_run_done(self) -> None:
        """Setup xong → chuyển sang Welcome."""
        self._show_welcome()

    # ── Welcome ───────────────────────────────────────────────────────────────

    def _show_welcome(self) -> None:
        if not hasattr(self, "_welcome"):
            self._welcome = WelcomeScreen()
            self._welcome.on_get_started = self._on_go_to_login
            self._welcome.on_learn_more  = self._on_learn_more
            self._stack.addWidget(self._welcome)
        self._stack.setCurrentWidget(self._welcome)

    # ── Login ─────────────────────────────────────────────────────────────────

    def _show_login(self) -> None:
        if not hasattr(self, "_login"):
            self._login = LoginScreen()
            self._login.on_login_success = self._on_login_success
            self._login.on_back          = self._on_back_to_welcome
            self._login.on_go_register   = self._show_register
            self._stack.addWidget(self._login)
        else:
            self._login.reset()
        self._stack.setCurrentWidget(self._login)

    # ── Register ──────────────────────────────────────────────────────────────

    def _show_register(self) -> None:
        """Hiển thị màn hình đăng ký (tạo mới hoặc reset)."""
        if self._register is not None:
            self._stack.removeWidget(self._register)
            self._register.deleteLater()
            self._register = None

        self._register = RegisterScreen()
        self._register.on_register_success = self._on_register_success
        self._register.on_back_to_login    = self._on_back_to_login
        self._stack.addWidget(self._register)
        self._stack.setCurrentWidget(self._register)

    def _on_register_success(self, user: UserModel) -> None:
        """Đăng ký xong → chuyển về Login để user đăng nhập."""
        self._show_login()

    def _on_back_to_login(self) -> None:
        """Register → Login."""
        self._show_login()

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _show_dashboard(self, user: UserModel) -> None:
        if self._dashboard is not None:
            self._stack.removeWidget(self._dashboard)
            self._dashboard.deleteLater()
            self._dashboard = None

        self._dashboard = DashboardScreen(user)
        self._dashboard.on_logout = self._on_logout
        self._stack.addWidget(self._dashboard)
        self._stack.setCurrentWidget(self._dashboard)

    # ── Company Profile ───────────────────────────────────────────────────────

    def _show_company_profile(self) -> None:
        """Hiển thị màn hình hồ sơ doanh nghiệp (chỉ role='company')."""
        from app.services.auth_service import SessionManager
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return
        if session.current_user.role != "company":
            return  # Không hiển thị cho role khác

        if self._company_profile is not None:
            self._stack.removeWidget(self._company_profile)
            self._company_profile.deleteLater()
            self._company_profile = None

        self._company_profile = CompanyProfileScreen()
        self._company_profile.on_back = self._on_company_profile_back
        self._stack.addWidget(self._company_profile)
        self._stack.setCurrentWidget(self._company_profile)

    def _on_company_profile_back(self) -> None:
        """Company Profile → Dashboard."""
        if self._dashboard is not None:
            self._stack.setCurrentWidget(self._dashboard)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_go_to_login(self) -> None:
        self._show_login()

    def _on_back_to_welcome(self) -> None:
        self._stack.setCurrentWidget(self._welcome)

    def _on_login_success(self, user: UserModel) -> None:
        self._show_dashboard(user)

    def _on_logout(self) -> None:
        self._show_login()

    def _on_learn_more(self) -> None:
        QMessageBox.information(
            self, "Về SkillProof",
            f"<b>{APP_NAME}</b><br><br>"
            "Hệ thống quản lý và chứng nhận kỹ năng chuyên nghiệp.<br><br>"
            "<b>Tính năng:</b><br>"
            "• Quản lý hồ sơ kỹ năng<br>"
            "• Đánh giá năng lực theo chuẩn<br>"
            "• Cấp và xác thực chứng chỉ<br>"
            "• Theo dõi lộ trình học tập",
        )

    # ── Đóng ứng dụng ────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        from app.database.connection import db
        from app.services.auth_service import auth_service
        auth_service.logout()
        db.close()
        event.accept()
