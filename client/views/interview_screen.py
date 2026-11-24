"""Interview schedule and evaluation notes view."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.utils.constants import COLOR_OFF_WHITE
from app.utils.styles import secondary_button_style
from client.components.status_banner import StatusBanner
from client.components.workflow_page import add_workflow_header
from client.views.extended_workflow_contracts import InterviewController, InterviewEntry


class InterviewScreen(QWidget):
    """Displays Controller-provided schedules; does not simulate a video call."""

    def __init__(
        self,
        role: str,
        controller: InterviewController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._role = role
        self._controller = controller
        self._on_back_cb: Callable[[], None] | None = None
        self._interviews: dict[int, InterviewEntry] = {}
        self._selected: InterviewEntry | None = None
        self.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        self._build_ui()
        if controller is None:
            self._status.set_status(
                "Chưa có Interview Controller. Lịch và ghi chú chưa thể tải "
                "hoặc lưu; chưa có cuộc gọi video nào được tạo.",
                "unavailable",
            )
        else:
            self.refresh()

    @property
    def on_back(self) -> Callable[[], None] | None:
        return self._on_back_cb

    @on_back.setter
    def on_back(self, callback: Callable[[], None] | None) -> None:
        self._on_back_cb = callback

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        self._back_button = add_workflow_header(
            layout, "Lịch phỏng vấn", self._handle_back
        )
        self._status = StatusBanner()
        layout.addWidget(self._status)
        self._refresh_button = QPushButton("Tải lịch")
        self._refresh_button.setStyleSheet(secondary_button_style(font_size=12))
        self._refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self._refresh_button, alignment=Qt.AlignmentFlag.AlignRight)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Buổi phỏng vấn", "Ứng viên", "Thời gian", "Trạng thái"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self._table, stretch=1)

        self._meeting_link = QLabel("Liên kết họp ngoài: chưa có dữ liệu.")
        self._meeting_link.setWordWrap(True)
        layout.addWidget(self._meeting_link)
        self._evaluation_label = QLabel("Ghi chú đánh giá")
        self._evaluation_notes = QPlainTextEdit()
        self._evaluation_notes.setPlaceholderText(
            "Nhập ghi chú đánh giá sau buổi phỏng vấn."
        )
        self._evaluation_notes.setMaximumHeight(120)
        layout.addWidget(self._evaluation_label)
        layout.addWidget(self._evaluation_notes)
        self._save_button = QPushButton("Lưu ghi chú")
        self._save_button.setStyleSheet(secondary_button_style(font_size=12))
        self._save_button.clicked.connect(self._save_evaluation)
        layout.addWidget(self._save_button, alignment=Qt.AlignmentFlag.AlignRight)
        self._refresh_button.setEnabled(self._controller is not None)
        self._save_button.setEnabled(False)
        if self._role == "candidate":
            self._evaluation_label.hide()
            self._evaluation_notes.hide()
            self._save_button.hide()

    def refresh(self) -> None:
        if self._controller is None:
            self._status.set_status(
                "Chưa có Interview Controller; lịch chưa được kết nối.",
                "unavailable",
            )
            return
        self._status.set_status("Đang tải lịch phỏng vấn...", "loading")
        result = self._controller.list_interviews()
        self._table.setRowCount(0)
        self._interviews = {item.id: item for item in result.items}
        self._selected = None
        if not result.success:
            self._status.set_status(
                result.message or "Không thể tải lịch phỏng vấn.", "error"
            )
            self._show_interview(None)
            return
        for item in result.items:
            row = self._table.rowCount()
            self._table.insertRow(row)
            values = (item.title, item.candidate_name, item.scheduled_at, item.status)
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.id)
                self._table.setItem(row, column, cell)
        self._status.set_status(
            "" if result.items else "Chưa có lịch phỏng vấn.",
            "info" if result.items else "empty",
        )
        self._show_interview(None)

    def _selection_changed(self) -> None:
        row = self._table.currentRow()
        cell = self._table.item(row, 0) if row >= 0 else None
        interview_id = cell.data(Qt.ItemDataRole.UserRole) if cell else None
        self._show_interview(self._interviews.get(interview_id))

    def _show_interview(self, item: InterviewEntry | None) -> None:
        self._selected = item
        if item is None:
            self._meeting_link.setText("Liên kết họp ngoài: chưa có dữ liệu.")
            self._evaluation_notes.clear()
            self._save_button.setEnabled(False)
            return
        self._meeting_link.setText(
            f"Liên kết họp ngoài: {item.meeting_url or 'Chưa được cung cấp.'}"
        )
        self._evaluation_notes.setPlainText(item.evaluation_notes)
        self._save_button.setEnabled(
            self._controller is not None
            and self._role in {"company", "expert"}
            and item.status in {"scheduled", "in_progress", "completed"}
        )

    def _save_evaluation(self) -> None:
        if (
            self._controller is None
            or self._selected is None
            or self._role not in {"company", "expert"}
        ):
            return
        result = self._controller.save_evaluation(
            self._selected.id, self._evaluation_notes.toPlainText().strip()
        )
        self._status.set_status(
            result.message or (
                "Đã lưu ghi chú đánh giá."
                if result.success
                else "Không thể lưu ghi chú."
            ),
            "success" if result.success else "error",
        )

    def _handle_back(self) -> None:
        if self._on_back_cb is not None:
            self._on_back_cb()
