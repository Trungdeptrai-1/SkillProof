"""Interview schedule and evaluation notes view."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QDateTime, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
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
        meeting_row = QHBoxLayout()
        meeting_row.addWidget(self._meeting_link, stretch=1)
        self._join_button = QPushButton("Tham gia phỏng vấn")
        self._join_button.setStyleSheet(secondary_button_style(font_size=12))
        self._join_button.clicked.connect(self._join_meeting)
        meeting_row.addWidget(self._join_button)
        layout.addLayout(meeting_row)
        self._schedule_section = QWidget()
        schedule_form = QFormLayout(self._schedule_section)
        self._candidate_id = QSpinBox()
        self._candidate_id.setRange(1, 2147483647)
        self._expert_id = QSpinBox()
        self._expert_id.setRange(0, 2147483647)
        self._expert_id.setSpecialValueText("Không chỉ định")
        self._interview_title = QLineEdit()
        self._interview_title.setPlaceholderText("Ví dụ: Phỏng vấn kỹ thuật")
        self._scheduled_at = QDateTimeEdit()
        self._scheduled_at.setCalendarPopup(True)
        self._scheduled_at.setDateTime(
            QDateTime.currentDateTime().addDays(1)
        )
        self._schedule_button = QPushButton("Tạo lịch phỏng vấn")
        self._schedule_button.setStyleSheet(secondary_button_style(font_size=12))
        self._schedule_button.clicked.connect(self._schedule_interview)
        schedule_form.addRow("Candidate ID", self._candidate_id)
        schedule_form.addRow("Expert ID (đã ký hợp đồng)", self._expert_id)
        schedule_form.addRow("Tiêu đề", self._interview_title)
        schedule_form.addRow("Thời gian", self._scheduled_at)
        schedule_form.addRow(self._schedule_button)
        layout.addWidget(self._schedule_section)

        self._status_section = QWidget()
        status_row = QHBoxLayout(self._status_section)
        self._next_status = QComboBox()
        for label, status in (
            ("Đang diễn ra", "in_progress"),
            ("Hoàn thành", "completed"),
            ("Đã hủy", "cancelled"),
            ("Ứng viên vắng mặt", "no_show"),
        ):
            self._next_status.addItem(label, status)
        self._update_status_button = QPushButton("Cập nhật trạng thái")
        self._update_status_button.setStyleSheet(
            secondary_button_style(font_size=12)
        )
        self._update_status_button.clicked.connect(self._update_status)
        status_row.addWidget(self._next_status)
        status_row.addWidget(self._update_status_button)
        layout.addWidget(self._status_section)
        self._evaluation_label = QLabel("Ghi chú đánh giá")
        self._evaluation_notes = QPlainTextEdit()
        self._evaluation_notes.setPlaceholderText(
            "Nhập ghi chú đánh giá sau buổi phỏng vấn."
        )
        self._evaluation_notes.setMaximumHeight(120)
        layout.addWidget(self._evaluation_label)
        layout.addWidget(self._evaluation_notes)
        self._scores: list[QSpinBox] = []
        self._score_section = QWidget()
        score_row = QHBoxLayout(self._score_section)
        for label in (
            "Kỹ thuật",
            "Giao tiếp",
            "Giải quyết vấn đề",
            "Tổng thể",
        ):
            score_row.addWidget(QLabel(label))
            score = QSpinBox()
            score.setRange(1, 5)
            score.setValue(3)
            self._scores.append(score)
            score_row.addWidget(score)
        layout.addWidget(self._score_section)
        self._save_button = QPushButton("Lưu ghi chú")
        self._save_button.setStyleSheet(secondary_button_style(font_size=12))
        self._save_button.clicked.connect(self._save_evaluation)
        layout.addWidget(self._save_button, alignment=Qt.AlignmentFlag.AlignRight)
        self._refresh_button.setEnabled(self._controller is not None)
        self._save_button.setEnabled(False)
        self._join_button.setEnabled(False)
        self._join_button.setVisible(self._role in {"candidate", "company", "expert"})
        if self._role == "candidate":
            self._schedule_section.hide()
            self._evaluation_label.hide()
            self._evaluation_notes.hide()
            self._save_button.hide()
            self._score_section.hide()
            self._status_section.hide()
        else:
            self._schedule_section.setVisible(self._role == "company")
            self._score_section.setVisible(self._role == "expert")
            self._evaluation_label.setVisible(self._role == "expert")
            self._evaluation_notes.setVisible(self._role == "expert")
            self._save_button.setVisible(self._role == "expert")
        self._schedule_button.setEnabled(self._controller is not None)
        self._update_status_button.setEnabled(False)

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
            self._update_status_button.setEnabled(False)
            self._join_button.setEnabled(False)
            return
        meeting_url = self._meeting_url(item.meeting_url)
        if item.meeting_url and meeting_url is None:
            self._meeting_link.setText(
                "Liên kết họp ngoài không hợp lệ; không thể mở an toàn."
            )
        else:
            self._meeting_link.setText(
                f"Liên kết họp ngoài: {item.meeting_url or 'Chưa được cung cấp.'}"
            )
        self._evaluation_notes.setPlainText(item.evaluation_notes)
        self._join_button.setEnabled(
            self._role in {"candidate", "company", "expert"}
            and self._controller is not None
            and meeting_url is not None
            and item.status in {"scheduled", "in_progress"}
        )
        self._save_button.setEnabled(
            self._controller is not None
            and self._role == "expert"
            and item.status in {"in_progress", "completed"}
        )
        self._update_status_button.setEnabled(
            self._controller is not None
            and self._role in {"company", "expert"}
            and item.status in {"scheduled", "in_progress"}
        )

    def _save_evaluation(self) -> None:
        if (
            self._controller is None
            or self._selected is None
            or self._role != "expert"
        ):
            return
        result = self._controller.save_evaluation(
            self._selected.id,
            self._evaluation_notes.toPlainText().strip(),
            *(score.value() for score in self._scores),
        )
        self._status.set_status(
            result.message or (
                "Đã lưu ghi chú đánh giá."
                if result.success
                else "Không thể lưu ghi chú."
            ),
            "success" if result.success else "error",
        )
        if result.success:
            self.refresh()

    def _schedule_interview(self) -> None:
        if self._controller is None or self._role != "company":
            return
        title = self._interview_title.text().strip()
        if not title:
            self._status.set_status("Nhập tiêu đề buổi phỏng vấn.", "error")
            return
        scheduled_at = self._scheduled_at.dateTime().toString(
            "yyyy-MM-dd'T'HH:mm:ss"
        )
        result = self._controller.schedule_interview(
            self._candidate_id.value(),
            title,
            scheduled_at,
            (self._expert_id.value(),) if self._expert_id.value() > 0 else (),
        )
        self._status.set_status(
            result.message or (
                "Đã tạo lịch phỏng vấn."
                if result.success
                else "Không thể tạo lịch phỏng vấn."
            ),
            "success" if result.success else "error",
        )
        if result.success:
            self._interview_title.clear()
            self.refresh()

    def _update_status(self) -> None:
        if self._controller is None or self._selected is None:
            return
        result = self._controller.update_status(
            self._selected.id, self._next_status.currentData()
        )
        self._status.set_status(
            result.message or (
                "Đã cập nhật trạng thái."
                if result.success
                else "Không thể cập nhật trạng thái."
            ),
            "success" if result.success else "error",
        )
        if result.success:
            self.refresh()

    @staticmethod
    def _meeting_url(value: str) -> QUrl | None:
        url = QUrl(value.strip())
        if (
            not url.isValid()
            or url.scheme().lower() not in {"http", "https"}
            or not url.host()
        ):
            return None
        return url

    def _join_meeting(self) -> None:
        if self._selected is None or self._role not in {
            "candidate",
            "company",
            "expert",
        }:
            self._status.set_status(
                "Bạn không có quyền tham gia buổi phỏng vấn này.", "error"
            )
            return
        if self._selected.status not in {"scheduled", "in_progress"}:
            self._status.set_status(
                "Buổi phỏng vấn hiện không ở trạng thái có thể tham gia.",
                "unavailable",
            )
            return
        url = self._meeting_url(self._selected.meeting_url)
        if url is None:
            self._status.set_status(
                "Buổi phỏng vấn chưa có liên kết HTTPS/HTTP hợp lệ.", "unavailable"
            )
            return
        if not QDesktopServices.openUrl(url):
            self._status.set_status(
                "Không thể mở liên kết họp bằng trình duyệt hệ thống.", "error"
            )
            return
        self._status.set_status(
            "Đã mở liên kết phỏng vấn trong trình duyệt hệ thống.", "success"
        )

    def _handle_back(self) -> None:
        if self._on_back_cb is not None:
            self._on_back_cb()
