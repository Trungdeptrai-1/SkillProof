"""Candidate invitations, multiple-choice exam flow, and results."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.utils.constants import (
    COLOR_NAVY_DARK,
    COLOR_OFF_WHITE,
    COLOR_TEXT_MUTED,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from app.utils.styles import primary_button_style, secondary_button_style
from client.components.status_banner import StatusBanner
from client.views.recruitment_contracts import (
    CandidateAssessmentController,
    CandidateInvitation,
    CandidateResult,
    ExamDetails,
    ExamQuestion,
)


class CandidateAssessmentScreen(QWidget):
    """Candidate exam workflow; submission and answers always go through Controller."""

    def __init__(
        self,
        controller: CandidateAssessmentController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._controller = controller
        self._on_back_cb: Callable[[], None] | None = None
        self._invitations: tuple[CandidateInvitation, ...] = ()
        self._active_invitation: CandidateInvitation | None = None
        self._exam: ExamDetails | None = None
        self._question_index = 0
        self._saved_answers: dict[int, int] = {}
        self._draft_answers: dict[int, int] = {}
        self._submitted_invitation_ids: set[int] = set()
        self._submission_in_progress = False
        self._submitted = False
        self._rendering_question = False
        self._option_buttons: dict[int, QRadioButton] = {}
        self._setup_ui()
        if self._controller is None:
            self._set_unavailable()
        else:
            self.refresh_invitations()

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
        title = QLabel("Lời mời và bài thi")
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
        self._invitations_tab = self._build_invitations_tab()
        self._exam_tab = self._build_exam_tab()
        self._result_tab = self._build_result_tab()
        self._tabs.addTab(self._invitations_tab, "Lời mời")
        self._tabs.addTab(self._exam_tab, "Làm bài")
        self._tabs.addTab(self._result_tab, "Kết quả")
        layout.addWidget(self._tabs, stretch=1)

    def _build_invitations_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        intro = QLabel("Các bài thi được doanh nghiệp gửi cho bạn.")
        intro.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        controls.addWidget(intro)
        controls.addStretch()
        self._invitations_refresh = QPushButton("Tải lời mời")
        self._invitations_refresh.setStyleSheet(secondary_button_style(font_size=12))
        self._invitations_refresh.clicked.connect(self.refresh_invitations)
        controls.addWidget(self._invitations_refresh)
        layout.addLayout(controls)

        self._invitations_table = self._make_table(
            ["Doanh nghiệp", "Vị trí", "Bài thi", "Thời lượng", "Trạng thái"]
        )
        self._invitations_table.itemSelectionChanged.connect(
            self._invitation_selection_changed
        )
        layout.addWidget(self._invitations_table, stretch=1)

        actions = QHBoxLayout()
        self._start_exam_button = QPushButton("Mở bài thi")
        self._start_exam_button.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._start_exam_button.clicked.connect(self._open_selected_exam)
        self._view_result_button = QPushButton("Xem kết quả")
        self._view_result_button.setStyleSheet(secondary_button_style(font_size=12))
        self._view_result_button.clicked.connect(self._view_selected_result)
        actions.addStretch()
        actions.addWidget(self._view_result_button)
        actions.addWidget(self._start_exam_button)
        layout.addLayout(actions)
        self._start_exam_button.setEnabled(False)
        self._view_result_button.setEnabled(False)
        return tab

    def _build_exam_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self._exam_title = QLabel("Chọn lời mời để tải bài thi.")
        self._exam_title.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:19px;font-weight:700;"
        )
        layout.addWidget(self._exam_title)
        self._exam_meta = QLabel("")
        self._exam_meta.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        layout.addWidget(self._exam_meta)

        self._progress_label = QLabel("Chưa có câu trả lời được lưu.")
        layout.addWidget(self._progress_label)
        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFormat("%v/%m đáp án đã lưu")
        layout.addWidget(self._progress)

        question_header = QHBoxLayout()
        self._question_counter = QLabel("")
        self._question_counter.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:15px;font-weight:600;"
        )
        question_header.addWidget(self._question_counter)
        question_header.addStretch()
        self._previous_question = QPushButton("← Câu trước")
        self._previous_question.setStyleSheet(secondary_button_style(font_size=12))
        self._previous_question.clicked.connect(
            lambda: self._show_question(self._question_index - 1)
        )
        self._next_question = QPushButton("Câu tiếp →")
        self._next_question.setStyleSheet(secondary_button_style(font_size=12))
        self._next_question.clicked.connect(
            lambda: self._show_question(self._question_index + 1)
        )
        question_header.addWidget(self._previous_question)
        question_header.addWidget(self._next_question)
        layout.addLayout(question_header)

        self._question_prompt = QLabel("")
        self._question_prompt.setWordWrap(True)
        self._question_prompt.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:16px;background:white;"
            "border:1px solid #DCE3EB;border-radius:8px;padding:16px;"
        )
        layout.addWidget(self._question_prompt)

        self._options_group = QButtonGroup(self)
        self._options_group.setExclusive(True)
        self._options_layout = QVBoxLayout()
        self._options_layout.setSpacing(10)
        layout.addLayout(self._options_layout)
        layout.addStretch()

        actions = QHBoxLayout()
        self._save_answer_button = QPushButton("Lưu đáp án")
        self._save_answer_button.setStyleSheet(secondary_button_style(font_size=12))
        self._save_answer_button.clicked.connect(self._save_current_answer)
        self._submit_exam_button = QPushButton("Nộp bài")
        self._submit_exam_button.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._submit_exam_button.clicked.connect(self._submit_exam)
        actions.addStretch()
        actions.addWidget(self._save_answer_button)
        actions.addWidget(self._submit_exam_button)
        layout.addLayout(actions)
        self._set_exam_controls_enabled(False)
        return tab

    def _build_result_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self._result_title = QLabel("Chưa chọn kết quả.")
        self._result_title.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:19px;font-weight:700;"
        )
        self._result_score = QLabel("")
        self._result_status = QLabel("")
        self._result_date = QLabel("")
        for label in (self._result_title, self._result_score, self._result_status, self._result_date):
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addStretch()
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
            "Candidate Assessment Controller chưa được cung cấp. Lời mời và "
            "kết quả không được giả lập; tải, lưu đáp án và nộp bài đã bị khoá.",
            "unavailable",
        )
        for widget in (
            self._invitations_refresh,
            self._invitations_table,
            self._start_exam_button,
            self._view_result_button,
            self._save_answer_button,
            self._submit_exam_button,
        ):
            widget.setEnabled(False)

    def refresh_invitations(self) -> str | None:
        if self._controller is None:
            self._set_unavailable()
            return self._status.text()
        self._status.set_status("Đang tải lời mời...", "loading")
        result = self._controller.list_invitations()
        if not result.success:
            self._invitations = ()
            self._invitations_table.setRowCount(0)
            self._start_exam_button.setEnabled(False)
            self._view_result_button.setEnabled(False)
            self._status.set_status(
                result.message or "Không thể tải lời mời làm bài.", "error"
            )
            return result.message or "Không thể tải lời mời làm bài."
        self._invitations = tuple(
            replace(invitation, status="completed")
            if invitation.id in self._submitted_invitation_ids
            else invitation
            for invitation in result.items
        )
        self._render_invitations()
        if not self._invitations:
            self._status.set_status("Bạn chưa có lời mời làm bài.", "empty")
        else:
            self._status.set_status(
                f"Đã tải {len(self._invitations)} lời mời.", "success"
            )
        return None

    def _render_invitations(self) -> None:
        self._invitations_table.setRowCount(len(self._invitations))
        for row, invitation in enumerate(self._invitations):
            values = (
                invitation.company_name,
                invitation.position_title,
                invitation.assessment_title,
                f"{invitation.duration_minutes} phút",
                invitation.status,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, invitation.id)
                self._invitations_table.setItem(row, column, item)
        self._invitation_selection_changed()

    def _selected_invitation(self) -> CandidateInvitation | None:
        row = self._invitations_table.currentRow()
        if row < 0:
            return None
        item = self._invitations_table.item(row, 0)
        if item is None:
            return None
        invitation_id = item.data(Qt.ItemDataRole.UserRole)
        return next((i for i in self._invitations if i.id == invitation_id), None)

    def _invitation_selection_changed(self) -> None:
        invitation = self._selected_invitation()
        self._start_exam_button.setEnabled(
            self._controller is not None
            and invitation is not None
            and invitation.id not in self._submitted_invitation_ids
            and invitation.status in ("scheduled", "in_progress")
        )
        self._view_result_button.setEnabled(
            self._controller is not None
            and invitation is not None
            and invitation.status == "completed"
        )

    def _open_selected_exam(self) -> None:
        invitation = self._selected_invitation()
        if self._controller is None or invitation is None:
            self._status.set_status("Chọn lời mời hợp lệ trước.", "error")
            return
        if invitation.id in self._submitted_invitation_ids:
            self._load_result(invitation.id)
            return
        if invitation.status not in ("scheduled", "in_progress"):
            self._status.set_status("Lời mời này không thể mở bài thi.", "error")
            return
        self._active_invitation = None
        self._exam = None
        self._set_exam_controls_enabled(False)
        self._exam_title.setText("Đang tải bài thi...")
        self._question_prompt.clear()
        self._question_counter.clear()
        self._clear_options()
        self._status.set_status("Đang tải bài thi...", "loading")
        response = self._controller.get_exam(invitation.id)
        if not response.success or response.exam is None:
            self._status.set_status(
                response.message or "Không thể tải nội dung bài thi.", "error"
            )
            return
        exam = response.exam
        if exam.invitation_id != invitation.id:
            self._status.set_status(
                "Bài thi trả về không khớp với lời mời đã chọn.", "error"
            )
            return
        if exam.duration_minutes <= 0:
            self._status.set_status(
                "Thời lượng bài thi không hợp lệ.", "error"
            )
            return
        if not exam.questions:
            self._status.set_status("Bài thi chưa có câu hỏi.", "empty")
            return
        question_ids = [question.id for question in exam.questions]
        if len(question_ids) != len(set(question_ids)) or any(
            not question.prompt.strip()
            or len(question.options) < 2
            or any(not option.text.strip() for option in question.options)
            or len({option.id for option in question.options})
            != len(question.options)
            for question in exam.questions
        ):
            self._status.set_status(
                "Bài thi có câu hỏi hoặc phương án trả lời không hợp lệ.", "error"
            )
            return
        self._load_exam(invitation, exam)

    def _load_exam(
        self, invitation: CandidateInvitation, exam: ExamDetails
    ) -> None:
        self._active_invitation = invitation
        self._exam = exam
        self._question_index = 0
        invalid_saved_answer = False
        self._saved_answers = {}
        for question in exam.questions:
            option_ids = {option.id for option in question.options}
            if question.selected_option_id is None:
                continue
            if question.selected_option_id not in option_ids:
                invalid_saved_answer = True
                continue
            self._saved_answers[question.id] = question.selected_option_id
        self._draft_answers = dict(self._saved_answers)
        self._submitted = (
            invitation.status == "completed"
            or invitation.id in self._submitted_invitation_ids
        )
        self._submission_in_progress = False
        self._exam_title.setText(exam.title)
        self._exam_meta.setText(
            f"{exam.duration_minutes} phút · {len(exam.questions)} câu hỏi"
        )
        if not exam.questions:
            self._question_prompt.setText("Bài thi chưa có câu hỏi.")
            self._question_counter.clear()
            self._set_exam_controls_enabled(False)
            self._status.set_status("Bài thi chưa có câu hỏi.", "empty")
            self._tabs.setCurrentWidget(self._exam_tab)
            return
        self._set_exam_controls_enabled(not self._submitted)
        self._show_question(0)
        self._status.set_status(
            "Một đáp án đã lưu không còn hợp lệ; vui lòng chọn lại."
            if invalid_saved_answer
            else "Đã tải bài thi.",
            "error" if invalid_saved_answer else "success",
        )
        self._tabs.setCurrentWidget(self._exam_tab)

    def _show_question(self, index: int) -> None:
        if self._exam is None or not self._exam.questions:
            return
        if index < 0 or index >= len(self._exam.questions):
            return
        self._question_index = index
        question = self._exam.questions[index]
        self._question_counter.setText(
            f"Câu {index + 1} / {len(self._exam.questions)}"
        )
        self._question_prompt.setText(question.prompt)
        self._previous_question.setEnabled(index > 0 and not self._submitted)
        self._next_question.setEnabled(
            index < len(self._exam.questions) - 1 and not self._submitted
        )
        self._render_options(question)
        self._update_progress()

    def _render_options(self, question: ExamQuestion) -> None:
        self._clear_options()
        self._rendering_question = True
        selected_id = self._draft_answers.get(question.id)
        for option in question.options:
            button = QRadioButton(option.text)
            button.setProperty("option_id", option.id)
            button.setEnabled(not self._submitted)
            self._options_group.addButton(button, option.id)
            self._options_layout.addWidget(button)
            self._option_buttons[option.id] = button
            button.toggled.connect(
                lambda checked, qid=question.id, oid=option.id: self._option_changed(
                    qid, oid, checked
                )
            )
            if selected_id == option.id:
                button.setChecked(True)
        self._rendering_question = False

    def _clear_options(self) -> None:
        self._rendering_question = True
        for button in self._option_buttons.values():
            self._options_group.removeButton(button)
            button.deleteLater()
        self._option_buttons.clear()
        while self._options_layout.count():
            item = self._options_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._rendering_question = False

    def _option_changed(self, question_id: int, option_id: int, checked: bool) -> None:
        if checked and not self._rendering_question and not self._submitted:
            self._draft_answers[question_id] = option_id
            self._update_progress()
            self._status.set_status(
                "Đáp án đã thay đổi; hãy lưu trước khi nộp bài.", "info"
            )

    def _save_current_answer(self) -> None:
        if (
            self._controller is None
            or self._exam is None
            or self._active_invitation is None
            or self._submitted
            or self._submission_in_progress
        ):
            return
        question = self._exam.questions[self._question_index]
        option_id = self._options_group.checkedId()
        if option_id < 0:
            self._status.set_status("Chọn một đáp án trước khi lưu.", "error")
            return
        self._status.set_status("Đang lưu đáp án...", "loading")
        result = self._controller.save_answer(
            self._active_invitation.id, question.id, option_id
        )
        if not result.success:
            self._status.set_status(
                result.message or "Không thể lưu đáp án.", "error"
            )
            return
        self._draft_answers[question.id] = option_id
        self._saved_answers[question.id] = option_id
        self._update_progress()
        self._status.set_status("Đáp án đã được lưu.", "success")

    def _update_progress(self) -> None:
        question_count = len(self._exam.questions) if self._exam else 0
        saved_count = sum(
            1
            for question_id, option_id in self._saved_answers.items()
            if self._draft_answers.get(question_id) == option_id
        )
        self._progress.setRange(0, max(1, question_count))
        self._progress.setValue(saved_count)
        self._progress_label.setText(
            f"Đã lưu {saved_count} / {question_count} đáp án"
            + (
                " · Có đáp án chưa lưu"
                if any(
                    self._draft_answers.get(question.id)
                    != self._saved_answers.get(question.id)
                    for question in self._exam.questions
                    if question.id in self._draft_answers
                )
                else ""
            )
        )

    def _set_exam_controls_enabled(self, enabled: bool) -> None:
        self._save_answer_button.setEnabled(enabled)
        self._submit_exam_button.setEnabled(enabled)
        self._previous_question.setEnabled(False)
        self._next_question.setEnabled(False)

    def _submit_exam(self) -> None:
        if (
            self._controller is None
            or self._active_invitation is None
            or self._exam is None
            or self._submitted
            or self._submission_in_progress
        ):
            return
        if any(
            self._draft_answers.get(question.id)
            != self._saved_answers.get(question.id)
            for question in self._exam.questions
            if question.id in self._draft_answers
        ):
            self._status.set_status(
                "Lưu các đáp án đã chọn trước khi nộp bài.", "error"
            )
            return
        answer = QMessageBox.question(
            self,
            "Xác nhận nộp bài",
            "Bạn chắc chắn muốn nộp bài? Sau khi nộp, đáp án sẽ không thể thay đổi.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._submission_in_progress = True
        self._set_exam_controls_enabled(False)
        self._status.set_status("Đang nộp bài...", "loading")
        response = self._controller.submit_exam(self._active_invitation.id)
        self._submission_in_progress = False
        if not response.success:
            self._status.set_status(
                response.message or "Không thể nộp bài.", "error"
            )
            self._set_exam_controls_enabled(True)
            self._show_question(self._question_index)
            return

        self._submitted = True
        self._submitted_invitation_ids.add(self._active_invitation.id)
        self._set_exam_controls_enabled(False)
        for button in self._option_buttons.values():
            button.setEnabled(False)
        invitation_refresh_error = self.refresh_invitations()
        if (
            response.result is not None
            and response.result.invitation_id == self._active_invitation.id
        ):
            self._display_result(response.result)
        elif response.result is not None:
            self._status.set_status(
                "Kết quả trả về không khớp với lời mời đã nộp.", "error"
            )
        else:
            self._load_result(self._active_invitation.id)
        if invitation_refresh_error:
            self._status.set_status(
                f"{self._status.text()} Lời mời chưa thể tải lại: "
                f"{invitation_refresh_error}",
                "error",
            )
        self._tabs.setCurrentWidget(self._result_tab)

    def _view_selected_result(self) -> None:
        invitation = self._selected_invitation()
        if invitation is None or (
            invitation.status != "completed"
            and invitation.id not in self._submitted_invitation_ids
        ):
            self._status.set_status("Chỉ xem được kết quả bài đã hoàn thành.", "error")
            return
        self._load_result(invitation.id)

    def _load_result(self, invitation_id: int) -> None:
        if self._controller is None:
            return
        self._status.set_status("Đang tải kết quả...", "loading")
        response = self._controller.get_result(invitation_id)
        if not response.success or response.result is None:
            self._status.set_status(
                response.message or "Không thể tải kết quả bài thi.", "error"
            )
            return
        if response.result.invitation_id != invitation_id:
            self._status.set_status(
                "Kết quả trả về không khớp với lời mời đã chọn.", "error"
            )
            return
        self._display_result(response.result)
        self._tabs.setCurrentWidget(self._result_tab)

    def _display_result(self, result: CandidateResult) -> None:
        invitation = next(
            (item for item in self._invitations if item.id == result.invitation_id),
            self._active_invitation,
        )
        self._result_title.setText(
            invitation.assessment_title if invitation else "Kết quả bài thi"
        )
        if result.score is None:
            score_text = "Chưa có điểm"
        elif result.max_score is None:
            score_text = f"Điểm: {result.score:g}"
        else:
            score_text = f"Điểm: {result.score:g} / {result.max_score:g}"
        self._result_score.setText(score_text)
        self._result_status.setText(f"Trạng thái: {result.status}")
        self._result_date.setText(
            f"Hoàn thành: {result.submitted_at}" if result.submitted_at else ""
        )
        self._status.set_status(result.message or "Đã tải kết quả.", "success")

    def _handle_back(self) -> None:
        if self._on_back_cb is not None:
            self._on_back_cb()
