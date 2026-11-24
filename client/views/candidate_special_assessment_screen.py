"""Candidate essay and coding workflow, driven only by its Controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from app.utils.constants import COLOR_NAVY_DARK, COLOR_OFF_WHITE, COLOR_TEXT_MUTED
from app.utils.styles import primary_button_style, secondary_button_style
from client.components.status_banner import StatusBanner
from client.components.workflow_page import add_workflow_header
from client.views.extended_workflow_contracts import (
    CandidateSpecializedAssessment,
    CandidateSpecializedAssessmentController,
)


class CandidateSpecialAssessmentScreen(QWidget):
    """UI for written/coding assessments; no runtime mock content is used."""

    def __init__(
        self,
        controller: CandidateSpecializedAssessmentController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._on_back_cb: Callable[[], None] | None = None
        self._assignments: dict[int, CandidateSpecializedAssessment] = {}
        self._selected: CandidateSpecializedAssessment | None = None
        self.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        self._build_ui()
        if controller is None:
            self._set_unavailable()
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
            layout, "Bài tự luận & Coding", self._handle_back
        )

        self._status = StatusBanner()
        layout.addWidget(self._status)
        self._refresh_button = QPushButton("Tải bài đánh giá")
        self._refresh_button.setStyleSheet(secondary_button_style(font_size=12))
        self._refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self._refresh_button, alignment=Qt.AlignmentFlag.AlignRight)

        self._assignments_table = QTableWidget(0, 4)
        self._assignments_table.setHorizontalHeaderLabels(
            ["Bài đánh giá", "Dạng bài", "Trạng thái", "Thời lượng"]
        )
        self._assignments_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._assignments_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._assignments_table.itemSelectionChanged.connect(
            self._selection_changed
        )
        layout.addWidget(self._assignments_table, stretch=1)

        self._prompt = QLabel("Chọn bài để xem nội dung.")
        self._prompt.setWordWrap(True)
        self._prompt.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};background:white;"
            "border:1px solid #DCE3EB;border-radius:8px;padding:14px;"
        )
        layout.addWidget(self._prompt)

        spec_row = QHBoxLayout()
        self._input_description = QLabel("")
        self._input_description.setWordWrap(True)
        self._output_description = QLabel("")
        self._output_description.setWordWrap(True)
        spec_row.addWidget(self._input_description)
        spec_row.addWidget(self._output_description)
        layout.addLayout(spec_row)

        self._public_cases = QPlainTextEdit()
        self._public_cases.setReadOnly(True)
        self._public_cases.setPlaceholderText(
            "Test cases công khai sẽ được cung cấp cùng đề bài."
        )
        self._public_cases.setMaximumHeight(110)
        layout.addWidget(self._public_cases)

        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Ngôn ngữ:"))
        self._language = QComboBox()
        self._language.setEnabled(False)
        language_row.addWidget(self._language)
        language_row.addStretch()
        layout.addLayout(language_row)

        self._answer = QPlainTextEdit()
        self._answer.setPlaceholderText("Nhập câu trả lời tại đây.")
        self._answer.setMinimumHeight(130)
        layout.addWidget(self._answer, stretch=1)

        actions = QHBoxLayout()
        self._answer_status = QLabel("")
        self._answer_status.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        actions.addWidget(self._answer_status, stretch=1)
        self._save_button = QPushButton("Lưu bài")
        self._save_button.setStyleSheet(secondary_button_style(font_size=12))
        self._save_button.clicked.connect(self._save_answer)
        self._submit_button = QPushButton("Nộp bài")
        self._submit_button.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._submit_button.clicked.connect(self._submit_answer)
        self._result_button = QPushButton("Xem kết quả")
        self._result_button.setStyleSheet(secondary_button_style(font_size=12))
        self._result_button.clicked.connect(self._load_result)
        actions.addWidget(self._save_button)
        actions.addWidget(self._submit_button)
        actions.addWidget(self._result_button)
        layout.addLayout(actions)
        self._refresh_button.setEnabled(self._controller is not None)
        self._set_editor_enabled(False)

    def _set_unavailable(self) -> None:
        self._status.set_status(
            "Chưa có Candidate Controller cho bài tự luận/Coding. "
            "Không thể tải bài, lưu hoặc nộp câu trả lời.",
            "unavailable",
        )
        self._refresh_controls()

    def refresh(self) -> None:
        if self._controller is None:
            self._set_unavailable()
            return
        self._status.set_status("Đang tải bài đánh giá...", "loading")
        result = self._controller.list_assignments()
        self._assignments_table.setRowCount(0)
        self._assignments = {item.id: item for item in result.items}
        self._selected = None
        if not result.success:
            self._status.set_status(
                result.message or "Không thể tải danh sách bài đánh giá.", "error"
            )
            self._show_assignment(None)
            return
        for item in result.items:
            row = self._assignments_table.rowCount()
            self._assignments_table.insertRow(row)
            values = (
                item.title,
                "Tự luận" if item.kind == "essay" else "Coding",
                item.status,
                f"{item.duration_minutes} phút" if item.duration_minutes else "—",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.id)
                self._assignments_table.setItem(row, column, cell)
        if result.items:
            self._status.set_status("", "info")
        else:
            self._status.set_status("Hiện chưa có bài tự luận/Coding được giao.", "empty")
        self._show_assignment(None)

    def _selection_changed(self) -> None:
        row = self._assignments_table.currentRow()
        item = self._assignments_table.item(row, 0) if row >= 0 else None
        assignment_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._show_assignment(self._assignments.get(assignment_id))

    def _show_assignment(
        self, assignment: CandidateSpecializedAssessment | None
    ) -> None:
        self._selected = assignment
        self._language.clear()
        if assignment is None:
            self._prompt.setText("Chọn bài để xem nội dung.")
            self._input_description.clear()
            self._output_description.clear()
            self._public_cases.clear()
            self._answer.clear()
            self._answer_status.clear()
            self._set_editor_enabled(False)
            self._refresh_controls()
            return

        self._prompt.setText(assignment.prompt)
        is_coding = assignment.kind == "coding"
        self._input_description.setText(
            f"Đầu vào: {assignment.input_description}" if is_coding else ""
        )
        self._output_description.setText(
            f"Đầu ra: {assignment.output_description}" if is_coding else ""
        )
        self._public_cases.setPlainText(
            "\n\n".join(assignment.public_test_cases) if is_coding else ""
        )
        self._public_cases.setVisible(is_coding)
        self._input_description.setVisible(is_coding)
        self._output_description.setVisible(is_coding)
        self._answer.setPlaceholderText(
            "Nhập mã nguồn tại đây." if is_coding else "Nhập câu trả lời tại đây."
        )
        self._answer.setPlainText(assignment.saved_answer)
        self._answer.setStyleSheet(
            "font-family:Consolas,monospace;" if is_coding else ""
        )
        for language in assignment.supported_languages:
            self._language.addItem(language)
        if assignment.saved_language:
            index = self._language.findText(assignment.saved_language)
            if index >= 0:
                self._language.setCurrentIndex(index)
        self._language.setEnabled(is_coding and bool(assignment.supported_languages))
        self._answer_status.setText(f"Trạng thái: {assignment.status}")
        if is_coding and not assignment.supported_languages:
            self._status.set_status(
                "Backend chưa cung cấp danh sách ngôn ngữ Coding được hỗ trợ.",
                "unavailable",
            )
        else:
            self._status.set_status("", "info")
        editable = assignment.status == "in_progress"
        self._set_editor_enabled(editable)
        self._refresh_controls()

    def _set_editor_enabled(self, enabled: bool) -> None:
        self._answer.setEnabled(enabled)
        self._language.setEnabled(
            enabled
            and self._selected is not None
            and self._selected.kind == "coding"
            and bool(self._selected.supported_languages)
        )

    def _refresh_controls(self) -> None:
        assignment = self._selected
        can_edit = (
            self._controller is not None
            and assignment is not None
            and assignment.status == "in_progress"
            and (
                assignment.kind == "essay"
                or bool(assignment.supported_languages)
            )
        )
        self._save_button.setEnabled(can_edit)
        self._submit_button.setEnabled(can_edit)
        self._result_button.setEnabled(
            self._controller is not None
            and assignment is not None
            and assignment.status == "released"
        )

    def _answer_values(self) -> tuple[str, str] | None:
        assignment = self._selected
        answer = self._answer.toPlainText().strip()
        if assignment is None or not answer:
            self._status.set_status("Chọn bài và nhập câu trả lời trước.", "error")
            return None
        language = self._language.currentText() if assignment.kind == "coding" else ""
        if assignment.kind == "coding" and not language:
            self._status.set_status(
                "Backend chưa cung cấp ngôn ngữ Coding được hỗ trợ.", "unavailable"
            )
            return None
        return answer, language

    def _save_answer(self) -> None:
        if self._controller is None or self._selected is None:
            return
        values = self._answer_values()
        if values is None:
            return
        result = self._controller.save_answer(self._selected.id, *values)
        self._status.set_status(
            result.message or (
                "Đã lưu bài." if result.success else "Không thể lưu bài."
            ),
            "success" if result.success else "error",
        )
        if result.success:
            self._selected = replace(
                self._selected,
                saved_answer=values[0],
                saved_language=values[1],
                status=result.status or self._selected.status,
            )
            self._assignments[self._selected.id] = self._selected
            self._answer_status.setText(
                f"Trạng thái: {result.status or self._selected.status}"
            )
            self._refresh_controls()

    def _submit_answer(self) -> None:
        if self._controller is None or self._selected is None:
            return
        values = self._answer_values()
        if values is None:
            return
        confirmation = QMessageBox.question(
            self,
            "Xác nhận nộp bài",
            "Sau khi nộp, bạn không thể chỉnh sửa câu trả lời. Tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        self._submit_button.setEnabled(False)
        result = self._controller.submit_answer(self._selected.id, *values)
        self._status.set_status(
            result.message or (
                "Đã nộp bài." if result.success else "Không thể nộp bài."
            ),
            "success" if result.success else "error",
        )
        if result.success:
            self._answer_status.setText(
                f"Trạng thái: {result.status or 'submitted'}"
            )
            self._selected = replace(
                self._selected, status=result.status or "submitted"
            )
            self._assignments[self._selected.id] = self._selected
            self._set_editor_enabled(False)
        self._refresh_controls()

    def _load_result(self) -> None:
        if self._controller is None or self._selected is None:
            return
        result = self._controller.get_result(self._selected.id)
        if not result.success:
            self._status.set_status(
                result.message or "Không thể tải kết quả.", "error"
            )
        elif not result.released:
            self._status.set_status(
                "Kết quả chưa được công bố; chưa hiển thị điểm.", "info"
            )
        else:
            score = (
                f"Điểm: {result.score:g} / {result.max_score:g}"
                if result.score is not None and result.max_score is not None
                else "Kết quả đã được công bố."
            )
            self._status.set_status(
                "\n".join(part for part in (score, result.feedback) if part),
                "success",
            )

    def _handle_back(self) -> None:
        if self._on_back_cb is not None:
            self._on_back_cb()
