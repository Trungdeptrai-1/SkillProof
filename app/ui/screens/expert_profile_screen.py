"""
ExpertProfileScreen — Màn hình quản lý hồ sơ chuyên gia.

Chức năng:
- Xem hồ sơ (title, bio, specialization, hourly_rate, availability, is_verified).
- Tạo / chỉnh sửa hồ sơ (3 chế độ: create / view / edit).
- availability qua ComboBox.
- hourly_rate hiển thị đơn vị VNĐ.
- is_verified chỉ đọc (badge hiển thị).
- Chỉ hiển thị khi role == 'expert'.
"""

from __future__ import annotations

import math
from PySide6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFrame,
    QComboBox, QDoubleSpinBox, QGraphicsOpacityEffect,
    QScrollArea,
)

from app.utils.constants import (
    APP_NAME, COLOR_NAVY_DARK, COLOR_NAVY_MID, COLOR_NAVY_LIGHT,
    COLOR_ACCENT, COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_ERROR,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
)
from app.utils.styles import primary_button_style, secondary_button_style
from app.services.expert_profile_service import (
    ExpertProfileService, ExpertProfileResult, ExpertProfileModel,
    AVAILABILITY_LABELS, AVAILABILITY_VALUES,
)
from app.services.auth_service import SessionManager


class ExpertProfileScreen(QWidget):
    """
    Màn hình quản lý hồ sơ chuyên gia.

    Callbacks:
        screen.on_back = lambda: ...
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._on_back_cb = None
        self._svc = ExpertProfileService()
        self._profile: ExpertProfileModel | None = None
        self._is_editing = False
        self._setup_ui()
        self._load_profile()
        QTimer.singleShot(80, self._animate_in)

    @property
    def on_back(self):
        return self._on_back_cb

    @on_back.setter
    def on_back(self, cb):
        self._on_back_cb = cb

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self._sidebar = self._make_sidebar()
        main.addWidget(self._sidebar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{COLOR_OFF_WHITE};}}")

        content = QWidget()
        content.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        self._cl = QVBoxLayout(content)
        self._cl.setContentsMargins(32, 28, 32, 28)
        self._cl.setSpacing(0)

        self._build_header()
        self._build_banner()
        self._build_account_card()
        self._build_form_card()

        self._cl.addStretch()
        scroll.setWidget(content)
        main.addWidget(scroll, stretch=1)

    def _make_sidebar(self) -> QWidget:
        sb = QWidget()
        sb.setFixedWidth(240)
        sb.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {COLOR_NAVY_DARK}, stop:1 {COLOR_NAVY_MID});
            }}
        """)
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(20, 28, 20, 20)
        lay.setSpacing(0)

        # Logo
        logo_row = QHBoxLayout()
        lb = QWidget(); lb.setFixedSize(36, 36)
        lb.setStyleSheet(f"background:{COLOR_ACCENT};border-radius:10px;")
        ll = QVBoxLayout(lb); ll.setContentsMargins(0,0,0,0)
        li = QLabel("✓"); li.setAlignment(Qt.AlignmentFlag.AlignCenter)
        li.setStyleSheet(f"color:{COLOR_WHITE};font-size:18px;font-weight:700;background:transparent;")
        ll.addWidget(li)
        logo_row.addWidget(lb); logo_row.addSpacing(8)
        al = QLabel(APP_NAME)
        al.setStyleSheet(f"color:{COLOR_WHITE};font-size:16px;font-weight:700;background:transparent;")
        logo_row.addWidget(al); logo_row.addStretch()
        lay.addLayout(logo_row)
        lay.addSpacing(28)

        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.15);")
        lay.addWidget(div); lay.addSpacing(20)

        for icon, text, active in [
            ("🏆", "Hồ sơ chuyên gia", True),
            ("📋", "Ngân hàng câu hỏi", False),
            ("🎯", "Đánh giá & Chấm điểm", False),
            ("🤝", "Phỏng vấn", False),
            ("📊", "Thống kê", False),
        ]:
            btn = QPushButton(f"  {icon}  {text}")
            btn.setFixedHeight(38)
            bg = "rgba(46,134,222,0.2)" if active else "transparent"
            clr = COLOR_WHITE if active else "rgba(255,255,255,0.75)"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{bg}; color:{clr};
                    border:none; border-radius:8px;
                    font-size:12px; text-align:left; padding-left:8px;
                }}
                QPushButton:hover {{ background:rgba(255,255,255,0.1); color:{COLOR_WHITE}; }}
            """)
            lay.addWidget(btn); lay.addSpacing(4)

        lay.addStretch()

        back_btn = QPushButton("  ←  Quay lại Dashboard")
        back_btn.setFixedHeight(40)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background:rgba(46,134,222,0.15); color:{COLOR_ACCENT};
                border:1px solid rgba(46,134,222,0.4); border-radius:8px;
                font-size:12px; font-weight:600; text-align:left; padding-left:12px;
            }}
            QPushButton:hover {{ background:rgba(46,134,222,0.3); }}
        """)
        back_btn.clicked.connect(self._handle_back)
        lay.addWidget(back_btn)
        return sb

    def _build_header(self) -> None:
        hdr = QFrame()
        hdr.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 20, 24, 20)
        left = QVBoxLayout()
        t = QLabel("Hồ sơ chuyên gia")
        t.setStyleSheet(f"color:{COLOR_NAVY_DARK};font-size:22px;font-weight:700;")
        left.addWidget(t)
        s = QLabel("Quản lý thông tin chuyên môn của bạn")
        s.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:13px;margin-top:4px;")
        left.addWidget(s); left.setSpacing(0)
        hl.addLayout(left); hl.addStretch()

        self._verified_badge = QLabel("🔒 Chưa xác minh")
        self._verified_badge.setStyleSheet(f"""
            background:{COLOR_LIGHT_GRAY}; color:{COLOR_TEXT_MUTED};
            border-radius:12px; padding:6px 16px; font-size:12px; font-weight:600;
        """)
        hl.addWidget(self._verified_badge)
        self._cl.addWidget(hdr); self._cl.addSpacing(16)

    def _build_banner(self) -> None:
        self._banner = QLabel("")
        self._banner.setWordWrap(True)
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setStyleSheet(f"background:transparent;color:{COLOR_ERROR};font-size:12px;padding:8px;min-height:20px;")
        self._banner.hide()
        self._cl.addWidget(self._banner); self._cl.addSpacing(8)

    def _build_account_card(self) -> None:
        """Thông tin tài khoản (read-only: họ tên, email)."""
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        cl = QVBoxLayout(card); cl.setContentsMargins(24, 20, 24, 20); cl.setSpacing(0)
        t = QLabel("Thông tin tài khoản")
        t.setStyleSheet(f"color:{COLOR_NAVY_DARK};font-size:15px;font-weight:700;")
        cl.addWidget(t); cl.addSpacing(14)

        for lbl_text, attr in [("Họ và tên", "_acc_name_lbl"), ("Email", "_acc_email_lbl")]:
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:11px;font-weight:600;")
            cl.addWidget(lbl)
            val = QLabel("—")
            val.setStyleSheet(f"color:{COLOR_TEXT_DARK};font-size:13px;padding:6px 12px;background:{COLOR_OFF_WHITE};border-radius:6px;")
            setattr(self, attr, val)
            cl.addWidget(val); cl.addSpacing(10)

        self._cl.addWidget(card); self._cl.addSpacing(16)

    def _build_form_card(self) -> None:
        self._card = QFrame()
        self._card.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        cl = QVBoxLayout(self._card); cl.setContentsMargins(24, 20, 24, 20); cl.setSpacing(0)

        self._card_title = QLabel("Thông tin chuyên môn")
        self._card_title.setStyleSheet(f"color:{COLOR_NAVY_DARK};font-size:15px;font-weight:700;")
        cl.addWidget(self._card_title); cl.addSpacing(16)

        # Title *
        cl.addWidget(self._flabel("Tiêu đề chuyên môn *"))
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Ví dụ: Senior Python Developer")
        self._title_input.setFixedHeight(42)
        self._title_input.setStyleSheet(self._input_css())
        cl.addWidget(self._title_input); cl.addSpacing(12)

        # Specialization
        cl.addWidget(self._flabel("Lĩnh vực chuyên môn"))
        self._spec_input = QLineEdit()
        self._spec_input.setPlaceholderText("Ví dụ: Backend, Machine Learning, DevOps")
        self._spec_input.setFixedHeight(42)
        self._spec_input.setStyleSheet(self._input_css())
        cl.addWidget(self._spec_input); cl.addSpacing(12)

        # Bio
        cl.addWidget(self._flabel("Giới thiệu bản thân"))
        self._bio_input = QTextEdit()
        self._bio_input.setMaximumHeight(80)
        self._bio_input.setPlaceholderText("Mô tả kinh nghiệm, thành tích nổi bật...")
        self._bio_input.setStyleSheet(self._textedit_css())
        cl.addWidget(self._bio_input); cl.addSpacing(12)

        # Hourly rate
        cl.addWidget(self._flabel("Mức phí theo giờ (VNĐ)"))
        rate_row = QHBoxLayout()
        self._rate_input = QDoubleSpinBox()
        self._rate_input.setRange(0, 100_000_000)
        self._rate_input.setDecimals(0)
        self._rate_input.setSuffix(" VNĐ")
        self._rate_input.setFixedHeight(42)
        self._rate_input.setStyleSheet(self._spin_css())
        self._rate_input.setSpecialValueText("Chưa cập nhật")
        rate_row.addWidget(self._rate_input)
        self._rate_null_check = QPushButton("Xóa giá trị")
        self._rate_null_check.setFixedHeight(42)
        self._rate_null_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rate_null_check.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{COLOR_TEXT_MUTED};
                border:1.5px solid {COLOR_LIGHT_GRAY}; border-radius:8px;
                font-size:12px; padding:0 12px;
            }}
            QPushButton:hover {{ color:{COLOR_ERROR}; border-color:{COLOR_ERROR}; }}
        """)
        self._rate_null_check.clicked.connect(lambda: self._rate_input.setValue(0))
        rate_row.addWidget(self._rate_null_check)
        cl.addLayout(rate_row); cl.addSpacing(12)

        # Availability
        cl.addWidget(self._flabel("Trạng thái sẵn sàng"))
        self._avail_combo = QComboBox()
        for val in AVAILABILITY_VALUES:
            self._avail_combo.addItem(AVAILABILITY_LABELS[val], val)
        self._avail_combo.setFixedHeight(42)
        self._avail_combo.setStyleSheet(self._combo_css())
        cl.addWidget(self._avail_combo); cl.addSpacing(20)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(12)

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

        self._cl.addWidget(self._card)

    # ── Style helpers ─────────────────────────────────────────────────────────

    def _flabel(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color:{COLOR_TEXT_DARK};font-size:13px;font-weight:600;")
        return l

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

    def _textedit_css(self) -> str:
        return f"""
            QTextEdit {{
                background:{COLOR_WHITE}; color:{COLOR_TEXT_DARK};
                border:1.5px solid {COLOR_LIGHT_GRAY}; border-radius:8px;
                padding:8px 12px; font-size:13px;
            }}
            QTextEdit:focus {{ border-color:{COLOR_ACCENT}; }}
            QTextEdit:disabled {{ background:{COLOR_OFF_WHITE}; color:{COLOR_TEXT_MUTED}; }}
        """

    def _spin_css(self) -> str:
        return f"""
            QDoubleSpinBox {{
                background:{COLOR_WHITE}; color:{COLOR_TEXT_DARK};
                border:1.5px solid {COLOR_LIGHT_GRAY}; border-radius:8px;
                padding:8px 12px; font-size:13px;
            }}
            QDoubleSpinBox:focus {{ border-color:{COLOR_ACCENT}; }}
            QDoubleSpinBox:disabled {{ background:{COLOR_OFF_WHITE}; color:{COLOR_TEXT_MUTED}; }}
        """

    def _combo_css(self) -> str:
        return f"""
            QComboBox {{
                background:{COLOR_WHITE}; color:{COLOR_TEXT_DARK};
                border:1.5px solid {COLOR_LIGHT_GRAY}; border-radius:8px;
                padding:8px 12px; font-size:13px;
            }}
            QComboBox:focus {{ border-color:{COLOR_ACCENT}; }}
            QComboBox:disabled {{ background:{COLOR_OFF_WHITE}; color:{COLOR_TEXT_MUTED}; }}
        """

    # ── Load & mode switching ─────────────────────────────────────────────────

    def _load_profile(self) -> None:
        # Điền thông tin tài khoản từ session
        session = SessionManager.instance()
        if session.is_logged_in and session.current_user:
            self._acc_name_lbl.setText(session.current_user.display_name)
            self._acc_email_lbl.setText(session.current_user.email)

        result = self._svc.get_profile()
        if result.status == ExpertProfileResult.NOT_FOUND:
            self._show_create_mode()
        elif result.success:
            self._profile = result.profile
            self._show_view_mode()
        else:
            self._show_banner(result.message, is_error=True)
            if result.status == ExpertProfileResult.WRONG_ROLE:
                self._set_form_enabled(False)
                self._btn_save.hide(); self._btn_edit.hide()

    def _show_create_mode(self) -> None:
        self._is_editing = False
        self._card_title.setText("Tạo hồ sơ chuyên gia")
        self._btn_save.setText("Tạo hồ sơ"); self._btn_save.show()
        self._btn_cancel.hide(); self._btn_edit.hide()
        self._set_form_enabled(True)

    def _show_view_mode(self) -> None:
        self._is_editing = False
        self._fill_fields()
        self._card_title.setText("Thông tin chuyên môn")
        self._btn_save.hide(); self._btn_cancel.hide(); self._btn_edit.show()
        self._set_form_enabled(False)
        self._update_verified_badge()

    def _show_edit_mode(self) -> None:
        self._is_editing = True
        self._card_title.setText("Chỉnh sửa hồ sơ")
        self._btn_save.setText("Lưu thay đổi"); self._btn_save.show()
        self._btn_cancel.show(); self._btn_edit.hide()
        self._set_form_enabled(True)

    def _fill_fields(self) -> None:
        if not self._profile:
            return
        self._title_input.setText(self._profile.title or "")
        self._spec_input.setText(self._profile.specialization or "")
        self._bio_input.setPlainText(self._profile.bio or "")
        # hourly_rate — dùng round để tránh lỗi float
        if self._profile.hourly_rate is not None and math.isfinite(self._profile.hourly_rate):
            self._rate_input.setValue(round(self._profile.hourly_rate))
        else:
            self._rate_input.setValue(0)
        # availability
        idx = self._avail_combo.findData(self._profile.availability)
        if idx >= 0:
            self._avail_combo.setCurrentIndex(idx)

    def _set_form_enabled(self, enabled: bool) -> None:
        for w in [self._title_input, self._spec_input, self._bio_input,
                  self._rate_input, self._avail_combo, self._rate_null_check]:
            w.setEnabled(enabled)

    def _update_verified_badge(self) -> None:
        if self._profile and self._profile.is_verified:
            self._verified_badge.setText("✅ Đã xác minh")
            self._verified_badge.setStyleSheet(f"""
                background:rgba(39,174,96,0.15); color:{COLOR_SUCCESS};
                border-radius:12px; padding:6px 16px; font-size:12px; font-weight:600;
            """)
        else:
            self._verified_badge.setText("🔒 Chưa xác minh")
            self._verified_badge.setStyleSheet(f"""
                background:{COLOR_LIGHT_GRAY}; color:{COLOR_TEXT_MUTED};
                border-radius:12px; padding:6px 16px; font-size:12px; font-weight:600;
            """)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        self._title_input.setStyleSheet(self._input_css(error=False))
        self._show_banner("")

        title = self._title_input.text()
        spec  = self._spec_input.text()
        bio   = self._bio_input.toPlainText()
        rate_val = self._rate_input.value()
        # 0 → None (SpecialValueText)
        rate = rate_val if rate_val > 0 else None
        avail_idx = self._avail_combo.currentIndex()
        availability = self._avail_combo.itemData(avail_idx) or "available"

        if self._profile is None:
            result = self._svc.create_profile(title, bio, spec, rate, availability)
        else:
            result = self._svc.update_profile(title, bio, spec, rate, availability)

        if result.success:
            self._profile = result.profile
            self._show_view_mode()
            self._show_banner("Lưu thông tin thành công!", is_error=False)
        else:
            if result.status in (ExpertProfileResult.EMPTY_TITLE, ExpertProfileResult.TITLE_TOO_LONG):
                self._title_input.setStyleSheet(self._input_css(error=True))
            self._show_banner(result.message, is_error=True)

    def _on_edit(self) -> None:
        self._show_edit_mode(); self._show_banner("")

    def _on_cancel(self) -> None:
        if self._profile:
            self._fill_fields(); self._show_view_mode()
        else:
            self._show_create_mode()
        self._show_banner("")

    def _handle_back(self) -> None:
        if callable(self._on_back_cb):
            self._on_back_cb()

    # ── Banner ─────────────────────────────────────────────────────────────────

    def _show_banner(self, text: str, is_error: bool = False) -> None:
        if not text:
            self._banner.hide(); return
        color = COLOR_ERROR if is_error else COLOR_SUCCESS
        bg = "rgba(231,76,60,0.08)" if is_error else "rgba(39,174,96,0.08)"
        self._banner.setStyleSheet(f"background:{bg};color:{color};border-radius:8px;padding:8px 16px;font-size:12px;min-height:20px;")
        self._banner.setText(text); self._banner.show()

    # ── Animation ──────────────────────────────────────────────────────────────

    def _animate_in(self) -> None:
        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self._eff.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._eff, b"opacity")
        self._anim.setDuration(400); self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0); self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def refresh(self) -> None:
        self._load_profile()
