"""
ContractManagementScreen — Quản lý hợp đồng Company↔Expert.

Company: xem danh sách hợp đồng, cancel pending, complete/terminate active.
Expert: xem danh sách hợp đồng, chấp thuận/từ chối pending.
"""

from __future__ import annotations

from PySide6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QComboBox,
    QGraphicsOpacityEffect, QDialog, QLineEdit,
)

from app.utils.constants import (
    APP_NAME, COLOR_NAVY_DARK, COLOR_NAVY_MID, COLOR_ACCENT,
    COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_ERROR,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
)
from app.utils.styles import primary_button_style, secondary_button_style
from app.services.contract_service import ContractService, ContractResult, ContractModel
from app.services.auth_service import SessionManager

STATUS_LABELS = {
    "pending_expert": ("🕐", "#F39C12", "Chờ chuyên gia"),
    "rejected":       ("✗",  "#E74C3C", "Bị từ chối"),
    "active":         ("✓",  "#27AE60", "Đang hoạt động"),
    "completed":      ("✓✓", "#2E86DE", "Hoàn thành"),
    "terminated":     ("⊘",  "#7F8C8D", "Chấm dứt"),
    "cancelled":      ("✗",  "#7F8C8D", "Đã hủy"),
}


class ContractManagementScreen(QWidget):
    """Màn hình quản lý hợp đồng. Callbacks: on_back, on_find_experts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._on_back_cb = None
        self._on_find_experts_cb = None
        self._svc = ContractService()
        self._setup_ui()
        self._load_contracts()
        QTimer.singleShot(80, self._animate_in)

    @property
    def on_back(self): return self._on_back_cb
    @on_back.setter
    def on_back(self, cb): self._on_back_cb = cb

    @property
    def on_find_experts(self): return self._on_find_experts_cb
    @on_find_experts.setter
    def on_find_experts(self, cb): self._on_find_experts_cb = cb

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0); main.setSpacing(0)
        main.addWidget(self._make_sidebar())
        main.addWidget(self._make_content(), stretch=1)

    def _make_sidebar(self) -> QWidget:
        sb = QWidget(); sb.setFixedWidth(240)
        sb.setStyleSheet(f"""QWidget{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {COLOR_NAVY_DARK}, stop:1 {COLOR_NAVY_MID});}}""")
        lay = QVBoxLayout(sb); lay.setContentsMargins(20,28,20,20); lay.setSpacing(0)
        lr = QHBoxLayout()
        lb = QWidget(); lb.setFixedSize(36,36)
        lb.setStyleSheet(f"background:{COLOR_ACCENT};border-radius:10px;")
        ll = QVBoxLayout(lb); ll.setContentsMargins(0,0,0,0)
        li = QLabel("✓"); li.setAlignment(Qt.AlignmentFlag.AlignCenter)
        li.setStyleSheet(f"color:{COLOR_WHITE};font-size:18px;font-weight:700;background:transparent;")
        ll.addWidget(li); lr.addWidget(lb); lr.addSpacing(8)
        al = QLabel(APP_NAME); al.setStyleSheet(f"color:{COLOR_WHITE};font-size:16px;font-weight:700;background:transparent;")
        lr.addWidget(al); lr.addStretch(); lay.addLayout(lr); lay.addSpacing(28)
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color:rgba(255,255,255,0.15);"); lay.addWidget(div); lay.addSpacing(20)
        for icon, text, is_active in [
            ("📋", "Hợp đồng của tôi", True),
            ("🔎", "Tìm chuyên gia", False),
        ]:
            btn = QPushButton(f"  {icon}  {text}"); btn.setFixedHeight(38)
            bg = "rgba(46,134,222,0.2)" if is_active else "transparent"
            clr = COLOR_WHITE if is_active else "rgba(255,255,255,0.75)"
            btn.setStyleSheet(f"""QPushButton{{background:{bg};color:{clr};border:none;border-radius:8px;
                font-size:12px;text-align:left;padding-left:8px;}}
                QPushButton:hover{{background:rgba(255,255,255,0.1);color:{COLOR_WHITE};}}""")
            if text == "Tìm chuyên gia":
                btn.clicked.connect(self._handle_find_experts)
            lay.addWidget(btn); lay.addSpacing(4)
        lay.addStretch()
        back_btn = QPushButton("  ←  Quay lại Dashboard"); back_btn.setFixedHeight(40)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""QPushButton{{background:rgba(46,134,222,0.15);color:{COLOR_ACCENT};
            border:1px solid rgba(46,134,222,0.4);border-radius:8px;font-size:12px;
            font-weight:600;text-align:left;padding-left:12px;}}
            QPushButton:hover{{background:rgba(46,134,222,0.3);}}""")
        back_btn.clicked.connect(self._handle_back); lay.addWidget(back_btn); return sb

    def _make_content(self) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{COLOR_OFF_WHITE};}}")
        w = QWidget(); w.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        self._cl = QVBoxLayout(w); self._cl.setContentsMargins(32,28,32,28); self._cl.setSpacing(16)
        # Header
        hdr = QFrame(); hdr.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24,20,24,20)
        left = QVBoxLayout()
        left.addWidget(self._lbl("Quản lý hợp đồng", size=22, bold=True, color=COLOR_NAVY_DARK))
        left.addWidget(self._lbl("Hợp đồng hợp tác giữa doanh nghiệp và chuyên gia", size=13, color=COLOR_TEXT_MUTED))
        left.setSpacing(4); hl.addLayout(left); hl.addStretch()
        ref_btn = QPushButton("🔄 Tải lại"); ref_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ref_btn.setStyleSheet(secondary_button_style(font_size=12, padding="8px 16px"))
        ref_btn.clicked.connect(self._load_contracts); hl.addWidget(ref_btn)
        self._cl.addWidget(hdr)
        # Banner
        self._banner = QLabel(""); self._banner.setWordWrap(True)
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setStyleSheet(f"background:transparent;color:{COLOR_ERROR};font-size:12px;min-height:20px;")
        self._banner.hide(); self._cl.addWidget(self._banner)
        # Filter
        ff = QFrame(); ff.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:10px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        fl = QHBoxLayout(ff); fl.setContentsMargins(16,12,16,12); fl.setSpacing(12)
        fl.addWidget(self._lbl("Lọc:", size=12))
        self._status_filter = QComboBox(); self._status_filter.setFixedHeight(36)
        self._status_filter.addItem("Tất cả", "")
        for s, (_, _, lbl) in STATUS_LABELS.items():
            self._status_filter.addItem(lbl, s)
        self._status_filter.setStyleSheet(self._input_css())
        self._status_filter.currentIndexChanged.connect(self._load_contracts)
        fl.addWidget(self._status_filter); fl.addStretch(); self._cl.addWidget(ff)
        # Contracts container
        self._contracts_label = self._lbl("Đang tải...", color=COLOR_TEXT_MUTED)
        self._cl.addWidget(self._contracts_label)
        self._contracts_container = QWidget(); self._contracts_container.setStyleSheet("background:transparent;")
        self._contracts_layout = QVBoxLayout(self._contracts_container)
        self._contracts_layout.setContentsMargins(0,0,0,0); self._contracts_layout.setSpacing(12)
        self._cl.addWidget(self._contracts_container); self._cl.addStretch()
        scroll.setWidget(w); return scroll

    def _input_css(self) -> str:
        return f"""QComboBox,QLineEdit{{background:{COLOR_WHITE};color:{COLOR_TEXT_DARK};
            border:1.5px solid {COLOR_LIGHT_GRAY};border-radius:8px;padding:5px 10px;font-size:12px;}}"""

    def _lbl(self, text, size=13, bold=False, color=None) -> QLabel:
        lbl = QLabel(text); c = color or COLOR_TEXT_DARK
        fw = "font-weight:700;" if bold else ""
        lbl.setStyleSheet(f"color:{c};font-size:{size}px;{fw}"); lbl.setWordWrap(True); return lbl

    def _load_contracts(self) -> None:
        status_filter = self._status_filter.currentData() or None
        while self._contracts_layout.count():
            item = self._contracts_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        r = self._svc.list_my_contracts(status_filter=status_filter)
        if not r.success:
            self._contracts_label.setText(r.message); return
        if not r.contracts:
            self._contracts_label.setText("Chưa có hợp đồng nào."); return
        self._contracts_label.setText(f"{len(r.contracts)} hợp đồng")
        for contract in r.contracts:
            self._contracts_layout.addWidget(self._make_contract_card(contract))

    def _make_contract_card(self, c: ContractModel) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        cl = QVBoxLayout(card); cl.setContentsMargins(20,16,20,16); cl.setSpacing(8)
        # Header row
        icon, color, label = STATUS_LABELS.get(c.status, ("?", "#999", c.status))
        hr = QHBoxLayout(); hr.setSpacing(10)
        st_lbl = QLabel(f"{icon} {label}")
        st_lbl.setStyleSheet(f"color:{color};font-size:11px;font-weight:600;background:rgba(0,0,0,0.05);border-radius:6px;padding:3px 8px;")
        hr.addWidget(st_lbl)
        code_lbl = QLabel(c.contract_code)
        code_lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:11px;"); hr.addWidget(code_lbl)
        hr.addStretch()
        date_lbl = QLabel(c.start_date[:10] if c.start_date else "")
        date_lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:11px;"); hr.addWidget(date_lbl)
        cl.addLayout(hr)
        # Names
        user = SessionManager.instance().current_user
        if user and user.role == "company":
            name_text = f"Chuyên gia: {c.expert_title or '—'}"
        else:
            name_text = f"Doanh nghiệp: {c.company_name or '—'}"
        cl.addWidget(self._lbl(name_text, size=14, bold=True))
        if c.notes:
            cl.addWidget(self._lbl(c.notes, size=12, color=COLOR_TEXT_MUTED))
        # Action buttons
        btns = self._get_action_buttons(c)
        if btns:
            br = QHBoxLayout(); br.setSpacing(8); br.addStretch()
            for btn in btns: br.addWidget(btn)
            cl.addLayout(br)
        return card

    def _get_action_buttons(self, c: ContractModel) -> list[QPushButton]:
        user = SessionManager.instance().current_user
        if not user: return []
        btns = []
        if user.role == "company":
            if c.status == "pending_expert":
                b = QPushButton("Hủy đề nghị"); b.setFixedHeight(34)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setStyleSheet(secondary_button_style(font_size=12, padding="6px 14px"))
                b.clicked.connect(lambda _, cid=c.id: self._do_action("cancel_pending", cid))
                btns.append(b)
            elif c.status == "active":
                b1 = QPushButton("Hoàn thành"); b1.setFixedHeight(34)
                b1.setCursor(Qt.CursorShape.PointingHandCursor)
                b1.setStyleSheet(primary_button_style(font_size=12, padding="6px 14px"))
                b1.clicked.connect(lambda _, cid=c.id: self._do_action("complete", cid))
                b2 = QPushButton("Chấm dứt"); b2.setFixedHeight(34)
                b2.setCursor(Qt.CursorShape.PointingHandCursor)
                b2.setStyleSheet(f"""QPushButton{{background:rgba(231,76,60,0.1);color:#E74C3C;
                    border:1px solid rgba(231,76,60,0.4);border-radius:8px;font-size:12px;padding:6px 14px;}}
                    QPushButton:hover{{background:rgba(231,76,60,0.2);}}""")
                b2.clicked.connect(lambda _, cid=c.id: self._do_action("terminate", cid))
                btns.extend([b1, b2])
        elif user.role == "expert":
            if c.status == "pending_expert":
                b1 = QPushButton("Chấp thuận"); b1.setFixedHeight(34)
                b1.setCursor(Qt.CursorShape.PointingHandCursor)
                b1.setStyleSheet(primary_button_style(font_size=12, padding="6px 14px"))
                b1.clicked.connect(lambda _, cid=c.id: self._do_action("accept", cid))
                b2 = QPushButton("Từ chối"); b2.setFixedHeight(34)
                b2.setCursor(Qt.CursorShape.PointingHandCursor)
                b2.setStyleSheet(secondary_button_style(font_size=12, padding="6px 14px"))
                b2.clicked.connect(lambda _, cid=c.id: self._do_action("reject", cid))
                btns.extend([b1, b2])
        return btns

    def _do_action(self, action: str, contract_id: int) -> None:
        if action == "cancel_pending":
            r = self._svc.cancel_pending_contract(contract_id)
        elif action == "complete":
            r = self._svc.complete_contract(contract_id)
        elif action == "terminate":
            r = self._svc.terminate_contract(contract_id, reason="Chấm dứt bởi doanh nghiệp")
        elif action == "accept":
            r = self._svc.accept_contract(contract_id)
        elif action == "reject":
            r = self._svc.reject_contract(contract_id)
        else:
            return
        if r.success:
            self._show_banner("Thao tác thành công!", is_error=False)
            self._load_contracts()
        else:
            self._show_banner(r.message, is_error=True)

    def _show_banner(self, text, is_error=False):
        if not text: self._banner.hide(); return
        clr = COLOR_ERROR if is_error else COLOR_SUCCESS
        bg = "rgba(231,76,60,0.08)" if is_error else "rgba(39,174,96,0.08)"
        self._banner.setStyleSheet(f"background:{bg};color:{clr};border-radius:8px;padding:8px 16px;font-size:12px;")
        self._banner.setText(text); self._banner.show()

    def _handle_back(self):
        if callable(self._on_back_cb): self._on_back_cb()

    def _handle_find_experts(self):
        if callable(self._on_find_experts_cb): self._on_find_experts_cb()

    def _animate_in(self):
        self._eff = QGraphicsOpacityEffect(self); self.setGraphicsEffect(self._eff)
        self._eff.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._eff, b"opacity")
        self._anim.setDuration(400); self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0); self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def refresh(self): self._load_contracts()
