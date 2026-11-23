"""Company recruitment workspace for jobs, assessments, invitations, and results."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.utils.constants import (
    COLOR_NAVY_DARK,
    COLOR_OFF_WHITE,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from app.utils.styles import primary_button_style, secondary_button_style
from client.components.status_banner import StatusBanner
from client.views.recruitment_contracts import (
    Assessment,
    AssessmentResultRow,
    Candidate,
    CompanyRecruitmentController,
    Position,
    QuestionDraft,
)


class CompanyRecruitmentScreen(QWidget):
    """Company UI; data and mutations are only available through a Controller."""

    def __init__(
        self,
        controller: CompanyRecruitmentController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._controller = controller
        self._on_back_cb: Callable[[], None] | None = None
        self._positions: tuple[Position, ...] = ()
        self._assessments: tuple[Assessment, ...] = ()
        self._candidates: tuple[Candidate, ...] = ()
        self._results: tuple[AssessmentResultRow, ...] = ()
        self._question_drafts: list[QuestionDraft] = []
        self._editing_position_id: int | None = None
        self._setup_ui()
        if self._controller is None:
            self._set_unavailable()
        else:
            self.refresh()

    @property
    def on_back(self) -> Callable[[], None] | None:
        return self._on_back_cb

    @on_back.setter
    def on_back(self, callback: Callable[[], None] | None) -> None:
        self._on_back_cb = callback

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Tuyển dụng và đánh giá")
        title.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:23px;font-weight:700;"
        )
        self._back_button = QPushButton("← Quay lại Dashboard")
        self._back_button.setStyleSheet(secondary_button_style(font_size=12))
        self._back_button.clicked.connect(self._handle_back)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._back_button)
        layout.addLayout(header)

        self._status = StatusBanner()
        layout.addWidget(self._status)

        self._tabs = QTabWidget()
        self._positions_tab = self._build_positions_tab()
        self._assessments_tab = self._build_assessments_tab()
        self._invitations_tab = self._build_invitations_tab()
        self._results_tab = self._build_results_tab()
        self._tabs.addTab(self._positions_tab, "Vị trí tuyển dụng")
        self._tabs.addTab(self._assessments_tab, "Bài thi")
        self._tabs.addTab(self._invitations_tab, "Mời ứng viên")
        self._tabs.addTab(self._results_tab, "Kết quả")
        layout.addWidget(self._tabs, stretch=1)

    def _build_positions_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        self._position_search = QLineEdit()
        self._position_search.setPlaceholderText("Lọc vị trí trong danh sách")
        self._position_search.textChanged.connect(self._filter_positions)
        self._positions_refresh = QPushButton("Tải lại")
        self._positions_refresh.setStyleSheet(secondary_button_style(font_size=12))
        self._positions_refresh.clicked.connect(self.refresh_positions)
        controls.addWidget(self._position_search, stretch=1)
        controls.addWidget(self._positions_refresh)
        layout.addLayout(controls)

        self._positions_status = StatusBanner(tab)
        layout.addWidget(self._positions_status)
        self._positions_table = self._make_table(
            ["Mã", "Vị trí", "Địa điểm", "Hình thức", "Trạng thái"]
        )
        self._positions_table.itemSelectionChanged.connect(
            self._position_selection_changed
        )
        layout.addWidget(self._positions_table, stretch=2)

        form = QFormLayout()
        self._position_title = QLineEdit()
        self._position_title.setPlaceholderText("Ví dụ: Kỹ sư phần mềm")
        self._position_location = QLineEdit()
        self._position_location.setPlaceholderText("Địa điểm làm việc")
        self._position_type = QComboBox()
        self._position_type.addItem("Toàn thời gian", "full_time")
        self._position_type.addItem("Bán thời gian", "part_time")
        self._position_type.addItem("Hợp đồng", "contract")
        self._position_type.addItem("Thực tập", "internship")
        self._position_description = QTextEdit()
        self._position_description.setMaximumHeight(76)
        form.addRow("Tên vị trí *", self._position_title)
        form.addRow("Địa điểm *", self._position_location)
        form.addRow("Hình thức", self._position_type)
        form.addRow("Mô tả", self._position_description)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self._position_save = QPushButton("Tạo vị trí")
        self._position_save.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._position_save.clicked.connect(self._save_position)
        self._position_edit = QPushButton("Sửa vị trí đã chọn")
        self._position_edit.setStyleSheet(secondary_button_style(font_size=12))
        self._position_edit.setEnabled(False)
        self._position_edit.clicked.connect(self._edit_position)
        self._position_clear = QPushButton("Xoá biểu mẫu")
        self._position_clear.setStyleSheet(secondary_button_style(font_size=12))
        self._position_clear.clicked.connect(self._clear_position_form)
        actions.addStretch()
        actions.addWidget(self._position_edit)
        actions.addWidget(self._position_clear)
        actions.addWidget(self._position_save)
        layout.addLayout(actions)
        return tab

    def _build_assessments_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self._assessments_status = StatusBanner(tab)
        layout.addWidget(self._assessments_status)
        self._assessments_table = self._make_table(
            ["Mã", "Bài thi", "Thời lượng (phút)", "Số câu"]
        )
        layout.addWidget(self._assessments_table, stretch=1)

        form = QFormLayout()
        self._assessment_title = QLineEdit()
        self._assessment_title.setPlaceholderText("Tên bài thi")
        self._assessment_description = QTextEdit()
        self._assessment_description.setMaximumHeight(60)
        self._assessment_duration = QSpinBox()
        self._assessment_duration.setRange(1, 600)
        self._assessment_duration.setValue(60)
        form.addRow("Tên bài thi *", self._assessment_title)
        form.addRow("Mô tả", self._assessment_description)
        form.addRow("Thời lượng (phút)", self._assessment_duration)
        layout.addLayout(form)

        question_group = QVBoxLayout()
        question_group.addWidget(QLabel("Thêm câu hỏi trắc nghiệm"))
        self._question_prompt = QLineEdit()
        self._question_prompt.setPlaceholderText("Nội dung câu hỏi *")
        question_group.addWidget(self._question_prompt)

        options_row = QHBoxLayout()
        self._question_options: list[QLineEdit] = []
        for letter in ("A", "B", "C", "D"):
            option = QLineEdit()
            option.setPlaceholderText(f"Đáp án {letter}")
            self._question_options.append(option)
            options_row.addWidget(option)
        self._correct_option = QComboBox()
        for index, letter in enumerate(("A", "B", "C", "D")):
            self._correct_option.addItem(f"Đáp án đúng: {letter}", index)
        options_row.addWidget(self._correct_option)
        self._question_add = QPushButton("Thêm câu hỏi")
        self._question_add.setStyleSheet(secondary_button_style(font_size=12))
        self._question_add.clicked.connect(self._add_question)
        options_row.addWidget(self._question_add)
        question_group.addLayout(options_row)

        self._questions_table = self._make_table(
            ["Câu hỏi", "Các phương án", "Đáp án đúng"]
        )
        self._question_remove = QPushButton("Xoá câu hỏi đã chọn")
        self._question_remove.setStyleSheet(secondary_button_style(font_size=12))
        self._question_remove.clicked.connect(self._remove_question)
        question_group.addWidget(self._questions_table)
        question_group.addWidget(self._question_remove, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(question_group, stretch=1)

        actions = QHBoxLayout()
        self._assessment_refresh = QPushButton("Tải bài thi")
        self._assessment_refresh.setStyleSheet(secondary_button_style(font_size=12))
        self._assessment_refresh.clicked.connect(self.refresh_assessments)
        self._assessment_create = QPushButton("Tạo bài thi")
        self._assessment_create.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._assessment_create.clicked.connect(self._create_assessment)
        actions.addWidget(self._assessment_refresh)
        actions.addStretch()
        actions.addWidget(self._assessment_create)
        layout.addLayout(actions)
        return tab

    def _build_invitations_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Chọn vị trí, bài thi và ứng viên để gửi lời mời."))
        self._candidates_status = StatusBanner(tab)
        layout.addWidget(self._candidates_status)

        self._invite_position = QComboBox()
        self._invite_assessment = QComboBox()
        self._candidate_search = QLineEdit()
        self._candidate_search.setPlaceholderText("Tìm ứng viên theo tên hoặc email")
        self._candidate_search.returnPressed.connect(self.refresh_candidates)
        self._invite_candidate = QComboBox()
        form = QFormLayout()
        form.addRow("Vị trí *", self._invite_position)
        form.addRow("Bài thi *", self._invite_assessment)
        form.addRow("Lọc ứng viên", self._candidate_search)
        form.addRow("Ứng viên *", self._invite_candidate)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self._candidate_refresh = QPushButton("Tìm ứng viên")
        self._candidate_refresh.setStyleSheet(secondary_button_style(font_size=12))
        self._candidate_refresh.clicked.connect(self.refresh_candidates)
        self._send_invitation = QPushButton("Gửi lời mời")
        self._send_invitation.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._send_invitation.clicked.connect(self._invite_selected_candidate)
        actions.addStretch()
        actions.addWidget(self._candidate_refresh)
        actions.addWidget(self._send_invitation)
        layout.addLayout(actions)
        layout.addStretch()
        return tab

    def _build_results_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Kết quả các bài đánh giá"))
        controls.addStretch()
        self._results_refresh = QPushButton("Tải kết quả")
        self._results_refresh.setStyleSheet(secondary_button_style(font_size=12))
        self._results_refresh.clicked.connect(self.refresh_results)
        controls.addWidget(self._results_refresh)
        layout.addLayout(controls)
        self._results_status = StatusBanner(tab)
        layout.addWidget(self._results_status)
        self._results_table = self._make_table(
            ["Ứng viên", "Vị trí", "Bài thi", "Điểm", "Trạng thái", "Nộp lúc"]
        )
        layout.addWidget(self._results_table, stretch=1)
        return tab

    @staticmethod
    def _make_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _set_unavailable(self) -> None:
        self._status.set_status(
            "Recruitment Controller chưa được cung cấp. Không có dữ liệu tuyển "
            "dụng giả; các biểu mẫu và thao tác ghi đã bị khoá.",
            "unavailable",
        )
        for widget in (
            self._positions_table,
            self._position_search,
            self._positions_refresh,
            self._position_title,
            self._position_location,
            self._position_type,
            self._position_description,
            self._position_save,
            self._position_edit,
            self._position_clear,
            self._assessments_table,
            self._assessment_title,
            self._assessment_description,
            self._assessment_duration,
            self._question_prompt,
            *self._question_options,
            self._correct_option,
            self._question_add,
            self._questions_table,
            self._question_remove,
            self._assessment_refresh,
            self._assessment_create,
            self._invite_position,
            self._invite_assessment,
            self._candidate_search,
            self._invite_candidate,
            self._candidate_refresh,
            self._send_invitation,
            self._results_refresh,
            self._results_table,
        ):
            widget.setEnabled(False)

    def refresh(self) -> None:
        if self._controller is None:
            self._set_unavailable()
            return
        self._status.set_status("Đang tải dữ liệu tuyển dụng...", "loading")
        failures = [
            message
            for message in (
                self._load_positions(),
                self._load_assessments(),
                self._load_candidates(),
                self._load_results(),
            )
            if message
        ]
        if failures:
            self._status.set_status("; ".join(failures), "error")
        elif not any(
            (self._positions, self._assessments, self._candidates, self._results)
        ):
            self._status.set_status("Chưa có dữ liệu tuyển dụng.", "empty")
        else:
            self._status.set_status("Đã tải dữ liệu tuyển dụng.", "success")

    def _load_positions(self) -> str:
        result = self._controller.list_positions()
        if not result.success:
            self._positions = ()
            self._positions_table.setRowCount(0)
            self._position_edit.setEnabled(False)
            self._positions_status.set_status(
                result.message or "Không thể tải vị trí tuyển dụng.", "error"
            )
            return result.message or "Không thể tải vị trí tuyển dụng."
        self._positions = result.items
        self._render_positions()
        self._positions_status.set_status(
            "Chưa có vị trí tuyển dụng."
            if not self._positions
            else f"Đã tải {len(self._positions)} vị trí.",
            "empty" if not self._positions else "success",
        )
        return ""

    def _load_assessments(self) -> str:
        result = self._controller.list_assessments()
        if not result.success:
            self._assessments = ()
            self._assessments_table.setRowCount(0)
            self._assessments_status.set_status(
                result.message or "Không thể tải danh sách bài thi.", "error"
            )
            return result.message or "Không thể tải danh sách bài thi."
        self._assessments = result.items
        self._render_assessments()
        self._assessments_status.set_status(
            "Chưa có bài thi."
            if not self._assessments
            else f"Đã tải {len(self._assessments)} bài thi.",
            "empty" if not self._assessments else "success",
        )
        return ""

    def _load_candidates(self) -> str:
        result = self._controller.list_candidates(self._candidate_search.text())
        if not result.success:
            self._candidates = ()
            self._fill_combo(self._invite_candidate, ())
            self._candidates_status.set_status(
                result.message or "Không thể tìm ứng viên.", "error"
            )
            return result.message or "Không thể tìm ứng viên."
        self._candidates = result.items
        self._fill_combo(
            self._invite_candidate,
            ((candidate.full_name, candidate.id) for candidate in self._candidates),
        )
        self._candidates_status.set_status(
            "Không tìm thấy ứng viên."
            if not self._candidates
            else f"Đã tìm thấy {len(self._candidates)} ứng viên.",
            "empty" if not self._candidates else "success",
        )
        return ""

    def _load_results(self) -> str:
        result = self._controller.list_results()
        if not result.success:
            self._results = ()
            self._results_table.setRowCount(0)
            self._results_status.set_status(
                result.message or "Không thể tải kết quả đánh giá.", "error"
            )
            return result.message or "Không thể tải kết quả đánh giá."
        self._results = result.items
        self._render_results()
        self._results_status.set_status(
            "Chưa có kết quả đánh giá."
            if not self._results
            else f"Đã tải {len(self._results)} kết quả.",
            "empty" if not self._results else "success",
        )
        return ""

    def refresh_positions(self) -> None:
        if self._controller is None:
            return
        message = self._load_positions()
        self._status.set_status(
            message or (
                "Chưa có vị trí tuyển dụng."
                if not self._positions
                else f"Đã tải {len(self._positions)} vị trí."
            ),
            "error" if message else ("empty" if not self._positions else "success"),
        )

    def refresh_assessments(self) -> None:
        if self._controller is None:
            return
        message = self._load_assessments()
        self._status.set_status(
            message or (
                "Chưa có bài thi."
                if not self._assessments
                else f"Đã tải {len(self._assessments)} bài thi."
            ),
            "error" if message else ("empty" if not self._assessments else "success"),
        )

    def refresh_candidates(self) -> None:
        if self._controller is None:
            return
        message = self._load_candidates()
        self._status.set_status(
            message or (
                "Không tìm thấy ứng viên."
                if not self._candidates
                else f"Đã tìm thấy {len(self._candidates)} ứng viên."
            ),
            "error" if message else ("empty" if not self._candidates else "success"),
        )

    def refresh_results(self) -> None:
        if self._controller is None:
            return
        message = self._load_results()
        self._status.set_status(
            message or (
                "Chưa có kết quả đánh giá."
                if not self._results
                else f"Đã tải {len(self._results)} kết quả."
            ),
            "error" if message else ("empty" if not self._results else "success"),
        )

    def _render_positions(self) -> None:
        self._positions_table.setRowCount(len(self._positions))
        for row, position in enumerate(self._positions):
            values = (
                str(position.id),
                position.title,
                position.location,
                position.employment_type,
                position.status,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, position.id)
                self._positions_table.setItem(row, column, item)
        self._filter_positions(self._position_search.text())
        self._fill_combo(
            self._invite_position,
            ((position.title, position.id) for position in self._positions),
        )

    def _render_assessments(self) -> None:
        self._assessments_table.setRowCount(len(self._assessments))
        for row, assessment in enumerate(self._assessments):
            values = (
                str(assessment.id),
                assessment.title,
                str(assessment.duration_minutes),
                str(assessment.question_count),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, assessment.id)
                self._assessments_table.setItem(row, column, item)
        self._fill_combo(
            self._invite_assessment,
            ((item.title, item.id) for item in self._assessments),
        )

    def _render_results(self) -> None:
        self._results_table.setRowCount(len(self._results))
        for row, result in enumerate(self._results):
            score = (
                ""
                if result.score is None
                else f"{result.score:g}/{result.max_score:g}"
                if result.max_score is not None
                else f"{result.score:g}"
            )
            values = (
                result.candidate_name,
                result.position_title,
                result.assessment_title,
                score,
                result.status,
                result.submitted_at,
            )
            for column, value in enumerate(values):
                self._results_table.setItem(row, column, QTableWidgetItem(value))

    @staticmethod
    def _fill_combo(
        combo: QComboBox, values: Iterable[tuple[str, int]]
    ) -> None:
        selected = combo.currentData()
        combo.clear()
        for label, item_data in values:
            combo.addItem(label, item_data)
        if selected is not None:
            index = combo.findData(selected)
            if index >= 0:
                combo.setCurrentIndex(index)

    def _filter_positions(self, query: str) -> None:
        needle = query.strip().casefold()
        for row in range(self._positions_table.rowCount()):
            searchable = " ".join(
                self._positions_table.item(row, column).text()
                for column in range(1, self._positions_table.columnCount())
                if self._positions_table.item(row, column) is not None
            )
            self._positions_table.setRowHidden(
                row, needle not in searchable.casefold()
            )

    def _selected_position(self) -> Position | None:
        row = self._positions_table.currentRow()
        if row < 0:
            return None
        item = self._positions_table.item(row, 0)
        if item is None:
            return None
        position_id = item.data(Qt.ItemDataRole.UserRole)
        return next((p for p in self._positions if p.id == position_id), None)

    def _position_selection_changed(self) -> None:
        self._position_edit.setEnabled(self._selected_position() is not None)

    def _save_position(self) -> None:
        if self._controller is None:
            return
        title = self._position_title.text().strip()
        location = self._position_location.text().strip()
        if not title or not location:
            self._status.set_status("Tên vị trí và địa điểm là bắt buộc.", "error")
            return
        args = (
            title,
            self._position_description.toPlainText().strip(),
            location,
            self._position_type.currentData(),
        )
        self._status.set_status("Đang lưu vị trí...", "loading")
        if self._editing_position_id is None:
            result = self._controller.create_position(*args)
        else:
            result = self._controller.update_position(
                self._editing_position_id, *args
            )
        if not result.success:
            self._status.set_status(
                result.message or "Không thể lưu vị trí tuyển dụng.", "error"
            )
            return
        self._clear_position_form()
        self.refresh_positions()

    def _edit_position(self) -> None:
        position = self._selected_position()
        if position is None:
            self._status.set_status("Chọn vị trí cần cập nhật.", "error")
            return
        self._editing_position_id = position.id
        self._position_title.setText(position.title)
        self._position_location.setText(position.location)
        self._position_description.setPlainText(position.description)
        index = self._position_type.findData(position.employment_type)
        if index >= 0:
            self._position_type.setCurrentIndex(index)
        self._position_save.setText("Lưu thay đổi")
        self._tabs.setCurrentWidget(self._positions_tab)

    def _clear_position_form(self) -> None:
        self._editing_position_id = None
        self._position_title.clear()
        self._position_location.clear()
        self._position_description.clear()
        self._position_type.setCurrentIndex(0)
        self._position_save.setText("Tạo vị trí")
        self._positions_table.clearSelection()

    def _add_question(self) -> None:
        if self._controller is None:
            return
        prompt = self._question_prompt.text().strip()
        entered = [option.text().strip() for option in self._question_options]
        last_filled = max(
            (index for index, value in enumerate(entered) if value), default=-1
        )
        if not prompt:
            self._status.set_status("Nội dung câu hỏi không được để trống.", "error")
            return
        if last_filled < 1 or any(not value for value in entered[: last_filled + 1]):
            self._status.set_status(
                "Mỗi câu hỏi cần ít nhất hai phương án liên tiếp.", "error"
            )
            return
        correct_index = self._correct_option.currentData()
        if correct_index > last_filled:
            self._status.set_status(
                "Đáp án đúng phải trùng với một phương án đã nhập.", "error"
            )
            return
        draft = QuestionDraft(
            prompt=prompt,
            options=tuple(entered[: last_filled + 1]),
            correct_option_index=correct_index,
        )
        self._question_drafts.append(draft)
        self._render_questions()
        self._question_prompt.clear()
        for option in self._question_options:
            option.clear()
        self._correct_option.setCurrentIndex(0)
        self._status.set_status(
            f"Đã thêm câu hỏi ({len(self._question_drafts)}).", "success"
        )

    def _render_questions(self) -> None:
        self._questions_table.setRowCount(len(self._question_drafts))
        for row, question in enumerate(self._question_drafts):
            values = (
                question.prompt,
                " | ".join(question.options),
                chr(ord("A") + question.correct_option_index),
            )
            for column, value in enumerate(values):
                self._questions_table.setItem(row, column, QTableWidgetItem(value))

    def _remove_question(self) -> None:
        row = self._questions_table.currentRow()
        if row < 0 or row >= len(self._question_drafts):
            self._status.set_status("Chọn câu hỏi cần xoá.", "error")
            return
        self._question_drafts.pop(row)
        self._render_questions()

    def _create_assessment(self) -> None:
        if self._controller is None:
            return
        title = self._assessment_title.text().strip()
        if not title:
            self._status.set_status("Tên bài thi không được để trống.", "error")
            return
        if not self._question_drafts:
            self._status.set_status("Thêm ít nhất một câu hỏi trước khi lưu.", "error")
            return
        self._status.set_status("Đang tạo bài thi...", "loading")
        result = self._controller.create_assessment(
            title,
            self._assessment_description.toPlainText().strip(),
            self._assessment_duration.value(),
            tuple(self._question_drafts),
        )
        if not result.success:
            self._status.set_status(result.message or "Không thể tạo bài thi.", "error")
            return
        self._assessment_title.clear()
        self._assessment_description.clear()
        self._question_drafts.clear()
        self._render_questions()
        self.refresh_assessments()

    def _invite_selected_candidate(self) -> None:
        if self._controller is None:
            return
        position_id = self._invite_position.currentData()
        assessment_id = self._invite_assessment.currentData()
        candidate_id = self._invite_candidate.currentData()
        if None in (position_id, assessment_id, candidate_id):
            self._status.set_status(
                "Chọn vị trí, bài thi và ứng viên trước khi gửi.", "error"
            )
            return
        self._status.set_status("Đang gửi lời mời...", "loading")
        result = self._controller.send_invitation(
            position_id, assessment_id, candidate_id
        )
        if not result.success:
            self._status.set_status(result.message or "Không thể gửi lời mời.", "error")
            return
        self._status.set_status("Đã gửi lời mời ứng viên.", "success")
        self.refresh_results()

    def _handle_back(self) -> None:
        if self._on_back_cb is not None:
            self._on_back_cb()
