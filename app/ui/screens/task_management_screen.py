"""
TaskManagementScreen — Quản lý nhiệm vụ được phân công.

Company: tạo task, xem danh sách, cancel.
Expert: xem task được assign, nhận (start), hoàn thành, cancel.
"""

from __future__ import annotations

from PySide6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QComboBox,
    QLineEdit, QGraphicsOpacityEffect,
)

from app.utils.constants import (
    APP_NAME, COLOR_NAVY_DARK, COLOR_NAVY_MID, COLOR_ACCENT,
    COLOR_WHITE, COLOR_OFF_WHITE, COLOR_LIGHT_GRAY,
    COLOR_TEXT_DARK, COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_ERROR,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
)
from app.utils.styles import primary_button_style, secondary_button_style
from app.services.task_service import (
    TaskService, TaskResult, TaskModel,
    TASK_TYPE_LABELS, TASK_STATUS_LABELS, TASK_PRIORITY_LABELS,
    TASK_TYPES, TASK_PRIORITY,
)
from app.services.contract_service import ContractService, ContractResult
from app.services.auth_service import SessionManager

TASK_STATUS_COLORS = {
    "pending":     "#F39C12",
    "in_progress": "#2E86DE",
    "completed":   "#27AE60",
    "cancelled":   "#7F8C8D",
}


class TaskManagementScreen(QWidget):
    """Màn hình quản lý task. Callbacks: on_back."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._on_back_cb = None
        self._svc = TaskService()
        self._contract_svc = ContractService()
        self._setup_ui()
        self._load_tasks()
        QTimer.singleShot(80, self._animate_in)

    @property
    def on_back(self): return self._on_back_cb
    @on_back.setter
    def on_back(self, cb): self._on_back_cb = cb

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self); main.setContentsMargins(0,0,0,0); main.setSpacing(0)
        main.addWidget(self._make_sidebar()); main.addWidget(self._make_content(), stretch=1)

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
        for icon, text in [("🎯", "Nhiệm vụ của tôi")]:
            btn = QPushButton(f"  {icon}  {text}"); btn.setFixedHeight(38)
            btn.setStyleSheet(f"""QPushButton{{background:rgba(46,134,222,0.2);color:{COLOR_WHITE};
                border:none;border-radius:8px;font-size:12px;text-align:left;padding-left:8px;}}""")
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
        left.addWidget(self._lbl("Quản lý nhiệm vụ", size=22, bold=True, color=COLOR_NAVY_DARK))
        left.addWidget(self._lbl("Nhiệm vụ được phân công", size=13, color=COLOR_TEXT_MUTED))
        left.setSpacing(4); hl.addLayout(left); hl.addStretch()
        ref = QPushButton("🔄 Tải lại"); ref.setCursor(Qt.CursorShape.PointingHandCursor)
        ref.setStyleSheet(secondary_button_style(font_size=12, padding="8px 16px"))
        ref.clicked.connect(self._load_tasks); hl.addWidget(ref); self._cl.addWidget(hdr)
        # Banner
        self._banner = QLabel(""); self._banner.setWordWrap(True)
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setStyleSheet(f"background:transparent;color:{COLOR_ERROR};font-size:12px;min-height:20px;")
        self._banner.hide(); self._cl.addWidget(self._banner)
        # Create task (Company only)
        user = SessionManager.instance().current_user
        if user and user.role == "company":
            self._create_panel = self._make_create_panel()
            self._cl.addWidget(self._create_panel)
        # Filter
        ff = QFrame(); ff.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:10px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        fl = QHBoxLayout(ff); fl.setContentsMargins(16,12,16,12); fl.setSpacing(12)
        fl.addWidget(self._lbl("Lọc:", size=12))
        self._status_filter = QComboBox(); self._status_filter.setFixedHeight(36)
        self._status_filter.addItem("Tất cả trạng thái", "")
        for s, lbl in TASK_STATUS_LABELS.items():
            self._status_filter.addItem(lbl, s)
        self._status_filter.setStyleSheet(self._input_css())
        self._status_filter.currentIndexChanged.connect(self._load_tasks)
        fl.addWidget(self._status_filter); fl.addStretch(); self._cl.addWidget(ff)
        # Tasks container
        self._tasks_label = self._lbl("Đang tải...", color=COLOR_TEXT_MUTED)
        self._cl.addWidget(self._tasks_label)
        self._tasks_container = QWidget(); self._tasks_container.setStyleSheet("background:transparent;")
        self._tasks_layout = QVBoxLayout(self._tasks_container)
        self._tasks_layout.setContentsMargins(0,0,0,0); self._tasks_layout.setSpacing(12)
        self._cl.addWidget(self._tasks_container); self._cl.addStretch()
        scroll.setWidget(w); return scroll

    def _make_create_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        cl = QVBoxLayout(panel); cl.setContentsMargins(20,16,20,16); cl.setSpacing(10)
        cl.addWidget(self._lbl("Tạo nhiệm vụ mới", size=14, bold=True))
        # Row 1: title + type
        r1 = QHBoxLayout(); r1.setSpacing(10)
        self._task_title = QLineEdit(); self._task_title.setPlaceholderText("Tiêu đề nhiệm vụ *")
        self._task_title.setFixedHeight(38); self._task_title.setStyleSheet(self._input_css()); r1.addWidget(self._task_title)
        self._task_type_combo = QComboBox(); self._task_type_combo.setFixedHeight(38)
        for tt in TASK_TYPES:
            self._task_type_combo.addItem(TASK_TYPE_LABELS.get(tt, tt), tt)
        self._task_type_combo.setStyleSheet(self._input_css()); r1.addWidget(self._task_type_combo); cl.addLayout(r1)
        # Row 2: contract + priority + submit
        r2 = QHBoxLayout(); r2.setSpacing(10)
        self._contract_combo = QComboBox(); self._contract_combo.setFixedHeight(38)
        self._contract_combo.setPlaceholderText("Chọn hợp đồng *")
        self._contract_combo.setStyleSheet(self._input_css()); r2.addWidget(self._contract_combo)
        self._priority_combo = QComboBox(); self._priority_combo.setFixedHeight(38)
        for p in TASK_PRIORITY:
            self._priority_combo.addItem(TASK_PRIORITY_LABELS.get(p, p), p)
        self._priority_combo.setCurrentIndex(1)  # normal
        self._priority_combo.setStyleSheet(self._input_css()); r2.addWidget(self._priority_combo)
        sub = QPushButton("+ Tạo nhiệm vụ"); sub.setFixedHeight(38)
        sub.setCursor(Qt.CursorShape.PointingHandCursor)
        sub.setStyleSheet(primary_button_style(font_size=12, padding="8px 16px"))
        sub.clicked.connect(self._on_create_task); r2.addWidget(sub); cl.addLayout(r2)
        self._load_active_contracts()
        return panel

    def _load_active_contracts(self) -> None:
        """Load active contracts vào combo cho Company."""
        if not hasattr(self, "_contract_combo"): return
        r = self._contract_svc.list_my_contracts(status_filter="active")
        self._contract_combo.clear()
        self._contract_combo.addItem("-- Chọn hợp đồng --", None)
        if r.success:
            for c in r.contracts:
                label = f"{c.contract_code} — {c.expert_title or '?'}"
                self._contract_combo.addItem(label, c.id)

    def _on_create_task(self) -> None:
        title = self._task_title.text().strip()
        task_type = self._task_type_combo.currentData()
        contract_id = self._contract_combo.currentData()
        priority = self._priority_combo.currentData()
        if not title:
            self._show_banner("Vui lòng nhập tiêu đề nhiệm vụ.", is_error=True); return
        if not contract_id:
            self._show_banner("Vui lòng chọn hợp đồng.", is_error=True); return
        r = self._svc.create_task(contract_id, title, task_type, priority=priority)
        if r.success:
            self._task_title.clear()
            self._show_banner("Tạo nhiệm vụ thành công!", is_error=False)
            self._load_tasks()
        else:
            self._show_banner(r.message, is_error=True)

    def _load_tasks(self) -> None:
        status_filter = self._status_filter.currentData() or None
        while self._tasks_layout.count():
            item = self._tasks_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        r = self._svc.list_my_tasks(status_filter=status_filter)
        if not r.success:
            self._tasks_label.setText(r.message); return
        if not r.tasks:
            self._tasks_label.setText("Chưa có nhiệm vụ nào."); return
        self._tasks_label.setText(f"{len(r.tasks)} nhiệm vụ")
        for task in r.tasks:
            self._tasks_layout.addWidget(self._make_task_card(task))

    def _make_task_card(self, t: TaskModel) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{COLOR_WHITE};border-radius:12px;border:1px solid {COLOR_LIGHT_GRAY};}}")
        cl = QVBoxLayout(card); cl.setContentsMargins(20,14,20,14); cl.setSpacing(6)
        # Status + type row
        sr = QHBoxLayout(); sr.setSpacing(8)
        st_color = TASK_STATUS_COLORS.get(t.status, "#999")
        st_lbl = QLabel(TASK_STATUS_LABELS.get(t.status, t.status))
        st_lbl.setStyleSheet(f"color:{st_color};font-size:11px;font-weight:600;background:rgba(0,0,0,0.05);border-radius:5px;padding:2px 8px;")
        ty_lbl = QLabel(TASK_TYPE_LABELS.get(t.task_type, t.task_type))
        ty_lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:11px;background:{COLOR_LIGHT_GRAY};border-radius:5px;padding:2px 8px;")
        pr_lbl = QLabel(TASK_PRIORITY_LABELS.get(t.priority, t.priority))
        pr_lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:11px;")
        sr.addWidget(st_lbl); sr.addWidget(ty_lbl); sr.addWidget(pr_lbl); sr.addStretch()
        date_lbl = QLabel(t.assigned_at[:10] if t.assigned_at else "")
        date_lbl.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:11px;"); sr.addWidget(date_lbl)
        cl.addLayout(sr)
        cl.addWidget(self._lbl(t.title, size=14, bold=True))
        if t.description:
            cl.addWidget(self._lbl(t.description[:100] + ("..." if len(t.description) > 100 else ""), size=12, color=COLOR_TEXT_MUTED))
        # Action buttons
        btns = self._get_task_buttons(t)
        if btns:
            br = QHBoxLayout(); br.setSpacing(8); br.addStretch()
            for btn in btns: br.addWidget(btn)
            cl.addLayout(br)
        return card

    def _get_task_buttons(self, t: TaskModel) -> list[QPushButton]:
        user = SessionManager.instance().current_user
        if not user: return []
        btns = []
        if user.role == "expert":
            if t.status == "pending":
                b = QPushButton("Nhận nhiệm vụ"); b.setFixedHeight(32)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setStyleSheet(primary_button_style(font_size=12, padding="5px 12px"))
                b.clicked.connect(lambda _, tid=t.id: self._do_task_action("start", tid))
                btns.append(b)
            elif t.status == "in_progress":
                b1 = QPushButton("Hoàn thành"); b1.setFixedHeight(32)
                b1.setCursor(Qt.CursorShape.PointingHandCursor)
                b1.setStyleSheet(primary_button_style(font_size=12, padding="5px 12px"))
                b1.clicked.connect(lambda _, tid=t.id: self._do_task_action("complete", tid))
                b2 = QPushButton("Hủy"); b2.setFixedHeight(32)
                b2.setCursor(Qt.CursorShape.PointingHandCursor)
                b2.setStyleSheet(secondary_button_style(font_size=12, padding="5px 12px"))
                b2.clicked.connect(lambda _, tid=t.id: self._do_task_action("cancel", tid))
                btns.extend([b1, b2])
        elif user.role == "company":
            if t.status in ("pending", "in_progress"):
                b = QPushButton("Hủy task"); b.setFixedHeight(32)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setStyleSheet(secondary_button_style(font_size=12, padding="5px 12px"))
                b.clicked.connect(lambda _, tid=t.id: self._do_task_action("cancel", tid))
                btns.append(b)
        return btns

    def _do_task_action(self, action: str, task_id: int) -> None:
        if action == "start":
            r = self._svc.start_task(task_id)
        elif action == "complete":
            r = self._svc.complete_task(task_id)
        elif action == "cancel":
            r = self._svc.cancel_task(task_id)
        else: return
        if r.success:
            self._show_banner("Cập nhật thành công!", is_error=False); self._load_tasks()
        else:
            self._show_banner(r.message, is_error=True)

    def _input_css(self) -> str:
        return f"""QComboBox,QLineEdit{{background:{COLOR_WHITE};color:{COLOR_TEXT_DARK};
            border:1.5px solid {COLOR_LIGHT_GRAY};border-radius:8px;padding:5px 10px;font-size:12px;}}"""

    def _lbl(self, text, size=13, bold=False, color=None) -> QLabel:
        lbl = QLabel(text); c = color or COLOR_TEXT_DARK
        fw = "font-weight:700;" if bold else ""
        lbl.setStyleSheet(f"color:{c};font-size:{size}px;{fw}"); lbl.setWordWrap(True); return lbl

    def _show_banner(self, text, is_error=False):
        if not text: self._banner.hide(); return
        clr = COLOR_ERROR if is_error else COLOR_SUCCESS
        bg = "rgba(231,76,60,0.08)" if is_error else "rgba(39,174,96,0.08)"
        self._banner.setStyleSheet(f"background:{bg};color:{clr};border-radius:8px;padding:8px 16px;font-size:12px;")
        self._banner.setText(text); self._banner.show()

    def _handle_back(self):
        if callable(self._on_back_cb): self._on_back_cb()

    def _animate_in(self):
        self._eff = QGraphicsOpacityEffect(self); self.setGraphicsEffect(self._eff)
        self._eff.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._eff, b"opacity")
        self._anim.setDuration(400); self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0); self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def refresh(self): self._load_tasks()
