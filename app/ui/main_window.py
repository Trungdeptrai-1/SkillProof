"""
Cửa sổ chính của ứng dụng SkillProof.
Hiện tại chứa WelcomeScreen; sau này sẽ mở rộng thêm các màn hình nghiệp vụ.
"""

from __future__ import annotations

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QIcon
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from app.ui.screens.welcome_screen import WelcomeScreen
from app.utils.constants import (
    APP_NAME, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
)


class MainWindow(QMainWindow):
    """Cửa sổ gốc của SkillProof."""

    def __init__(self) -> None:
        super().__init__()
        self._setup_window()
        self._setup_central_widget()
        self._show_welcome()

    # ── Cấu hình cửa sổ ──────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        # Căn giữa màn hình
        screen = self.screen().availableGeometry()
        x = (screen.width()  - WINDOW_DEFAULT_WIDTH)  // 2
        y = (screen.height() - WINDOW_DEFAULT_HEIGHT) // 2
        self.move(x, y)

    # ── Widget trung tâm (stack để chuyển màn hình sau này) ──────────────────

    def _setup_central_widget(self) -> None:
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

    # ── Các màn hình ─────────────────────────────────────────────────────────

    def _show_welcome(self) -> None:
        """Hiển thị màn hình chào mừng."""
        self._welcome = WelcomeScreen()
        self._welcome.on_get_started = self._on_get_started
        self._welcome.on_learn_more  = self._on_learn_more

        self._stack.addWidget(self._welcome)
        self._stack.setCurrentWidget(self._welcome)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_get_started(self) -> None:
        """
        Xử lý khi người dùng nhấn 'Bắt đầu sử dụng'.
        TODO: chuyển sang màn hình Dashboard / Login sau khi lập trình nghiệp vụ.
        """
        QMessageBox.information(
            self,
            "Sắp ra mắt",
            "🚀 Chức năng đang được phát triển.\n\nCác tính năng sẽ sớm khả dụng!",
        )

    def _on_learn_more(self) -> None:
        """
        Xử lý khi người dùng nhấn 'Tìm hiểu thêm'.
        TODO: mở màn hình giới thiệu / tài liệu.
        """
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
        db.close()
        event.accept()
