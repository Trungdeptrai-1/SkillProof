"""
RegisterScreen — Màn hình đăng ký tài khoản ứng viên.
Thiết kế 2-panel thống nhất với LoginScreen.
  - Trái: Brand panel navy gradient
  - Phải: Form đăng ký trên nền trắng
"""

from __future__ import annotations

from PySide6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui     import QColor, QLinearGradient, QPainter, QPainterPath, QBrush
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QSizePolicy,
    QGraphicsOpacityEffect,
)

from app.utils.constants import (
    APP_NAME, APP_VERSION,
    COLOR_NAVY_DARK, COLOR_NAVY, COLOR_NAVY_MID, COLOR_NAVY_LIGHT,
    COLOR_ACCENT, COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, COLOR_ERROR,
    WELCOME_WIDTH, WELCOME_HEIGHT,
)
from app.utils.styles  import primary_button_style
from app.services.user_service import user_service, RegisterResult


# ══════════════════════════════════════════════════════════════════════════════
# Brand panel
# ══════════════════════════════════════════════════════════════════════════════

class _RegisterBrandPanel(QWidget):
    """Panel navy bên trái — thương hiệu."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(340)
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

        tagline = QLabel("Tham gia SkillProof")
        tagline.setStyleSheet(f"color:rgba(255,255,255,0.95); font-size:20px; font-weight:600; background:transparent;")
        layout.addWidget(tagline)

        layout.addSpacing(12)

        sub = QLabel(
            "Tạo tài khoản ứng viên để\n"
            "xây dựng hồ sơ kỹ năng\n"
            "và nhận chứng chỉ."
        )
        sub.setStyleSheet(f"color:rgba(255,255,255,0.65); font-size:13px; line-height:1.6; background:transparent;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        layout.addStretch()

        note = QLabel("Miễn phí • Bảo mật • PBKDF2-SHA256")
        note.setStyleSheet(f"color:rgba(255,255,255,0.4); font-size:11px; background:transparent;")
        layout.addWidget(note)

        layout.addSpacing(8)
        footer = QLabel("© 2024 SkillProof Team")
        footer.setStyleSheet(f"color:rgba(255,255,255,0.3); font-size:11px; background:transparent;")
        layout.addWidget(footer)


# ══════════════════════════════════════════════════════════════════════════════
# Form panel
# ══════════════════════════════════════════════════════════════════════════════

class _RegisterFormPanel(QWidget):
    """Panel trắng bên phải — form đăng ký."""

    register_success = Signal(object)   # payload: UserModel

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {COLOR_OFF_WHITE};")
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addStretch(1)

        # Card
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_WHITE};
                border-radius: 16px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        card.setFixedWidth(420)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(40, 32, 40, 32)
        cl.setSpacing(0)

        # Heading
        heading = QLabel("Đăng ký tài khoản")
        heading.setStyleSheet(f"color:{COLOR_NAVY_DARK}; font-size:22px; font-weight:700;")
        cl.addWidget(heading)

        sub = QLabel("Tạo tài khoản ứng viên mới")
        sub.setStyleSheet(f"color:{COLOR_TEXT_MUTED}; font-size:12px; margin-top:4px;")
        cl.addWidget(sub)
        cl.addSpacing(22)

        # ── Họ và tên ─────────────────────────────────────────────────────────
        cl.addWidget(self._make_label("Họ và tên"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Nguyễn Văn A")
        self._name_input.setFixedHeight(42)
        self._name_input.setStyleSheet(self._input_css())
        cl.addWidget(self._name_input)
        cl.addSpacing(12)

        # ── Email ──────────────────────────────────────────────────────────────
        cl.addWidget(self._make_label("Email"))
        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("example@email.com")
        self._email_input.setFixedHeight(42)
        self._email_input.setStyleSheet(self._input_css())
        cl.addWidget(self._email_input)
        cl.addSpacing(12)

        # ── Mật khẩu ───────────────────────────────────────────────────────────
        cl.addWidget(self._make_label("Mật khẩu (≥8 ký tự, có chữ hoa và số)"))
        self._pw1_input, pw1_wrap = self._pw_field("Nhập mật khẩu")
        cl.addWidget(pw1_wrap)
        cl.addSpacing(12)

        # ── Xác nhận mật khẩu ──────────────────────────────────────────────────
        cl.addWidget(self._make_label("Xác nhận mật khẩu"))
        self._pw2_input, pw2_wrap = self._pw_field("Nhập lại mật khẩu")
        self._pw2_input.returnPressed.connect(self._on_submit)
        cl.addWidget(pw2_wrap)
        cl.addSpacing(20)

        # ── Nút đăng ký ────────────────────────────────────────────────────────
        self._submit_btn = QPushButton("Đăng ký")
        self._submit_btn.setFixedHeight(46)
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.setStyleSheet(primary_button_style(font_size=15, padding="10px 0"))
        self._submit_btn.clicked.connect(self._on_submit)
        cl.addWidget(self._submit_btn)
        cl.addSpacing(14)

        # ── Thông báo ──────────────────────────────────────────────────────────
        self._msg_lbl = QLabel("")
        self._msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setStyleSheet(f"color:{COLOR_ERROR}; font-size:12px; min-height:18px;")
        self._msg_lbl.hide()
        cl.addWidget(self._msg_lbl)

        # ── Link quay lại đăng nhập ────────────────────────────────────────────
        cl.addSpacing(10)
        self._login_link = QPushButton("← Quay lại đăng nhập")
        self._login_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_link.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_ACCENT};
                border: none;
                font-size: 12px;
                font-weight: 500;
                padding: 4px 0;
            }}
            QPushButton:hover {{ text-decoration: underline; color: {COLOR_NAVY_LIGHT}; }}
        """)
        cl.addWidget(self._login_link)

        # Căn giữa card
        center = QHBoxLayout()
        center.addStretch()
        center.addWidget(card)
        center.addStretch()
        outer.addLayout(center)
        outer.addStretch(1)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{COLOR_TEXT_DARK}; font-size:12px; font-weight:600;")
        return lbl

    def _input_css(self, error: bool = False) -> str:
        border = COLOR_ERROR if error else COLOR_LIGHT_GRAY
        return f"""
            QLineEdit {{
                background-color: {COLOR_WHITE}; color: {COLOR_TEXT_DARK};
                border: 1.5px solid {border}; border-radius: 8px;
                padding: 8px 12px; font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {COLOR_ACCENT if not error else COLOR_ERROR}; }}
        """

    def _pw_field(self, placeholder: str) -> tuple[QLineEdit, QFrame]:
        wrapper = QFrame()
        wrapper.setStyleSheet(f"""
            QFrame {{
                background:{COLOR_WHITE};
                border:1.5px solid {COLOR_LIGHT_GRAY};
                border-radius:8px;
            }}
        """)
        wrapper.setFixedHeight(42)
        wl = QHBoxLayout(wrapper)
        wl.setContentsMargins(12, 0, 4, 0)
        inp = QLineEdit()
        inp.setEchoMode(QLineEdit.EchoMode.Password)
        inp.setPlaceholderText(placeholder)
        inp.setStyleSheet(
            "QLineEdit{border:none;background:transparent;font-size:13px;"
            "color:" + COLOR_TEXT_DARK + ";padding:0;}"
        )
        toggle = QPushButton("👁")
        toggle.setFixedSize(30, 30)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setStyleSheet(
            "QPushButton{background:transparent;border:none;font-size:15px;"
            "color:" + COLOR_TEXT_MUTED + ";}"
            "QPushButton:hover{color:" + COLOR_ACCENT + ";}"
        )
        visible = [False]

        def _toggle():
            visible[0] = not visible[0]
            inp.setEchoMode(
                QLineEdit.EchoMode.Normal if visible[0]
                else QLineEdit.EchoMode.Password
            )
            toggle.setText("🙈" if visible[0] else "👁")

        toggle.clicked.connect(_toggle)
        wl.addWidget(inp)
        wl.addWidget(toggle)
        return inp, wrapper

    # ── Message + error highlight ────────────────────────────────────────────

    def _show_msg(self, text: str, is_error: bool = True) -> None:
        color = COLOR_ERROR if is_error else COLOR_SUCCESS
        self._msg_lbl.setStyleSheet(f"color:{color}; font-size:12px; min-height:18px;")
        self._msg_lbl.setText(text)
        self._msg_lbl.show()

    def _clear_msg(self) -> None:
        self._msg_lbl.hide()
        self._msg_lbl.setText("")

    def _set_error(self, field: str) -> None:
        if field == "full_name":
            self._name_input.setStyleSheet(self._input_css(error=True))
        elif field == "email":
            self._email_input.setStyleSheet(self._input_css(error=True))
        elif field in ("password", "confirm"):
            pass  # Password fields use wrapper — skip inline highlight for simplicity

    def _reset_styles(self) -> None:
        self._name_input.setStyleSheet(self._input_css(error=False))
        self._email_input.setStyleSheet(self._input_css(error=False))

    # ── Submit handler ────────────────────────────────────────────────────────

    def _on_submit(self) -> None:
        self._clear_msg()
        self._reset_styles()

        full_name = self._name_input.text()
        email     = self._email_input.text()
        pw1       = self._pw1_input.text()
        pw2       = self._pw2_input.text()

        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Đang xử lý...")

        result = user_service.register(full_name, email, pw1, pw2)

        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Đăng ký")

        if result.success:
            # Xóa password khỏi input ngay lập tức
            self._pw1_input.clear()
            self._pw2_input.clear()
            self._show_msg(result.message, is_error=False)
            QTimer.singleShot(800, lambda: self.register_success.emit(result.user))
        else:
            # Highlight field lỗi
            if result.status in (RegisterResult.EMPTY_FULL_NAME,):
                self._set_error("full_name")
            elif result.status in (RegisterResult.EMPTY_EMAIL,
                                   RegisterResult.INVALID_EMAIL_FORMAT,
                                   RegisterResult.EMAIL_ALREADY_USED):
                self._set_error("email")
            self._show_msg(result.message)

    def reset_form(self) -> None:
        """Reset form về trạng thái ban đầu."""
        self._name_input.clear()
        self._email_input.clear()
        self._pw1_input.clear()
        self._pw2_input.clear()
        self._reset_styles()
        self._clear_msg()
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Đăng ký")


# ══════════════════════════════════════════════════════════════════════════════
# RegisterScreen
# ══════════════════════════════════════════════════════════════════════════════

class RegisterScreen(QWidget):
    """
    Màn hình đăng ký ứng viên.

    Callbacks từ MainWindow:
        screen.on_register_success = lambda user: ...
        screen.on_back_to_login    = lambda: ...
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WELCOME_WIDTH, WELCOME_HEIGHT)
        self._on_success_cb     = None
        self._on_back_to_login_cb = None
        self._setup_ui()
        QTimer.singleShot(80, self._animate_in)

    # ── Callbacks ────────────────────────────────────────────────────────────

    @property
    def on_register_success(self):
        return self._on_success_cb

    @on_register_success.setter
    def on_register_success(self, cb):
        self._on_success_cb = cb

    @property
    def on_back_to_login(self):
        return self._on_back_to_login_cb

    @on_back_to_login.setter
    def on_back_to_login(self, cb):
        self._on_back_to_login_cb = cb

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self._brand_panel = _RegisterBrandPanel()
        self._form_panel  = _RegisterFormPanel()

        self._form_panel.register_success.connect(self._handle_success)
        self._form_panel._login_link.clicked.connect(self._handle_back)

        main.addWidget(self._brand_panel, stretch=4)
        main.addWidget(self._form_panel,  stretch=5)

    # ── Animation ─────────────────────────────────────────────────────────────

    def _animate_in(self) -> None:
        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self._eff.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._eff, b"opacity")
        self._anim.setDuration(500)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _handle_success(self, user) -> None:
        if callable(self._on_success_cb):
            self._on_success_cb(user)

    def _handle_back(self) -> None:
        self._form_panel.reset_form()
        if callable(self._on_back_to_login_cb):
            self._on_back_to_login_cb()

    def reset(self) -> None:
        """Reset form khi màn hình được hiển thị lại."""
        self._form_panel.reset_form()
