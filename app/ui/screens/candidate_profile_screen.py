"""
CandidateProfileScreen — Màn hình quản lý hồ sơ ứng viên.

Chức năng:
- Xem thông tin cá nhân (họ tên, email — chỉ đọc).
- Tạo/chỉnh sửa hồ sơ (headline, bio, portfolio_url, years_experience).
- Quản lý CV: chọn PDF, lưu, mở.
- Chế độ xem và chỉnh sửa.
- Thanh tiến độ hoàn thiện hồ sơ.
- Chỉ hiển thị khi role == 'candidate'.
"""

from __future__ import annotations

import os
import subprocess
import platform
from datetime import datetime

from PySide6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui     import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFrame,
    QSizePolicy, QGraphicsOpacityEffect, QScrollArea,
    QFileDialog, QSpinBox, QProgressBar,
)

from app.utils.constants import (
    APP_NAME, COLOR_NAVY_DARK, COLOR_NAVY_MID, COLOR_NAVY_LIGHT,
    COLOR_ACCENT, COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_ERROR,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
)
from app.utils.styles import primary_button_style, secondary_button_style
from app.services.candidate_profile_service import (
    CandidateProfileService, CandidateProfileResult, CandidateProfileModel,
)
from app.services.auth_service import SessionManager


class CandidateProfileScreen(QWidget):
    """
    Màn hình quản lý hồ sơ ứng viên.

    Callbacks:
        screen.on_back = lambda: ...
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._on_back_cb = None
        self._svc = CandidateProfileService()
        self._profile: CandidateProfileModel | None = None
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
        self._build_progress_bar()
        self._build_status_banner()
        self._build_personal_info_card()
        self._build_profile_form_card()
        self._build_cv_card()

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
        ll = QVBoxLayout(logo_box); ll.setContentsMargins(0, 0, 0, 0)
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
        for icon, text, active in [
            ("👤", "Hồ sơ ứng viên", True),
            ("🏅", "Kỹ năng của tôi", False),
            ("📜", "Chứng chỉ", False),
            ("🎯", "Đánh giá", False),
            ("🔎", "Khám phá cơ hội", False),
        ]:
            btn = QPushButton(f"  {icon}  {text}")
            btn.setFixedHeight(38)
            bg = "rgba(46,134,222,0.2)" if active else "transparent"
            color = COLOR_WHITE if active else "rgba(255,255,255,0.75)"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg}; color: {color};
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
        title = QLabel("Hồ sơ ứng viên")
        title.setStyleSheet(f"color:{COLOR_NAVY_DARK};font-size:22px;font-weight:700;")
        left.addWidget(title)

        sub = QLabel("Quản lý thông tin cá nhân và hồ sơ chuyên môn")
        sub.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:13px;margin-top:4px;")
        left.addWidget(sub)
        left.setSpacing(0)

        hl.addLayout(left)
        hl.addStretch()

        self._content_layout.addWidget(header)
        self._content_layout.addSpacing(16)

    def _build_progress_bar(self) -> None:
        """Thanh tiến độ hoàn thiện hồ sơ."""
        prog_frame = QFrame()
        prog_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_WHITE}; border-radius: 10px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        pl = QVBoxLayout(prog_frame)
        pl.setContentsMargins(20, 14, 20, 14)
        pl.setSpacing(8)

        label_row = QHBoxLayout()
        lbl = QLabel("Mức độ hoàn thiện hồ sơ")
        lbl.setStyleSheet(f"color:{COLOR_TEXT_DARK};font-size:12px;font-weight:600;")
        label_row.addWidget(lbl)
        label_row.addStretch()
        self._progress_label = QLabel("0%")
        self._progress_label.setStyleSheet(f"color:{COLOR_ACCENT};font-size:12px;font-weight:700;")
        label_row.addWidget(self._progress_label)
        pl.addLayout(label_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLOR_LIGHT_GRAY}; border: none; border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {COLOR_ACCENT}; border-radius: 4px;
            }}
        """)
        pl.addWidget(self._progress_bar)

        self._content_layout.addWidget(prog_frame)
        self._content_layout.addSpacing(16)

    def _build_status_banner(self) -> None:
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

    def _build_personal_info_card(self) -> None:
        """Card thông tin cá nhân (read-only: họ tên, email)."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_WHITE}; border-radius: 12px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(0)

        title = QLabel("Thông tin cá nhân")
        title.setStyleSheet(f"color:{COLOR_NAVY_DARK};font-size:15px;font-weight:700;")
        cl.addWidget(title)
        cl.addSpacing(16)

        # Full name (read-only)
        cl.addWidget(self._make_readonly_label("Họ và tên"))
        self._full_name_lbl = QLabel("—")
        self._full_name_lbl.setStyleSheet(f"color:{COLOR_TEXT_DARK};font-size:13px;padding:6px 12px;background:{COLOR_OFF_WHITE};border-radius:6px;")
        cl.addWidget(self._full_name_lbl)
        cl.addSpacing(12)

        # Email (read-only)
        cl.addWidget(self._make_readonly_label("Email"))
        self._email_lbl = QLabel("—")
        self._email_lbl.setStyleSheet(f"color:{COLOR_TEXT_DARK};font-size:13px;padding:6px 12px;background:{COLOR_OFF_WHITE};border-radius:6px;")
        cl.addWidget(self._email_lbl)

        self._content_layout.addWidget(card)
        self._content_layout.addSpacing(16)

    def _make_readonly_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:11px;font-weight:600;")
        return lbl

    def _build_profile_form_card(self) -> None:
        """Card form hồ sơ chuyên môn."""
        self._card = QFrame()
        self._card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_WHITE}; border-radius: 12px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(0)

        self._card_title = QLabel("Thông tin nghề nghiệp")
        self._card_title.setStyleSheet(f"color:{COLOR_NAVY_DARK};font-size:15px;font-weight:700;")
        cl.addWidget(self._card_title)
        cl.addSpacing(16)

        # Headline
        cl.addWidget(self._make_field_label("Tiêu đề nghề nghiệp"))
        self._headline_input = QLineEdit()
        self._headline_input.setPlaceholderText("Ví dụ: Python Developer với 3 năm kinh nghiệm")
        self._headline_input.setFixedHeight(42)
        self._headline_input.setStyleSheet(self._input_css())
        cl.addWidget(self._headline_input)
        cl.addSpacing(12)

        # Bio
        cl.addWidget(self._make_field_label("Giới thiệu bản thân"))
        self._bio_input = QTextEdit()
        self._bio_input.setMaximumHeight(80)
        self._bio_input.setPlaceholderText("Mô tả ngắn về bản thân, kinh nghiệm, mục tiêu...")
        self._bio_input.setStyleSheet(self._text_edit_css())
        cl.addWidget(self._bio_input)
        cl.addSpacing(12)

        # Portfolio URL
        cl.addWidget(self._make_field_label("Link portfolio / GitHub"))
        self._portfolio_input = QLineEdit()
        self._portfolio_input.setPlaceholderText("https://github.com/username")
        self._portfolio_input.setFixedHeight(42)
        self._portfolio_input.setStyleSheet(self._input_css())
        cl.addWidget(self._portfolio_input)
        cl.addSpacing(12)

        # Years experience
        years_row = QHBoxLayout()
        years_label = self._make_field_label("Số năm kinh nghiệm")
        cl.addWidget(years_label)
        cl.addSpacing(6)
        self._years_input = QSpinBox()
        self._years_input.setRange(0, 50)
        self._years_input.setValue(0)
        self._years_input.setFixedHeight(42)
        self._years_input.setStyleSheet(self._input_css())
        cl.addWidget(self._years_input)
        cl.addSpacing(20)

        # Buttons
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
        self._content_layout.addSpacing(16)

    def _build_cv_card(self) -> None:
        """Card quản lý CV."""
        cv_card = QFrame()
        cv_card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_WHITE}; border-radius: 12px;
                border: 1px solid {COLOR_LIGHT_GRAY};
            }}
        """)
        cl = QVBoxLayout(cv_card)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(0)

        title = QLabel("CV / Hồ sơ PDF")
        title.setStyleSheet(f"color:{COLOR_NAVY_DARK};font-size:15px;font-weight:700;")
        cl.addWidget(title)
        cl.addSpacing(8)

        desc = QLabel("Chấp nhận file PDF, dung lượng tối đa 10MB")
        desc.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:11px;")
        cl.addWidget(desc)
        cl.addSpacing(16)

        # CV status
        self._cv_status = QLabel("Chưa có CV được tải lên")
        self._cv_status.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:13px;padding:8px 12px;background:{COLOR_OFF_WHITE};border-radius:6px;")
        cl.addWidget(self._cv_status)
        cl.addSpacing(12)

        # CV buttons
        cv_btn_row = QHBoxLayout()
        cv_btn_row.setSpacing(10)

        self._btn_upload_cv = QPushButton("📁 Chọn file CV")
        self._btn_upload_cv.setFixedHeight(40)
        self._btn_upload_cv.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_upload_cv.setStyleSheet(secondary_button_style(font_size=12, padding="8px 20px"))
        self._btn_upload_cv.clicked.connect(self._on_upload_cv)
        cv_btn_row.addWidget(self._btn_upload_cv)

        self._btn_open_cv = QPushButton("📄 Mở CV")
        self._btn_open_cv.setFixedHeight(40)
        self._btn_open_cv.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_cv.setStyleSheet(secondary_button_style(font_size=12, padding="8px 20px"))
        self._btn_open_cv.clicked.connect(self._on_open_cv)
        self._btn_open_cv.hide()
        cv_btn_row.addWidget(self._btn_open_cv)

        cv_btn_row.addStretch()
        cl.addLayout(cv_btn_row)

        self._content_layout.addWidget(cv_card)

    def _make_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{COLOR_TEXT_DARK};font-size:13px;font-weight:600;")
        return lbl

    def _input_css(self, error: bool = False) -> str:
        border = COLOR_ERROR if error else COLOR_LIGHT_GRAY
        return f"""
            QLineEdit, QSpinBox {{
                background:{COLOR_WHITE}; color:{COLOR_TEXT_DARK};
                border:1.5px solid {border}; border-radius:8px;
                padding:8px 12px; font-size:13px;
            }}
            QLineEdit:focus, QSpinBox:focus {{ border-color:{COLOR_ACCENT if not error else COLOR_ERROR}; }}
            QLineEdit:disabled, QSpinBox:disabled {{ background:{COLOR_OFF_WHITE}; color:{COLOR_TEXT_MUTED}; }}
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

        if result.status == CandidateProfileResult.NOT_FOUND:
            self._show_create_mode()
        elif result.success:
            self._profile = result.profile
            self._show_view_mode()
        else:
            self._show_banner(result.message, is_error=True)
            if result.status == CandidateProfileResult.WRONG_ROLE:
                self._set_form_enabled(False)
                self._btn_save.hide()
                self._btn_edit.hide()

    def _show_create_mode(self) -> None:
        self._is_editing = False
        self._card_title.setText("Tạo hồ sơ ứng viên")
        self._btn_save.setText("Tạo hồ sơ")
        self._btn_save.show()
        self._btn_cancel.hide()
        self._btn_edit.hide()
        self._set_form_enabled(True)
        self._update_progress(0)

    def _show_view_mode(self) -> None:
        self._is_editing = False
        self._fill_fields_from_profile()
        self._card_title.setText("Thông tin nghề nghiệp")
        self._btn_save.hide()
        self._btn_cancel.hide()
        self._btn_edit.show()
        self._set_form_enabled(False)
        self._update_cv_status()
        self._update_progress(self._calc_completion())

    def _show_edit_mode(self) -> None:
        self._is_editing = True
        self._card_title.setText("Chỉnh sửa hồ sơ")
        self._btn_save.setText("Lưu thay đổi")
        self._btn_save.show()
        self._btn_cancel.show()
        self._btn_edit.hide()
        self._set_form_enabled(True)

    def _fill_fields_from_profile(self) -> None:
        if not self._profile:
            return
        self._full_name_lbl.setText(self._profile.full_name or "—")
        self._email_lbl.setText(self._profile.email or "—")
        self._headline_input.setText(self._profile.headline or "")
        self._bio_input.setPlainText(self._profile.bio or "")
        self._portfolio_input.setText(self._portfolio.portfolio_url or "")
        self._years_input.setValue(self._profile.years_experience or 0)

    def _set_form_enabled(self, enabled: bool) -> None:
        for w in [self._headline_input, self._bio_input, self._portfolio_input, self._years_input]:
            w.setEnabled(enabled)

    def _update_progress(self, percent: int) -> None:
        self._progress_bar.setValue(percent)
        self._progress_label.setText(f"{percent}%")

    def _calc_completion(self) -> int:
        """Tính % hoàn thiện hồ sơ dựa trên các trường đã điền."""
        if not self._profile:
            return 0
        fields = [
            self._profile.headline,
            self._profile.bio,
            self._profile.portfolio_url,
            self._profile.years_experience,
            self._profile.resume_path,
        ]
        filled = sum(1 for f in fields if f is not None and str(f).strip() != "")
        # full_name và email luôn có (từ users) → +2 trường luôn filled
        total = 7
        return int((filled + 2) / total * 100)

    def _update_cv_status(self) -> None:
        cv_path = self._svc.get_cv_path()
        if cv_path:
            filename = os.path.basename(cv_path)
            self._cv_status.setText(f"✅ CV đã tải lên: {filename}")
            self._cv_status.setStyleSheet(f"color:{COLOR_SUCCESS};font-size:13px;padding:8px 12px;background:rgba(39,174,96,0.08);border-radius:6px;")
            self._btn_open_cv.show()
        else:
            self._cv_status.setText("Chưa có CV được tải lên")
            self._cv_status.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:13px;padding:8px 12px;background:{COLOR_OFF_WHITE};border-radius:6px;")
            self._btn_open_cv.hide()

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        headline = self._headline_input.text()
        bio = self._bio_input.toPlainText()
        portfolio_url = self._portfolio_input.text()
        years = self._years_input.value()

        self._headline_input.setStyleSheet(self._input_css(error=False))

        if self._profile is None:
            result = self._svc.create_profile(
                headline, bio, portfolio_url, years
            )
        else:
            result = self._svc.update_profile(
                headline, bio, portfolio_url, years
            )

        if result.success:
            self._profile = result.profile
            self._show_view_mode()
            self._show_banner("Lưu thông tin thành công!", is_error=False)
        else:
            self._show_banner(result.message, is_error=True)

    def _on_edit(self) -> None:
        self._show_edit_mode()
        self._show_banner("")

    def _on_cancel(self) -> None:
        if self._profile:
            self._fill_fields_from_profile()
            self._show_view_mode()
        else:
            self._show_create_mode()
        self._show_banner("")

    def _on_upload_cv(self) -> None:
        """Mở dialog chọn file CV (PDF)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file CV",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if not file_path:
            return

        result = self._svc.save_cv(file_path)
        if result.success:
            self._profile = result.profile
            self._show_view_mode()
            self._show_banner("Tải lên CV thành công!", is_error=False)
        else:
            self._show_banner(result.message, is_error=True)

    def _on_open_cv(self) -> None:
        """Mở file CV bằng ứng dụng mặc định của hệ điều hành."""
        cv_path = self._svc.get_cv_path()
        if not cv_path:
            self._show_banner("Chưa có CV để mở.", is_error=True)
            return

        try:
            if platform.system() == "Windows":
                os.startfile(cv_path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", cv_path])
        except Exception as e:
            self._show_banner(f"Không thể mở CV: {e}", is_error=True)

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
