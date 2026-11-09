"""
FirstRunScreen — Màn hình thiết lập admin lần đầu.
Hiển thị khi:
  - DB mới hoàn toàn (setup_done='0')
  - Admin seed legacy bị vô hiệu hóa (setup_done='reset_required')

Không hardcode mật khẩu. Admin tự nhập email + mật khẩu mạnh.
"""

from __future__ import annotations

from PySide6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui     import QColor, QLinearGradient, QPainter, QPainterPath, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QSizePolicy,
    QGraphicsOpacityEffect,
)

from app.utils.constants import (
    APP_NAME,
    COLOR_NAVY_DARK, COLOR_NAVY, COLOR_NAVY_MID, COLOR_NAVY_LIGHT,
    COLOR_ACCENT, COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_ERROR,
    WELCOME_WIDTH, WELCOME_HEIGHT,
)
from app.utils.styles  import primary_button_style
from app.utils.helpers import (
    hash_password, is_valid_email, is_strong_password,
)
from app.database.connection import db
from app.database.schema     import mark_setup_done


class FirstRunScreen(QWidget):
    """
    Màn hình thiết lập admin lần đầu.
    Callback: on_setup_complete = lambda: ...
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WELCOME_WIDTH, WELCOME_HEIGHT)
        self._on_complete_cb = None
        self._setup_ui()
        QTimer.singleShot(80, self._animate_in)

    # ── Callback ─────────────────────────────────────────────────────────────

    @property
    def on_setup_complete(self):
        return self._on_complete_cb

    @on_setup_complete.setter
    def on_setup_complete(self, cb):
        self._on_complete_cb = cb

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Brand panel (trái)
        brand = self._make_brand_panel()
        outer.addWidget(brand, stretch=4)

        # Form panel (phải)
        form = self._make_form_panel()
        outer.addWidget(form, stretch=5)

    def _make_brand_panel(self) -> QWidget:
        panel = _GradientWidget()
        panel.setMinimumWidth(340)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(40, 50, 40, 40)
        lay.setSpacing(0)

        logo_box = QWidget()
        logo_box.setFixedSize(64, 64)
        logo_box.setStyleSheet(
            f"background:{COLOR_ACCENT}; border-radius:18px;"
        )
        ll = QVBoxLayout(logo_box); ll.setContentsMargins(0,0,0,0)
        li = QLabel("⚙"); li.setAlignment(Qt.AlignmentFlag.AlignCenter)
        li.setStyleSheet(
            f"color:{COLOR_WHITE};font-size:30px;font-weight:700;background:transparent;"
        )
        ll.addWidget(li)
        lay.addWidget(logo_box)
        lay.addSpacing(24)

        t = QLabel(APP_NAME)
        t.setStyleSheet(
            f"color:{COLOR_WHITE};font-size:30px;font-weight:700;background:transparent;"
        )
        lay.addWidget(t)
        lay.addSpacing(20)

        h = QLabel("Thiết lập lần đầu")
        h.setStyleSheet(
            f"color:rgba(255,255,255,0.9);font-size:18px;font-weight:600;background:transparent;"
        )
        lay.addWidget(h)
        lay.addSpacing(10)

        d = QLabel(
            "Tạo tài khoản quản trị viên để\n"
            "bắt đầu sử dụng hệ thống.\n\n"
            "Mật khẩu sẽ được mã hóa an toàn\n"
            "bằng PBKDF2-SHA256."
        )
        d.setStyleSheet(
            f"color:rgba(255,255,255,0.65);font-size:13px;background:transparent;"
        )
        d.setWordWrap(True)
        lay.addWidget(d)
        lay.addStretch()

        note = QLabel("⚠ Chỉ hiển thị một lần")
        note.setStyleSheet(
            f"color:rgba(255,200,0,0.8);font-size:12px;background:transparent;"
        )
        lay.addWidget(note)
        return panel

    def _make_form_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0,0,0,0)
        outer.addStretch(2)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background:{COLOR_WHITE};
                border-radius:16px;
                border:1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        card.setFixedWidth(420)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(40,36,40,36)
        cl.setSpacing(0)

        heading = QLabel("Tạo tài khoản Quản trị viên")
        heading.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:20px;font-weight:700;"
        )
        cl.addWidget(heading)

        sub = QLabel("Bước này chỉ thực hiện một lần duy nhất.")
        sub.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:12px;margin-top:4px;")
        cl.addWidget(sub)
        cl.addSpacing(24)

        # Full name
        cl.addWidget(self._field_label("Họ và tên"))
        cl.addSpacing(5)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Nguyễn Văn A")
        self._name_input.setFixedHeight(42)
        self._name_input.setStyleSheet(self._input_css())
        cl.addWidget(self._name_input)
        cl.addSpacing(14)

        # Email
        cl.addWidget(self._field_label("Email quản trị"))
        cl.addSpacing(5)
        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("admin@example.com")
        self._email_input.setFixedHeight(42)
        self._email_input.setStyleSheet(self._input_css())
        cl.addWidget(self._email_input)
        cl.addSpacing(14)

        # Password
        cl.addWidget(self._field_label("Mật khẩu (tối thiểu 8 ký tự, có chữ hoa và số)"))
        cl.addSpacing(5)
        self._pw1_input, pw1_wrapper = self._pw_field("Nhập mật khẩu")
        cl.addWidget(pw1_wrapper)
        cl.addSpacing(14)

        # Confirm password
        cl.addWidget(self._field_label("Xác nhận mật khẩu"))
        cl.addSpacing(5)
        self._pw2_input, pw2_wrapper = self._pw_field("Nhập lại mật khẩu")
        self._pw2_input.returnPressed.connect(self._on_submit)
        cl.addWidget(pw2_wrapper)
        cl.addSpacing(22)

        # Submit
        self._submit_btn = QPushButton("Hoàn tất thiết lập")
        self._submit_btn.setFixedHeight(46)
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.setStyleSheet(primary_button_style(font_size=14))
        self._submit_btn.clicked.connect(self._on_submit)
        cl.addWidget(self._submit_btn)
        cl.addSpacing(14)

        self._msg_lbl = QLabel("")
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_lbl.setStyleSheet(f"color:{COLOR_ERROR};font-size:12px;min-height:18px;")
        self._msg_lbl.hide()
        cl.addWidget(self._msg_lbl)

        center = QHBoxLayout()
        center.addStretch(); center.addWidget(card); center.addStretch()
        outer.addLayout(center)
        outer.addStretch(2)
        return panel

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{COLOR_TEXT_DARK};font-size:12px;font-weight:600;"
        )
        return lbl

    def _input_css(self, error: bool = False) -> str:
        border = COLOR_ERROR if error else COLOR_LIGHT_GRAY
        return f"""
            QLineEdit {{
                background:{COLOR_WHITE}; color:{COLOR_TEXT_DARK};
                border:1.5px solid {border}; border-radius:8px;
                padding:8px 12px; font-size:13px;
            }}
            QLineEdit:focus {{ border-color:{COLOR_ACCENT if not error else COLOR_ERROR}; }}
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
            f"QPushButton{{background:transparent;border:none;font-size:15px;"
            f"color:{COLOR_TEXT_MUTED};}}"
            f"QPushButton:hover{{color:{COLOR_ACCENT};}}"
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

    # ── Handler ───────────────────────────────────────────────────────────────

    def _show_msg(self, text: str, ok: bool = False) -> None:
        color = COLOR_SUCCESS if ok else COLOR_ERROR
        self._msg_lbl.setStyleSheet(
            f"color:{color};font-size:12px;min-height:18px;"
        )
        self._msg_lbl.setText(text)
        self._msg_lbl.show()

    def _on_submit(self) -> None:
        self._msg_lbl.hide()
        full_name = self._name_input.text().strip()
        email     = self._email_input.text().strip()
        pw1       = self._pw1_input.text()
        pw2       = self._pw2_input.text()

        # Validate
        if not full_name:
            self._show_msg("Vui lòng nhập họ và tên."); return
        if not is_valid_email(email):
            self._show_msg("Địa chỉ email không hợp lệ."); return
        ok_pw, reason = is_strong_password(pw1)
        if not ok_pw:
            self._show_msg(reason); return
        if pw1 != pw2:
            self._show_msg("Mật khẩu xác nhận không khớp."); return

        # Kiểm tra email chưa dùng
        existing = db.fetchone("SELECT id FROM users WHERE email=?", (email,))
        if existing:
            self._show_msg("Email này đã được sử dụng."); return

        # Tạo tài khoản admin
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Đang xử lý...")
        try:
            pw_hash = hash_password(pw1)
            # Xác định username: lấy phần trước @ của email
            username = email.split("@")[0]
            # Đảm bảo username unique
            existing_uname = db.fetchone(
                "SELECT id FROM users WHERE username=?", (username,)
            )
            if existing_uname:
                username = f"{username}_admin"

            db.execute(
                "INSERT INTO users(username,email,password,full_name,role,is_active)"
                " VALUES(?,?,?,?,'admin',1)",
                (username, email, pw_hash, full_name),
            )
            mark_setup_done()
            # Xóa plain password khỏi bộ nhớ
            pw1 = pw2 = ""
            self._pw1_input.clear()
            self._pw2_input.clear()

            self._show_msg("Thiết lập hoàn tất! Đang chuyển sang đăng nhập...", ok=True)
            QTimer.singleShot(1200, self._complete)
        except Exception as exc:
            self._submit_btn.setEnabled(True)
            self._submit_btn.setText("Hoàn tất thiết lập")
            self._show_msg(f"Lỗi: {exc}")

    def _complete(self) -> None:
        if callable(self._on_complete_cb):
            self._on_complete_cb()

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


class _GradientWidget(QWidget):
    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, QColor(COLOR_NAVY_DARK))
        g.setColorAt(0.5, QColor(COLOR_NAVY))
        g.setColorAt(1.0, QColor(COLOR_NAVY_MID))
        path = QPainterPath()
        path.addRect(0, 0, self.width(), self.height())
        p.fillPath(path, QBrush(g))
