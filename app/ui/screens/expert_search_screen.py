"""
ExpertSearchScreen — Company tìm kiếm chuyên gia và gửi đề nghị hợp tác.

Chỉ hiển thị cho role='company'.
"""

from __future__ import annotations

from PySide6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QScrollArea,
    QComboBox, QGraphicsOpacityEffect, QSizePolicy,
)

from app.utils.constants import (
    APP_NAME, COLOR_NAVY_DARK, COLOR_NAVY_MID, COLOR_ACCENT,
    COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_ERROR,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
)
from app.utils.styles import primary_button_style, secondary_button_style
from app.services.expert_search_service import (
    ExpertSearchService, ExpertSearchResult,
    SearchResult,
)
from app.services.contract_service import ContractService, ContractResult


class ExpertSearchScreen(QWidget):
    """
    Màn hình tìm kiếm chuyên gia cho Company.
    Callbacks: on_back, on_view_contracts
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._on_back_cb = None
        self._on_view_contracts_cb = None
        self._svc = ExpertSearchService()
        self._contract_svc = ContractService()
        self._setup_ui()
        QTimer.singleShot(80, self._animate_in)

    @property
    def on_back(self): return self._on_back_cb
    @on_back.setter
    def on_back(self, cb): self._on_back_cb = cb

    @property
    def on_view_contracts(self): return self._on_view_contracts_cb
    @on_view_contracts.setter
    def on_view_contracts(self, cb): self._on_view_contracts_cb = cb

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0); main.setSpacing(0)
        main.addWidget(self._make_sidebar())
        content = self._make_content()
        main.addWidget(content, stretch=1)

    def _make_sidebar(self) -> QWidget:
        sb = QWidget(); sb.setFixedWidth(240)
        sb.setStyleSheet(f"""QWidget {{background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {COLOR_NAVY_DARK}, stop:1 {COLOR_NAVY_MID});}}""")
        lay = QVBoxLayout(sb); lay.setContentsMargins(20, 28, 20, 20); lay.setSpacing(0)
        # Logo
        lr = QHBoxLayout()
        lb = QWidget(); lb.setFixedSize(36, 36)
        lb.setStyleSheet(f"background:{COLOR_ACCENT};border-radius:10px;")
        ll = QVBoxLayout(lb); ll.setContentsMargins(0,0,0,0)
        li = QLabel("✓"); li.setAlignment(Qt.AlignmentFlag.AlignCenter)
        li.setStyleSheet(f"color:{COLOR_WHITE};font-size:18px;font-weight:700;background:transparent;")
        ll.addWidget(li)
        lr.addWidget(lb); lr.addSpacing(8)
        al = QLabel(APP_NAME); al.setStyleSheet(f"color:{COLOR_WHITE};font-size:16px;font-weight:700;background:transparent;")
        lr.addWidget(al); lr.addStretch(); lay.addLayout(lr); lay.addSpacing(28)
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.15);"); lay.addWidget(div); lay.addSpacing(20)
        for icon, text, active in [
            ("🔎", "Tìm kiếm chuyên gia", True),
            ("📋", "Hợp đồng của tôi", False),
        ]:
            btn = QPushButton(f"  {icon}  {text}"); btn.setFixedHeight(38)
            bg = "rgba(46,134,222,0.2)" if active else "transparent"
            clr = COLOR_WHITE if active else "rgba(255,255,255,0.75)"
            btn.setStyleSheet(f"""QPushButton{{background:{bg};color:{clr};border:none;border-radius:8px;
                font-size:12px;text-align:left;padding-left:8px;}}
                QPushButton:hover{{background:rgba(255,255,255,0.1);color:{COLOR_WHITE};}}""")
            if text == "Hợp đồng của tôi":
                btn.clicked.connect(self._handle_view_contracts)
            lay.addWidget(btn); lay.addSpacing(4)
        lay.addStretch()
        back_btn = QPushButton("  ←  Quay lại Dashboard"); back_btn.setFixedHeight(40)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""QPushButton{{background:rgba(46,134,222,0.15);color:{COLOR_ACCENT};
            border:1px solid rgba(46,134,222,0.4);border-radius:8px;font-size:12px;
            font-weight:600;text-align:left;padding-left:12px;}}
            QPushButton:hover{{background:rgba(46,134,222,0.3);}}""")
        back_btn.clicked.connect(self._handle_back); lay.addWidget(back_btn)
        return sb

    def _make_content(self) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{COLOR_OFF_WHITE};}}")
        w = QWidget(); w.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        cl = QVBoxLayout(w); cl.setContentsMargins(32, 28, 32, 28); cl.setSpacing(16)
        # Header
        hdr = QFrame(); hdr.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 20, 24, 20)
        left = QVBoxLayout()
        left.addWidget(self._lbl("Tìm kiếm chuyên gia", size=22, bold=True, color=COLOR_NAVY_DARK))
        left.addWidget(self._lbl("Tìm và mời chuyên gia phù hợp hợp tác", size=13, color=COLOR_TEXT_MUTED))
        left.setSpacing(4); hl.addLayout(left); hl.addStretch(); cl.addWidget(hdr)
        # Banner
        self._banner = QLabel(""); self._banner.setWordWrap(True)
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setStyleSheet(f"background:transparent;color:{COLOR_ERROR};font-size:12px;min-height:20px;")
        self._banner.hide(); cl.addWidget(self._banner)
        # Filter card
        fc = QFrame(); fc.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        fl = QHBoxLayout(fc); fl.setContentsMargins(20, 16, 20, 16); fl.setSpacing(12)
        self._spec_input = QLineEdit(); self._spec_input.setPlaceholderText("Lĩnh vực (vd: Python, AI...)")
        self._spec_input.setFixedHeight(40); self._spec_input.setStyleSheet(self._input_css())
        self._spec_input.returnPressed.connect(self._on_search); fl.addWidget(self._spec_input)
        self._avail_combo = QComboBox(); self._avail_combo.setFixedHeight(40)
        self._avail_combo.addItem("Tất cả trạng thái", "")
        self._avail_combo.addItem("Sẵn sàng", "available")
        self._avail_combo.addItem("Đang bận", "busy")
        self._avail_combo.setStyleSheet(self._input_css()); fl.addWidget(self._avail_combo)
        search_btn = QPushButton("🔍 Tìm kiếm"); search_btn.setFixedHeight(40)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setStyleSheet(primary_button_style(font_size=13, padding="8px 20px"))
        search_btn.clicked.connect(self._on_search); fl.addWidget(search_btn); cl.addWidget(fc)
        # Results area
        self._results_label = self._lbl("Nhấn 'Tìm kiếm' để xem danh sách chuyên gia", color=COLOR_TEXT_MUTED)
        cl.addWidget(self._results_label)
        self._results_container = QWidget(); self._results_container.setStyleSheet("background:transparent;")
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, 0, 0); self._results_layout.setSpacing(12)
        cl.addWidget(self._results_container)
        cl.addStretch(); scroll.setWidget(w); return scroll

    def _input_css(self) -> str:
        return f"""QLineEdit,QComboBox{{background:{COLOR_WHITE};color:{COLOR_TEXT_DARK};
            border:1.5px solid {COLOR_LIGHT_GRAY};border-radius:8px;padding:6px 12px;font-size:13px;}}
            QLineEdit:focus,QComboBox:focus{{border-color:{COLOR_ACCENT};}}"""

    def _lbl(self, text, size=13, bold=False, color=None) -> QLabel:
        lbl = QLabel(text)
        c = color or COLOR_TEXT_DARK
        fw = "font-weight:700;" if bold else ""
        lbl.setStyleSheet(f"color:{c};font-size:{size}px;{fw}")
        lbl.setWordWrap(True); return lbl

    def _on_search(self) -> None:
        self._show_banner("")
        spec = self._spec_input.text().strip()
        avail = self._avail_combo.currentData() or None
        # Clear results
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        r = self._svc.search(specialization=spec, availability=avail)
        if not r.success:
            self._show_banner(r.message, is_error=True); return
        if not r.experts:
            self._results_label.setText("Không tìm thấy chuyên gia phù hợp.")
            self._results_label.show(); return
        self._results_label.setText(f"Tìm thấy {len(r.experts)} chuyên gia")
        self._results_label.show()
        for expert in r.experts:
            card = self._make_expert_card(expert)
            self._results_layout.addWidget(card)

    def _make_expert_card(self, expert: ExpertSearchResult) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}""")
        cl = QHBoxLayout(card); cl.setContentsMargins(20, 16, 20, 16); cl.setSpacing(16)
        # Avatar placeholder
        av = QWidget(); av.setFixedSize(48, 48)
        av.setStyleSheet(f"background:{COLOR_ACCENT};border-radius:24px;")
        avl = QVBoxLayout(av); avl.setContentsMargins(0,0,0,0)
        ai = QLabel("🏆"); ai.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ai.setStyleSheet("font-size:20px;background:transparent;"); avl.addWidget(ai)
        cl.addWidget(av)
        # Info
        info = QVBoxLayout(); info.setSpacing(2)
        title_row = QHBoxLayout(); title_row.setSpacing(8)
        title_row.addWidget(self._lbl(expert.title, size=14, bold=True))
        if expert.is_verified:
            vb = QLabel("✅ Đã xác minh")
            vb.setStyleSheet(f"color:{COLOR_SUCCESS};font-size:11px;")
            title_row.addWidget(vb)
        title_row.addStretch(); info.addLayout(title_row)
        if expert.specialization:
            info.addWidget(self._lbl(expert.specialization, size=12, color=COLOR_TEXT_MUTED))
        rate_avail = f"{expert.hourly_rate_display}  •  {expert.availability}"
        info.addWidget(self._lbl(rate_avail, size=12, color=COLOR_TEXT_MUTED))
        cl.addLayout(info)
        cl.addStretch()
        # Invite button
        inv_btn = QPushButton("Mời hợp tác")
        inv_btn.setFixedHeight(38); inv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        inv_btn.setStyleSheet(primary_button_style(font_size=12, padding="8px 16px"))
        inv_btn.clicked.connect(lambda _, ep=expert.profile_id: self._on_invite(ep, inv_btn))
        cl.addWidget(inv_btn); return card

    def _on_invite(self, expert_profile_id: int, btn: QPushButton) -> None:
        btn.setEnabled(False); btn.setText("Đang gửi...")
        r = self._contract_svc.invite_expert(expert_profile_id)
        if r.success:
            btn.setText("✓ Đã mời"); self._show_banner("Đã gửi đề nghị hợp tác thành công!", is_error=False)
        else:
            btn.setEnabled(True); btn.setText("Mời hợp tác")
            self._show_banner(r.message, is_error=True)

    def _show_banner(self, text, is_error=False) -> None:
        if not text: self._banner.hide(); return
        clr = COLOR_ERROR if is_error else COLOR_SUCCESS
        bg = "rgba(231,76,60,0.08)" if is_error else "rgba(39,174,96,0.08)"
        self._banner.setStyleSheet(f"background:{bg};color:{clr};border-radius:8px;padding:8px 16px;font-size:12px;")
        self._banner.setText(text); self._banner.show()

    def _handle_back(self):
        if callable(self._on_back_cb): self._on_back_cb()

    def _handle_view_contracts(self):
        if callable(self._on_view_contracts_cb): self._on_view_contracts_cb()

    def _animate_in(self):
        self._eff = QGraphicsOpacityEffect(self); self.setGraphicsEffect(self._eff)
        self._eff.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._eff, b"opacity")
        self._anim.setDuration(400); self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0); self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def refresh(self): pass
