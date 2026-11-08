"""
LoginScreen — Màn hình đăng nhập SkillProof.
Thiết kế 2 panel thống nhất với WelcomeScreen:
  - Trái: Brand panel navy gradient
  - Phải: Form đăng nhập trên nền trắng
"""

from __future__ import annotations

from PySide6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, QTimer, Signal
from PySide6.QtGui     import (
    QColor, QLinearGradient, QPainter, QPainterPath, QBrush,
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QSizePolicy,
    QGraphicsOpacityEffect,
)

from app.utils.constants import (
    APP_NAME, APP_VERSION,
    COLOR_NAVY_DARK, COLOR_NAVY, COLOR_NAVY_MID, COLOR_NAVY_LIGHT,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, COLOR_ERROR,
    WELCOME_WIDTH, WELCOME_HEIGHT,
)
from app.utils.styles import primary_button_style
from app.services.auth_service import auth_service, LoginResult


# ══════════════════════════════════════════════════════════════════════════════
# Brand panel (bên trái) — tái sử dụng phong cách từ WelcomeScreen
# ══════════════════════════════════════════════════════════════════════════════

class _LoginBrandPanel(QWidget):
    """Panel navy bên trái — thương hiệu và slogan đăng nhập."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(360)
        self._setup_ui()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(COLOR_NAVY_DARK))
        gradient.setColorAt(0.5, QColor(COLOR_NAVY))
        gradient.setColorAt(1.0, QColor(COLOR_NAVY_MID))
        path = QPainterPath()
        path.addRect(0, 0, self.width(), self.height())
        painter.fillPath(path, QBrush(gradient))
        # Vòng tròn trang trí
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 10)))
        painter.drawEllipse(-60, -60, 300, 300)
        painter.setBrush(QBrush(QColor(255, 255, 255, 6)))
        painter.drawEllipse(self.width() - 140, self.height() - 180, 260, 260)
        painter.setBrush(QBrush(QColor(46, 134, 222, 35)))
        painter.drawEllipse(30, self.height() - 100, 160, 160)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 50, 40, 40)
        layout.setSpacing(0)

        # Logo
        logo_box = QWidget()
        logo_box.setFixedSize(64, 64)
        logo_box.setStyleSheet(f"background-color: {COLOR_ACCENT}; border-radius: 18px;")
        logo_inner = QVBoxLayout(logo_box)
        logo_inner.setContentsMargins(0, 0, 0, 0)
        logo_lbl = QLabel("✓")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet(f"color:{COLOR_WHITE}; font-size:30px; font-weight:700; background:transparent;")
        logo_inner.addWidget(logo_lbl)
        layout.addWidget(logo_box)

        layout.addSpacing(24)

        title = QLabel(APP_NAME)
        title.setStyleSheet(f"color:{COLOR_WHITE}; font-size:34px; font-weight:700; letter-spacing:1px; background:transparent;")
        layout.addWidget(title)

        ver = QLabel(f"v{APP_VERSION}")
        ver.setStyleSheet(f"color:rgba(255,255,255,0.5); font-size:12px; background:transparent; margin-top:2px;")
        layout.addWidget(ver)

        layout.addSpacing(32)

        tagline = QLabel("Chào mừng trở lại!")
        tagline.setStyleSheet(f"color:rgba(255,255,255,0.95); font-size:20px; font-weight:600; background:transparent;")
        layout.addWidget(tagline)

        layout.addSpacing(12)

        sub = QLabel(
            "Đăng nhập để tiếp tục\nquản lý và chứng nhận\nkỹ năng của bạn."
        )
        sub.setStyleSheet(f"color:rgba(255,255,255,0.65); font-size:13px; line-height:1.6; background:transparent;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        layout.addSpacing(32)

        # Gạch ngang trang trí
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: rgba(255,255,255,0.2);")
        layout.addWidget(divider)

        layout.addSpacing(20)

        # Tính năng nhanh
        features = [
            ("🎯", "Đánh giá năng lực chuyên nghiệp"),
            ("📜", "Cấp chứng nhận kỹ năng"),
            ("📊", "Theo dõi lộ trình học tập"),
        ]
        for icon, text in features:
            row = QWidget()
            row.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 4, 0, 4)
            rl.setSpacing(10)
            il = QLabel(icon)
            il.setStyleSheet("font-size:16px; background:transparent;")
            il.setFixedWidth(24)
            tl = QLabel(text)
            tl.setStyleSheet(f"color:rgba(255,255,255,0.7); font-size:12px; background:transparent;")
            rl.addWidget(il)
            rl.addWidget(tl)
            rl.addStretch()
            layout.addWidget(row)

        layout.addStretch()

        footer = QLabel("© 2024 SkillProof Team")
        footer.setStyleSheet(f"color:rgba(255,255,255,0.3); font-size:11px; background:transparent;")
        layout.addWidget(footer)


# ══════════════════════════════════════════════════════════════════════════════
# Form panel (bên phải)
# ══════════════════════════════════════════════════════════════════════════════

class _LoginFormPanel(QWidget):
    """Panel trắng bên phải — form đăng nhập."""

    # Signal nội bộ để báo đăng nhập thành công lên LoginScreen
    login_success = Signal(object)   # payload: UserModel

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {COLOR_OFF_WHITE};")
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Căn giữa theo chiều dọc
        outer.addStretch(2)

        # Card trung tâm
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_WHITE};
                border-radius: 16px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        card.setFixedWidth(400)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 36, 40, 36)
        card_layout.setSpacing(0)

        # ── Tiêu đề form ──────────────────────────────────────────────────────
        heading = QLabel("Đăng nhập")
        heading.setStyleSheet(f"color:{COLOR_NAVY_DARK}; font-size:24px; font-weight:700;")
        card_layout.addWidget(heading)

        subheading = QLabel("Nhập thông tin tài khoản của bạn")
        subheading.setStyleSheet(f"color:{COLOR_TEXT_MUTED}; font-size:13px; margin-top:4px;")
        card_layout.addWidget(subheading)

        card_layout.addSpacing(28)

        # ── Email ─────────────────────────────────────────────────────────────
        email_label = QLabel("Email")
        email_label.setStyleSheet(f"color:{COLOR_TEXT_DARK}; font-size:13px; font-weight:600;")
        card_layout.addWidget(email_label)
        card_layout.addSpacing(6)

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("example@email.com")
        self._email_input.setFixedHeight(44)
        self._email_input.setStyleSheet(self._input_style())
        self._email_input.returnPressed.connect(self._on_login_clicked)
        card_layout.addWidget(self._email_input)

        card_layout.addSpacing(16)

        # ── Mật khẩu ─────────────────────────────────────────────────────────
        pw_label_row = QHBoxLayout()
        pw_label = QLabel("Mật khẩu")
        pw_label.setStyleSheet(f"color:{COLOR_TEXT_DARK}; font-size:13px; font-weight:600;")
        pw_label_row.addWidget(pw_label)
        pw_label_row.addStretch()
        card_layout.addLayout(pw_label_row)
        card_layout.addSpacing(6)

        # Wrapper chứa input + nút hiện/ẩn
        pw_wrapper = QFrame()
        pw_wrapper.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_WHITE};
                border: 1.5px solid {COLOR_LIGHT_GRAY};
                border-radius: 8px;
            }}
            QFrame:focus-within {{
                border-color: {COLOR_ACCENT};
            }}
        """)
        pw_wrapper.setFixedHeight(44)
        pw_layout = QHBoxLayout(pw_wrapper)
        pw_layout.setContentsMargins(12, 0, 4, 0)
        pw_layout.setSpacing(0)

        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("Nhập mật khẩu")
        self._password_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 13px;
                color: #0A1628;
                padding: 0px;
            }
        """)
        self._password_input.returnPressed.connect(self._on_login_clicked)
        pw_layout.addWidget(self._password_input)

        self._toggle_pw_btn = QPushButton("👁")
        self._toggle_pw_btn.setFixedSize(32, 32)
        self._toggle_pw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_pw_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-size: 16px;
                color: {COLOR_TEXT_MUTED};
                border-radius: 6px;
            }}
            QPushButton:hover {{ color: {COLOR_ACCENT}; }}
        """)
        self._toggle_pw_btn.setToolTip("Hiện/ẩn mật khẩu")
        self._toggle_pw_btn.clicked.connect(self._toggle_password_visibility)
        self._pw_visible = False
        pw_layout.addWidget(self._toggle_pw_btn)

        card_layout.addWidget(pw_wrapper)
        card_layout.addSpacing(20)

        # ── Nút đăng nhập ─────────────────────────────────────────────────────
        self._login_btn = QPushButton("Đăng nhập")
        self._login_btn.setFixedHeight(46)
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.setStyleSheet(primary_button_style(font_size=15, padding="10px 0"))
        self._login_btn.clicked.connect(self._on_login_clicked)
        card_layout.addWidget(self._login_btn)

        card_layout.addSpacing(16)

        # ── Thông báo lỗi / thành công ────────────────────────────────────────
        self._msg_label = QLabel("")
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setWordWrap(True)
        self._msg_label.setStyleSheet(f"color:{COLOR_ERROR}; font-size:12px; min-height:20px;")
        self._msg_label.hide()
        card_layout.addWidget(self._msg_label)

        # Card căn giữa trong outer layout
        center_h = QHBoxLayout()
        center_h.addStretch()
        center_h.addWidget(card)
        center_h.addStretch()
        outer.addLayout(center_h)

        outer.addStretch(2)

        # ── Footer ────────────────────────────────────────────────────────────
        footer_lbl = QLabel("Liên hệ quản trị viên nếu bạn chưa có tài khoản.")
        footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED}; font-size:11px; margin-bottom:16px;")
        outer.addWidget(footer_lbl)

    # ── Input style ───────────────────────────────────────────────────────────

    def _input_style(self, error: bool = False) -> str:
        border = COLOR_ERROR if error else COLOR_LIGHT_GRAY
        return f"""
            QLineEdit {{
                background-color: {COLOR_WHITE};
                color: {COLOR_TEXT_DARK};
                border: 1.5px solid {border};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {COLOR_ACCENT if not error else COLOR_ERROR};
            }}
            QLineEdit:hover {{
                border-color: {COLOR_NAVY_LIGHT if not error else COLOR_ERROR};
            }}
        """

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _toggle_password_visibility(self) -> None:
        self._pw_visible = not self._pw_visible
        if self._pw_visible:
            self._password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_pw_btn.setText("🙈")
        else:
            self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_pw_btn.setText("👁")

    def _show_message(self, text: str, is_error: bool = True) -> None:
        color = COLOR_ERROR if is_error else COLOR_SUCCESS
        self._msg_label.setStyleSheet(
            f"color:{color}; font-size:12px; min-height:20px;"
        )
        self._msg_label.setText(text)
        self._msg_label.show()

    def _clear_message(self) -> None:
        self._msg_label.hide()
        self._msg_label.setText("")

    def _set_input_error(self, field: str) -> None:
        """Highlight input bị lỗi."""
        if field == "email":
            self._email_input.setStyleSheet(self._input_style(error=True))
        elif field == "password":
            self._password_input.setStyleSheet("""
                QLineEdit {
                    border: none;
                    background: transparent;
                    font-size: 13px;
                    color: #E74C3C;
                    padding: 0px;
                }
            """)

    def _reset_input_styles(self) -> None:
        self._email_input.setStyleSheet(self._input_style(error=False))
        self._password_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 13px;
                color: #0A1628;
                padding: 0px;
            }
        """)

    def _on_login_clicked(self) -> None:
        """Xử lý nhấn nút Đăng nhập."""
        self._reset_input_styles()
        self._clear_message()

        email    = self._email_input.text()
        password = self._password_input.text()

        # Disable nút tránh double-click
        self._login_btn.setEnabled(False)
        self._login_btn.setText("Đang xử lý...")

        # Gọi service
        result = auth_service.login(email, password)

        # Re-enable nút
        self._login_btn.setEnabled(True)
        self._login_btn.setText("Đăng nhập")

        if result.success:
            self._show_message(f"Đăng nhập thành công! Xin chào {result.user.display_name}.", is_error=False)
            # Xóa password khỏi input ngay sau khi đăng nhập
            self._password_input.clear()
            # Delay nhỏ để user thấy thông báo trước khi chuyển màn hình
            QTimer.singleShot(400, lambda: self.login_success.emit(result.user))
        else:
            # Highlight field lỗi
            if result.status in (LoginResult.EMPTY_EMAIL, LoginResult.INVALID_EMAIL_FORMAT,
                                  LoginResult.USER_NOT_FOUND):
                self._set_input_error("email")
            elif result.status == LoginResult.EMPTY_PASSWORD:
                self._set_input_error("password")
            elif result.status == LoginResult.WRONG_PASSWORD:
                self._set_input_error("password")

            self._show_message(result.message)

    def reset_form(self) -> None:
        """Reset form về trạng thái ban đầu."""
        self._email_input.clear()
        self._password_input.clear()
        self._reset_input_styles()
        self._clear_message()
        self._pw_visible = False
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._toggle_pw_btn.setText("👁")
        self._login_btn.setEnabled(True)
        self._login_btn.setText("Đăng nhập")


# ══════════════════════════════════════════════════════════════════════════════
# LoginScreen — màn hình chính
# ══════════════════════════════════════════════════════════════════════════════

class LoginScreen(QWidget):
    """
    Màn hình đăng nhập gồm 2 panel.

    Kết nối từ MainWindow:
        screen.on_login_success = lambda user: ...
        screen.on_back          = lambda: ...
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WELCOME_WIDTH, WELCOME_HEIGHT)
        self._on_login_success_cb = None
        self._on_back_cb          = None
        self._setup_ui()
        QTimer.singleShot(80, self._animate_in)

    # ── Callback properties ───────────────────────────────────────────────────

    @property
    def on_login_success(self):
        return self._on_login_success_cb

    @on_login_success.setter
    def on_login_success(self, cb):
        self._on_login_success_cb = cb

    @property
    def on_back(self):
        return self._on_back_cb

    @on_back.setter
    def on_back(self, cb):
        self._on_back_cb = cb

    # ── Setup UI ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self._brand_panel = _LoginBrandPanel()
        self._form_panel  = _LoginFormPanel()

        # Kết nối signal từ form
        self._form_panel.login_success.connect(self._handle_login_success)

        # Nút quay lại (trên nền brand panel)
        back_btn = QPushButton("← Quay lại")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: rgba(255,255,255,0.7);
                border: none;
                font-size: 12px;
                font-weight: 500;
                padding: 4px 8px;
            }}
            QPushButton:hover {{ color: {COLOR_WHITE}; }}
        """)
        back_btn.clicked.connect(self._handle_back)

        # Overlay back button lên brand panel góc trên trái
        brand_wrapper = QWidget()
        brand_wrapper.setMinimumWidth(360)
        bw_layout = QVBoxLayout(brand_wrapper)
        bw_layout.setContentsMargins(0, 0, 0, 0)
        bw_layout.setSpacing(0)

        back_row = QHBoxLayout()
        back_row.setContentsMargins(12, 12, 12, 0)
        back_row.addWidget(back_btn)
        back_row.addStretch()

        top_overlay = QWidget()
        top_overlay.setLayout(back_row)
        top_overlay.setStyleSheet("background: transparent;")

        # Stack back button trên brand panel bằng cách đặt vào layout
        inner_stack = QVBoxLayout()
        inner_stack.setContentsMargins(0, 0, 0, 0)
        inner_stack.setSpacing(0)

        # Dùng QWidget để overlay
        container = QWidget()
        container.setMinimumWidth(360)
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        back_bar = QWidget()
        back_bar.setFixedHeight(44)
        back_bar.setStyleSheet("background: transparent;")
        bb_layout = QHBoxLayout(back_bar)
        bb_layout.setContentsMargins(12, 8, 12, 0)
        bb_layout.addWidget(back_btn)
        bb_layout.addStretch()

        cl.addWidget(self._brand_panel)

        # Dùng absolute position sẽ phức tạp với Qt layout.
        # Giải pháp: đặt back_btn vào layout của brand_panel trực tiếp

        main.addWidget(self._brand_panel, stretch=4)
        main.addWidget(self._form_panel,  stretch=5)

        # Thêm back button vào brand panel layout
        self._inject_back_button(back_btn)

    def _inject_back_button(self, btn: QPushButton) -> None:
        """Thêm nút quay lại vào góc trên brand panel."""
        brand_layout = self._brand_panel.layout()
        if brand_layout:
            back_row = QHBoxLayout()
            back_row.setContentsMargins(0, 0, 0, 8)
            back_row.addWidget(btn)
            back_row.addStretch()
            back_widget = QWidget()
            back_widget.setStyleSheet("background: transparent;")
            back_widget.setLayout(back_row)
            brand_layout.insertWidget(0, back_widget)

    # ── Animation ─────────────────────────────────────────────────────────────

    def _animate_in(self) -> None:
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(500)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _handle_login_success(self, user) -> None:
        if callable(self._on_login_success_cb):
            self._on_login_success_cb(user)

    def _handle_back(self) -> None:
        self._form_panel.reset_form()
        if callable(self._on_back_cb):
            self._on_back_cb()

    def reset(self) -> None:
        """Reset form khi màn hình được hiển thị lại."""
        self._form_panel.reset_form()
