"""Company/Expert manual grading view for essay and coding submissions."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.utils.constants import COLOR_NAVY_DARK, COLOR_OFF_WHITE
from app.utils.styles import primary_button_style, secondary_button_style
from client.components.status_banner import StatusBanner
from client.components.workflow_page import add_workflow_header
from client.views.extended_workflow_contracts import (
    ManualGradingController,
    PendingGradingSubmission,
)


class GradingScreen(QWidget):
    """Manual grading actions always go through the injected Controller."""

    def __init__(
        self,
        controller: ManualGradingController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._on_back_cb: Callable[[], None] | None = None
        self._submissions: dict[int, PendingGradingSubmission] = {}
        self._selected: PendingGradingSubmission | None = None
        self.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        self._build_ui()
        if controller is None:
            self._status.set_status(
                "Chưa có Manual Grading Controller. Bài tự luận/Coding chưa "
                "được backend hỗ trợ chấm hoặc công bố.",
                "unavailable",
            )
        else:
            self.refresh()
        self._set_editor_enabled(False)

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
            layout, "Chấm bài tự luận & Coding", self._handle_back
        )

        self._status = StatusBanner()
        layout.addWidget(self._status)
        self._refresh_button = QPushButton("Tải bài cần xử lý")
        self._refresh_button.setStyleSheet(secondary_button_style(font_size=12))
        self._refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self._refresh_button, alignment=Qt.AlignmentFlag.AlignRight)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Ứng viên", "Bài đánh giá", "Dạng bài", "Trạng thái"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self._table, stretch=1)

        self._candidate = QLabel("Chọn bài để xem nội dung.")
        self._candidate.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:16px;font-weight:600;"
        )
        layout.addWidget(self._candidate)
        self._prompt = QLabel("")
        self._prompt.setWordWrap(True)
        layout.addWidget(self._prompt)
        self._answer = QPlainTextEdit()
        self._answer.setReadOnly(True)
        self._answer.setMinimumHeight(100)
        layout.addWidget(self._answer, stretch=1)

        grade_row = QHBoxLayout()
        grade_row.addWidget(QLabel("Điểm:"))
        self._score = QDoubleSpinBox()
        self._score.setRange(0, 1000000)
        self._score.setDecimals(2)
        grade_row.addWidget(self._score)
        grade_row.addWidget(QLabel("Nhận xét:"))
        grade_row.addStretch()
        layout.addLayout(grade_row)
        self._feedback = QPlainTextEdit()
        self._feedback.setPlaceholderText("Nhập nhận xét đánh giá.")
        self._feedback.setMaximumHeight(90)
        layout.addWidget(self._feedback)

        actions = QHBoxLayout()
        self._save_grade_button = QPushButton("Lưu kết quả chấm")
        self._save_grade_button.setStyleSheet(secondary_button_style(font_size=12))
        self._save_grade_button.clicked.connect(self._save_grade)
        self._release_button = QPushButton("Công bố kết quả")
        self._release_button.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._release_button.clicked.connect(self._release_result)
        actions.addStretch()
        actions.addWidget(self._save_grade_button)
        actions.addWidget(self._release_button)
        layout.addLayout(actions)

    def refresh(self) -> None:
        if self._controller is None:
            self._status.set_status(
                "Chưa có Manual Grading Controller; thao tác đang khóa.",
                "unavailable",
            )
            return
        self._status.set_status("Đang tải bài cần chấm/công bố...", "loading")
        result = self._controller.list_submissions_for_grading()
        self._table.setRowCount(0)
        self._submissions = {item.id: item for item in result.items}
        self._selected = None
        if not result.success:
            self._status.set_status(
                result.message or "Không thể tải bài cần xử lý.", "error"
            )
            self._show_submission(None)
            return
        for item in result.items:
            row = self._table.rowCount()
            self._table.insertRow(row)
            values = (
                item.candidate_name,
                item.assessment_title,
                "Tự luận" if item.kind == "essay" else "Coding",
                item.status,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.id)
                self._table.setItem(row, column, cell)
        self._status.set_status(
            "" if result.items else "Không có bài cần chấm hoặc công bố.",
            "info" if result.items else "empty",
        )
        self._show_submission(None)

    def _selection_changed(self) -> None:
        row = self._table.currentRow()
        item = self._table.item(row, 0) if row >= 0 else None
        submission_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._show_submission(self._submissions.get(submission_id))

    def _show_submission(self, submission: PendingGradingSubmission | None) -> None:
        self._selected = submission
        if submission is None:
            self._candidate.setText("Chọn bài để xem nội dung.")
            self._prompt.clear()
            self._answer.clear()
            self._feedback.clear()
            self._score.setValue(0)
            self._set_editor_enabled(False)
            return
        self._candidate.setText(
            f"{submission.candidate_name} — {submission.assessment_title} "
            f"({submission.status})"
        )
        self._prompt.setText(submission.prompt)
        language = f" — {submission.language}" if submission.language else ""
        self._answer.setPlainText(submission.submitted_answer)
        self._answer.setStyleSheet(
            "font-family:Consolas,monospace;" if submission.kind == "coding" else ""
        )
        self._answer.setPlaceholderText(f"Bài nộp{language}")
        self._score.setMaximum(max(0, submission.max_score))
        self._score.setValue(submission.score or 0)
        self._feedback.setPlainText(submission.feedback)
        if submission.max_score <= 0:
            self._status.set_status(
                "Bài nộp chưa có điểm tối đa hợp lệ; thao tác chấm bị khóa.",
                "error",
            )
        self._set_editor_enabled(True)

    def _set_editor_enabled(self, enabled: bool) -> None:
        item = self._selected
        can_grade = (
            enabled
            and self._controller is not None
            and item is not None
            and item.status in {"submitted", "grading"}
            and item.max_score > 0
        )
        can_release = (
            enabled
            and self._controller is not None
            and item is not None
            and item.status == "graded"
        )
        self._score.setEnabled(can_grade)
        self._feedback.setEnabled(can_grade)
        self._save_grade_button.setEnabled(can_grade)
        self._release_button.setEnabled(can_release)
        self._refresh_button.setEnabled(self._controller is not None)

    def _save_grade(self) -> None:
        if self._controller is None or self._selected is None:
            return
        result = self._controller.save_grade(
            self._selected.id,
            self._score.value(),
            self._feedback.toPlainText().strip(),
        )
        self._status.set_status(
            result.message or (
                "Đã lưu điểm và nhận xét."
                if result.success
                else "Không thể lưu kết quả chấm."
            ),
            "success" if result.success else "error",
        )
        if result.success:
            self.refresh()

    def _release_result(self) -> None:
        if self._controller is None or self._selected is None:
            return
        confirmation = QMessageBox.question(
            self,
            "Công bố kết quả",
            "Ứng viên sẽ xem được điểm và nhận xét sau thao tác này. Tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        self._release_button.setEnabled(False)
        result = self._controller.release_result(self._selected.id)
        self._status.set_status(
            result.message or (
                "Đã công bố kết quả."
                if result.success
                else "Không thể công bố kết quả."
            ),
            "success" if result.success else "error",
        )
        if result.success:
            self.refresh()
        else:
            self._set_editor_enabled(True)

    def _handle_back(self) -> None:
        if self._on_back_cb is not None:
            self._on_back_cb()
