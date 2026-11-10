"""
CompanyProfileScreen — Màn hình quản lý hồ sơ doanh nghiệp.

Chức năng:
- Nếu chưa có hồ sơ → form tạo mới.
- Nếu đã có hồ sơ → hiển thị thông tin + nút chỉnh sửa.
- Chỉnh sửa → lưu → tải lại.
- Nút Hủy để bỏ thay đổi chưa lưu.
- Chỉ hiển thị khi role == 'company'.
"""

from __future__ import annotations

from PySide6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui     import QColor, QLinearGradient, QPainter, QPainterPath, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFrame,
    QSizePolicy, QGraphicsOpacityEffect, QScrollArea,
)

from app.utils.constants import (
    APP_NAME, COLOR_NAVY_DARK, COLOR_NAVY, COLOR_NAVY_MID, COLOR_NAVY_LIGHT,
    COLOR_ACCENT, COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_ERROR,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
)
from app.utils.styles import primary_button_style, secondary_button_style
from app.services.company_profile_service import (
    CompanyProfileService, ProfileResult, CompanyProfileModel,
)
from app.services.auth_service import SessionManager


class CompanyProfileScreen(QWidget):
    """
    Màn hình quản lý hồ sơ doanh nghiệp.

    Callbacks:
        screen.on_back = lambda: ...
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._on_back_cb = None
        self._svc = CompanyProfileService()
        self._profile: CompanyProfileModel | None = None
        self._is_editing = False
        self._setup_ui()
        self._load_profile()
        QTimer.singleShot(80, self._animate_in)

    # ── Callback ──────────────────────────────────────────────────────────────

    @property
    def on_back(self):
        return self._on_back_cb

    @on_back.setter
    def on_back(self, cb):
        self._on_back_cb = cb

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self._sidebar = self._make_sidebar()
        main_layout.addWidget(self._sidebar)

        # Content area (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{COLOR_OFF_WHITE};}}")

        content = QWidget()
        content.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(32, 28, 32, 28)
        self._content_layout.setSpacing(0)

        self._build_header()
        self._build_status_banner()
        self._build_form_card()

        self._content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll, stretch=1)

    def _make_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_NAVY_DARK}, stop:1 {COLOR_NAVY_MID});
            }}
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 28, 20, 20)
        layout.setSpacing(0)

        # Logo + app name
        logo_row = QHBoxLayout()
        logo_box = QWidget()
        logo_box.setFixedSize(36, 36)
        logo_box.setStyleSheet(f"background:{COLOR_ACCENT};border-radius:10px;")
        ll = QVBoxLayout(logo_box); ll.setContentsMargins(0,0,0,0)
        lbl = QLabel("✓")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color:{COLOR_WHITE};font-size:18px;font-weight:700;background:transparent;")
        ll.addWidget(lbl)
        logo_row.addWidget(logo_box)
        logo_row.addSpacing(8)
        app_lbl = QLabel(APP_NAME)
        app_lbl.setStyleSheet(f"color:{COLOR_WHITE};font-size:16px;font-weight:700;background:transparent;")
        logo_row.addWidget(app_lbl)
        logo_row.addStretch()
        layout.addLayout(logo_row)
        layout.addSpacing(28)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.15);")
        layout.addWidget(div)
        layout.addSpacing(20)

        # Menu items
        for icon, text in [
            ("🏢", "Hồ sơ doanh nghiệp"),
            ("📋", "Quản lý hợp đồng"),
            ("🎯", "Phân công nhiệm vụ"),
            ("👤", "Tìm ứng viên"),
            ("📊", "Thống kê"),
        ]:
            btn = QPushButton(f"  {icon}  {text}")
            btn.setFixedHeight(38)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: rgba(255,255,255,0.75);
                    border: none; border-radius: 8px;
                    font-size: 12px; text-align: left; padding-left: 8px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.1); color: {COLOR_WHITE};
                }}
            """)
            layout.addWidget(btn)
            layout.addSpacing(4)

        layout.addStretch()

        # Back button
        back_btn = QPushButton("  ←  Quay lại Dashboard")
        back_btn.setFixedHeight(40)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(46,134,222,0.15);
                color: {COLOR_ACCENT}; border: 1px solid rgba(46,134,222,0.4);
                border-radius: 8px; font-size: 12px; font-weight: 600;
                text-align: left; padding-left: 12px;
            }}
            QPushButton:hover {{ background: rgba(46,134,222,0.3); }}
        """)
        back_btn.clicked.connect(self._handle_back)
        layout.addWidget(back_btn)

        return sidebar

    def _build_header(self) -> None:
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_WHITE}; border-radius: 12px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 20, 24, 20)

        left = QVBoxLayout()
        greeting = QLabel("Hồ sơ doanh nghiệp")
        greeting.setStyleSheet(f"color:{COLOR_NAVY_DARK};font-size:22px;font-weight:700;")
        left.addWidget(greeting)

        sub = QLabel("Quản lý thông tin doanh nghiệp của bạn")
        sub.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:13px;margin-top:4px;")
        left.addWidget(sub)
        left.setSpacing(0)

        hl.addLayout(left)
        hl.addStretch()

        # Verified badge (placeholder)
        self._verified_badge = QLabel("🔒 Chưa xác minh")
        self._verified_badge.setStyleSheet(f"""
            background:{COLOR_LIGHT_GRAY}; color:{COLOR_TEXT_MUTED};
            border-radius:12px; padding:6px 16px;
            font-size:12px; font-weight:600;
        """)
        hl.addWidget(self._verified_badge)

        self._content_layout.addWidget(header)
        self._content_layout.addSpacing(20)

    def _build_status_banner(self) -> None:
        """Banner hiển thị thông báo (thành công/thất bại)."""
        self._banner = QLabel("")
        self._banner.setWordWrap(True)
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setStyleSheet(f"""
            background: transparent; color: {COLOR_ERROR};
            font-size: 12px; padding: 8px; min-height: 20px;
        """)
        self._banner.hide()
        self._content_layout.addWidget(self._banner)
        self._content_layout.addSpacing(8)

    def _build_form_card(self) -> None:
        """Card chứa form tạo/sửa hồ sơ."""
        self._card = QFrame()
        self._card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_WHITE}; border-radius: 12px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(0)

        # Title (thay đổi theo mode)
        self._card_title = QLabel("Thông tin doanh nghiệp")
        self._card_title.setStyleSheet(f"color:{COLOR_NAVY_DARK};font-size:16px;font-weight:700;")
        cl.addWidget(self._card_title)
        cl.addSpacing(20)

        # ── Form fields ─────────────────────────────────────────────────────
        self._company_name = self._add_field(cl, "Tên doanh nghiệp *", placeholder="Công ty TNHH ABC")
        self._industry      = self._add_field(cl, "Lĩnh vực", placeholder="Công nghệ thông tin")
        self._website       = self._add_field(cl, "Website", placeholder="https://example.com")
        self._tax_code      = self._add_field(cl, "Mã số thuế", placeholder="0123456789")
        self._address       = self._add_field(cl, "Địa chỉ", placeholder="123 Nguyễn Văn Cừ, Q.1, TP.HCM")

        # Description (QTextEdit)
        desc_label = QLabel("Mô tả")
        desc_label.setStyleSheet(f"color:{COLOR_TEXT_DARK};font-size:13px;font-weight:600;")
        cl.addWidget(desc_label)
        cl.addSpacing(6)
        self._description = QTextEdit()
        self._description.setMaximumHeight(80)
        self._description.setPlaceholderText("Mô tả ngắn về doanh nghiệp...")
        self._description.setStyleSheet(self._text_edit_css())
        cl.addWidget(self._description)
        cl.addSpacing(20)

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._btn_save = QPushButton("Lưu thông tin")
        self._btn_save.setFixedHeight(44)
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.setStyleSheet(primary_button_style(font_size=14, padding="10px 28px"))
        self._btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self._btn_save)

        self._btn_cancel = QPushButton("Hủy")
        self._btn_cancel.setFixedHeight(44)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.setStyleSheet(secondary_button_style(font_size=13, padding="10px 28px"))
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_cancel.hide()
        btn_row.addWidget(self._btn_cancel)

        self._btn_edit = QPushButton("Chỉnh sửa")
        self._btn_edit.setFixedHeight(44)
        self._btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_edit.setStyleSheet(secondary_button_style(font_size=13, padding="10px 28px"))
        self._btn_edit.clicked.connect(self._on_edit)
        self._btn_edit.hide()
        btn_row.addWidget(self._btn_edit)

        btn_row.addStretch()
        cl.addLayout(btn_row)

        self._content_layout.addWidget(self._card)

    def _add_field(self, parent_layout, label_text: str, placeholder: str = "") -> QLineEdit:
        """Thêm field label + input vào layout, trả về QLineEdit."""
        label = QLabel(label_text)
        label.setStyleSheet(f"color:{COLOR_TEXT_DARK};font-size:13px;font-weight:600;")
        parent_layout.addWidget(label)
        parent_layout.addSpacing(6)
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(42)
        inp.setStyleSheet(self._input_css())
        parent_layout.addWidget(inp)
        parent_layout.addSpacing(14)
        return inp

    def _input_css(self, error: bool = False) -> str:
        border = COLOR_ERROR if error else COLOR_LIGHT_GRAY
        return f"""
            QLineEdit {{
                background:{COLOR_WHITE}; color:{COLOR_TEXT_DARK};
                border:1.5px solid {border}; border-radius:8px;
                padding:8px 12px; font-size:13px;
            }}
            QLineEdit:focus {{ border-color:{COLOR_ACCENT if not error else COLOR_ERROR}; }}
            QLineEdit:disabled {{ background:{COLOR_OFF_WHITE}; color:{COLOR_TEXT_MUTED}; }}
        """

    def _text_edit_css(self) -> str:
        return f"""
            QTextEdit {{
                background:{COLOR_WHITE}; color:{COLOR_TEXT_DARK};
                border:1.5px solid {COLOR_LIGHT_GRAY}; border-radius:8px;
                padding:8px 12px; font-size:13px;
            }}
            QTextEdit:focus {{ border-color:{COLOR_ACCENT}; }}
            QTextEdit:disabled {{ background:{COLOR_OFF_WHITE}; color:{COLOR_TEXT_MUTED}; }}
        """

    # ── Load profile ──────────────────────────────────────────────────────────

    def _load_profile(self) -> None:
        """Tải hồ sơ từ service, hiển thị form tạo hoặc view."""
        result = self._svc.get_profile()

        if result.status == ProfileResult.NOT_FOUND:
            self._show_create_mode()
        elif result.success:
            self._profile = result.profile
            self._show_view_mode()
        else:
            self._show_banner(result.message, is_error=True)
            if result.status == ProfileResult.WRONG_ROLE:
                self._set_fields_enabled(False)
                self._btn_save.hide()
                self._btn_edit.hide()

    def _show_create_mode(self) -> None:
        """Hiển thị form tạo mới."""
        self._is_editing = False
        self._card_title.setText("Tạo hồ sơ doanh nghiệp")
        self._btn_save.setText("Tạo hồ sơ")
        self._btn_save.show()
        self._btn_cancel.hide()
        self._btn_edit.hide()
        self._set_fields_enabled(True)
        self._verified_badge.setText("🔒 Chưa xác minh")
        self._verified_badge.setStyleSheet(f"""
            background:{COLOR_LIGHT_GRAY}; color:{COLOR_TEXT_MUTED};
            border-radius:12px; padding:6px 16px;
            font-size:12px; font-weight:600;
        """)

    def _show_view_mode(self) -> None:
        """Hiển thị thông tin hồ sơ (read-only) + nút chỉnh sửa."""
        self._is_editing = False
        self._fill_fields_from_profile()
        self._card_title.setText("Thông tin doanh nghiệp")
        self._btn_save.hide()
        self._btn_cancel.hide()
        self._btn_edit.show()
        self._set_fields_enabled(False)

        if self._profile and self._profile.is_verified:
            self._verified_badge.setText("✅ Đã xác minh")
            self._verified_badge.setStyleSheet(f"""
                background:rgba(39,174,96,0.15); color:{COLOR_SUCCESS};
                border-radius:12px; padding:6px 16px;
                font-size:12px; font-weight:600;
            """)
        else:
            self._verified_badge.setText("🔒 Chưa xác minh")
            self._verified_badge.setStyleSheet(f"""
                background:{COLOR_LIGHT_GRAY}; color:{COLOR_TEXT_MUTED};
                border-radius:12px; padding:6px 16px;
                font-size:12px; font-weight:600;
            """)

    def _show_edit_mode(self) -> None:
        """Hiển thị form chỉnh sửa."""
        self._is_editing = True
        self._card_title.setText("Chỉnh sửa hồ sơ")
        self._btn_save.setText("Lưu thay đổi")
        self._btn_save.show()
        self._btn_cancel.show()
        self._btn_edit.hide()
        self._set_fields_enabled(True)

    def _fill_fields_from_profile(self) -> None:
        """Điền form từ profile hiện có."""
        if not self._profile:
            return
        self._company_name.setText(self._profile.company_name or "")
        self._industry.setText(self._profile.industry or "")
        self._website.setText(self._profile.website or "")
        self._tax_code.setText(self._profile.tax_code or "")
        self._address.setText(self._profile.address or "")
        self._description.setPlainText(self._profile.description or "")

    def _set_fields_enabled(self, enabled: bool) -> None:
        """Bật/tắt tất cả input fields."""
        for w in [self._company_name, self._industry, self._website,
                  self._tax_code, self._address, self._description]:
            w.setEnabled(enabled)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        """Xử lý nút Lưu (tạo mới hoặc cập nhật)."""
        company_name = self._company_name.text()
        industry     = self._industry.text()
        website      = self._website.text()
        description  = self._description.toPlainText()
        tax_code     = self._tax_code.text()
        address      = self._address.text()

        # Reset error styles
        self._company_name.setStyleSheet(self._input_css(error=False))

        if not company_name.strip():
            self._company_name.setStyleSheet(self._input_css(error=True))
            self._show_banner("Tên doanh nghiệp không được để trống.", is_error=True)
            return

        if self._profile is None:
            # Create mode
            result = self._svc.create_profile(
                company_name, industry, website, description, tax_code, address
            )
        else:
            # Update mode
            result = self._svc.update_profile(
                company_name, industry, website, description, tax_code, address
            )

        if result.success:
            self._profile = result.profile
            self._show_view_mode()
            self._show_banner("Lưu thông tin thành công!", is_error=False)
        else:
            self._show_banner(result.message, is_error=True)

    def _on_edit(self) -> None:
        """Chuyển sang chế độ chỉnh sửa."""
        self._show_edit_mode()
        self._show_banner("")

    def _on_cancel(self) -> None:
        """Hủy chỉnh sửa → quay về view mode."""
        if self._profile:
            self._fill_fields_from_profile()
            self._show_view_mode()
        else:
            self._show_create_mode()
        self._show_banner("")

    def _handle_back(self) -> None:
        if callable(self._on_back_cb):
            self._on_back_cb()

    # ── Banner ─────────────────────────────────────────────────────────────────

    def _show_banner(self, text: str, is_error: bool = False) -> None:
        if not text:
            self._banner.hide()
            return
        color = COLOR_ERROR if is_error else COLOR_SUCCESS
        bg = "rgba(231,76,60,0.08)" if is_error else "rgba(39,174,96,0.08)"
        self._banner.setStyleSheet(f"""
            background:{bg}; color:{color};
            border-radius:8px; padding:8px 16px;
            font-size:12px; min-height:20px;
        """)
        self._banner.setText(text)
        self._banner.show()

    # ── Animation ──────────────────────────────────────────────────────────────

    def _animate_in(self) -> None:
        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self._eff.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._eff, b"opacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    # ── Refresh ────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Tải lại hồ sơ — gọi khi màn hình được hiển thị lại."""
        self._load_profile()
