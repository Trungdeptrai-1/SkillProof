"""Two-way job marketplace screens. Data always comes from authenticated Controller."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDateTime, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QTabWidget, QMessageBox, QCheckBox, QAbstractItemView, QDateTimeEdit,
    QListWidget, QListWidgetItem, QFrame, QSizePolicy,
)
from server.controllers.marketplace_controller import MarketplaceController
from server.controllers.direct_invitation_controller import DirectInvitationController


STYLE = """
QWidget#MarketplaceRoot { background: #F4F7FB; color: #172B4D; font-family: 'Segoe UI'; }
QLabel { background: transparent; border: none; }
QCheckBox { background: transparent; spacing: 10px; color: #334155; }
QLabel#PageTitle { font-size: 26px; font-weight: 700; color: #12233F; }
QLabel#SectionTitle { font-size: 15px; font-weight: 650; color: #172B4D; }
QLabel#Status { color: #475569; font-size: 12px; }
QLineEdit, QTextEdit, QComboBox, QDateTimeEdit { background: white; border: 1px solid #D8E1ED;
    border-radius: 9px; padding: 10px; font-size: 13px; color: #172B4D; selection-background-color: #D9E9FF; }
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateTimeEdit:focus { border: 1px solid #3185D9; }
QPushButton { background: white; color: #1E4D7B; border: 1px solid #D8E1ED;
    border-radius: 9px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #EFF6FF; }
QPushButton#Primary { background: #2563EB; color: white; border: none; }
QPushButton#Primary:hover { background: #1D4ED8; }
QTableWidget { background: white; alternate-background-color: #F7F9FC;
    border: 1px solid #DCE5F1; border-radius: 10px; gridline-color: #EDF1F7;
    color: #172B4D; selection-background-color: #E3F0FF; selection-color: #102A46; }
QHeaderView::section { background: #EFF4FA; color: #435570;
    padding: 12px; border: none; border-bottom: 1px solid #DAE3EE; font-weight: 600; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: transparent; color: #64748B; padding: 13px 18px;
    border: none; border-bottom: 2px solid transparent; }
QTabBar::tab:hover { color: #1E4D7B; }
QTabBar::tab:selected { color: #1D4ED8; border-bottom: 2px solid #3185D9; font-weight: 700; }
QListWidget#JobCards { background: transparent; border: none; outline: none; }
QListWidget#JobCards::item { background: white; border: 1px solid #DCE5F1;
    border-radius: 12px; padding: 13px 15px; margin-bottom: 9px; color: #172B4D; }
QListWidget#JobCards::item:hover { border: 1px solid #93B9EE; background: #F6FAFF; }
QListWidget#JobCards::item:selected { background: #EAF3FF; color: #102D4D;
    border: 2px solid #3284D7; }
QFrame#JobDetailPanel { background: white; border: 1px solid #DCE5F1; border-radius: 14px; }
QLabel#JobDetailTitle { font-size: 17px; font-weight: 700; color: #102C4D; }
"""


def button(label: str, callback, primary: bool = False) -> QPushButton:
    widget = QPushButton(label)
    widget.setMinimumHeight(37)
    if primary:
        widget.setObjectName("Primary")
    widget.clicked.connect(callback)
    return widget


def table(columns: list[str]) -> QTableWidget:
    widget = QTableWidget(0, len(columns))
    widget.setHorizontalHeaderLabels(columns)
    widget.setAlternatingRowColors(True)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.verticalHeader().setVisible(False)
    widget.verticalHeader().setDefaultSectionSize(46)
    widget.setShowGrid(False)
    widget.setWordWrap(False)
    if columns and columns[0] in ("ID", "Mã"):
        widget.setColumnHidden(0, True)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return widget


def populate(widget: QTableWidget, rows: list[dict], columns: list[str]) -> None:
    widget.setRowCount(len(rows))
    for row_index, item in enumerate(rows):
        for col_index, field in enumerate(columns):
            raw_value = item.get(field)
            display = {
                "published": "Đang tuyển",
                "draft": "Bản nháp",
                "closed": "Đã đóng",
                "applied": "Đã ứng tuyển",
                "reviewing": "Đang xem xét",
                "shortlisted": "Vào danh sách chọn",
                "assessment": "Đang đánh giá",
                "interview": "Đang phỏng vấn",
                "rejected": "Đã từ chối",
                "withdrawn": "Đã rút đơn",
                "offered": "Đã gửi đề nghị",
                "accepted": "Đã chấp nhận",
                "declined": "Đã từ chối",
            }.get(str(raw_value), str(raw_value) if raw_value is not None else "")
            cell = QTableWidgetItem(display)
            if field in ("status", "offer_response"):
                cell.setData(Qt.ItemDataRole.UserRole + 1, raw_value)
            if col_index == 0:
                cell.setData(Qt.ItemDataRole.UserRole, int(item["id"]))
            widget.setItem(row_index, col_index, cell)


def selected_id(widget: QTableWidget) -> int | None:
    row = widget.currentRow()
    item = widget.item(row, 0) if row >= 0 else None
    return item.data(Qt.ItemDataRole.UserRole) if item is not None else None


class MarketplaceScreen(QWidget):
    """Candidate discovery and applications, or Company applicant management."""

    def __init__(
        self, role: str, controller: MarketplaceController | None = None,
        parent: QWidget | None = None,
        invitation_controller: DirectInvitationController | None = None,
    ) -> None:
        super().__init__(parent)
        if role not in ("candidate", "company"):
            raise ValueError("Marketplace requires candidate/company role")
        self.setObjectName("MarketplaceRoot")
        self.setStyleSheet(STYLE)
        self.role = role
        self.controller = controller or MarketplaceController()
        self.invitation_controller = invitation_controller or DirectInvitationController()
        self.on_back = None
        self._jobs: list[dict] = []
        self._positions: list[dict] = []
        self._setup()
        self.refresh()

    def _setup(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 30, 36, 24)
        outer.setSpacing(20)
        header = QHBoxLayout()
        title = QLabel(
            "Khám phá cơ hội việc làm" if self.role == "candidate"
            else "Quản lý hồ sơ ứng tuyển"
        )
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(button("Quay lại tổng quan", self._back))
        outer.addLayout(header)

        self.status = QLabel("")
        self.status.setObjectName("Status")
        self.status.setWordWrap(True)

        self.tabs = QTabWidget()
        if self.role == "candidate":
            self._candidate_tabs()
        else:
            self._company_tabs()
        outer.addWidget(self.tabs, 1)
        outer.addWidget(self.status)

    def _back(self) -> None:
        if callable(self.on_back):
            self.on_back()

    def _candidate_tabs(self) -> None:
        explore = QWidget()
        layout = QVBoxLayout(explore)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm theo công việc, công ty hoặc kỹ năng")
        self.location = QLineEdit()
        self.location.setPlaceholderText("Địa điểm")
        filters.addWidget(self.search, 3)
        filters.addWidget(self.location, 2)
        filters.addWidget(button("Tìm kiếm", self._load_jobs, True))
        layout.addLayout(filters)

        # Keep the canonical selection table for controller logic and existing tests.
        # The user-facing browse experience is a two-column job board instead.
        self.jobs_table = table(["ID", "Vị trí", "Công ty", "Địa điểm", "Đã lưu", "Đã ứng tuyển"])
        self.jobs_table.itemSelectionChanged.connect(self._job_selected)

        columns = QHBoxLayout()
        columns.setSpacing(18)
        cards_panel = QWidget()
        cards_layout = QVBoxLayout(cards_panel)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)
        cards_title = QLabel("Cơ hội tuyển dụng")
        cards_title.setObjectName("SectionTitle")
        cards_layout.addWidget(cards_title)
        self.job_cards = QListWidget()
        self.job_cards.setObjectName("JobCards")
        self.job_cards.setSpacing(4)
        self.job_cards.setWordWrap(True)
        self.job_cards.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.job_cards.itemSelectionChanged.connect(self._card_selected)
        cards_layout.addWidget(self.job_cards, 1)
        columns.addWidget(cards_panel, 4)

        details_panel = QFrame()
        details_panel.setObjectName("JobDetailPanel")
        detail_layout = QVBoxLayout(details_panel)
        detail_layout.setContentsMargins(22, 20, 22, 20)
        detail_layout.setSpacing(12)
        self.job_heading = QLabel("Chọn một công việc")
        self.job_heading.setObjectName("JobDetailTitle")
        self.job_heading.setWordWrap(True)
        detail_layout.addWidget(self.job_heading)
        self.job_subtitle = QLabel("Thông tin công ty và vị trí sẽ hiển thị ở đây.")
        self.job_subtitle.setObjectName("Status")
        self.job_subtitle.setWordWrap(True)
        detail_layout.addWidget(self.job_subtitle)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Chọn một vị trí để xem mô tả và yêu cầu.")
        self.details.setMinimumHeight(160)
        detail_layout.addWidget(self.details, 1)
        cover_label = QLabel("Thư giới thiệu (không bắt buộc)")
        cover_label.setObjectName("SectionTitle")
        detail_layout.addWidget(cover_label)
        self.cover_letter = QTextEdit()
        self.cover_letter.setPlaceholderText("Giới thiệu ngắn về kinh nghiệm và lý do bạn phù hợp (tối đa 4000 ký tự)")
        self.cover_letter.setMaximumHeight(105)
        detail_layout.addWidget(self.cover_letter)
        actions = QHBoxLayout()
        actions.addWidget(button("Lưu", self._save_selected))
        actions.addWidget(button("Bỏ lưu", self._unsave_selected))
        actions.addStretch()
        actions.addWidget(button("Ứng tuyển ngay", self._apply_selected, True))
        detail_layout.addLayout(actions)
        columns.addWidget(details_panel, 6)
        layout.addLayout(columns, 1)
        self.tabs.addTab(explore, "Khám phá việc làm")

        mine = QWidget()
        mine_layout = QVBoxLayout(mine)
        mine_layout.addWidget(button("Làm mới đơn ứng tuyển", self._load_applications))
        self.apps_table = table(["ID", "Vị trí", "Công ty", "Trạng thái", "Ngày ứng tuyển", "Phản hồi tuyển dụng", "Trả lời đề nghị"])
        mine_layout.addWidget(self.apps_table)
        offer_actions = QHBoxLayout()
        offer_actions.addWidget(button("Rút đơn đã chọn", self._withdraw_selected))
        offer_actions.addStretch()
        offer_actions.addWidget(button("Chấp nhận đề nghị", lambda: self._respond_selected_offer(True), True))
        offer_actions.addWidget(button("Từ chối đề nghị", lambda: self._respond_selected_offer(False)))
        mine_layout.addLayout(offer_actions)
        self.tabs.addTab(mine, "Đơn ứng tuyển của tôi")

        saved = QWidget()
        saved_layout = QVBoxLayout(saved)
        saved_layout.addWidget(button("Làm mới việc làm đã lưu", self._load_saved_jobs))
        self.saved_table = table(["ID", "Vị trí", "Công ty", "Địa điểm", "Trạng thái", "Đã ứng tuyển"])
        saved_layout.addWidget(self.saved_table, 1)
        saved_layout.addWidget(button("Bỏ lưu việc làm đã chọn", self._unsave_saved_job))
        self.tabs.addTab(saved, "Việc làm đã lưu")

        privacy = QWidget()
        privacy_layout = QVBoxLayout(privacy)
        note = QLabel(
            "Mặc định hồ sơ của bạn không xuất hiện trong kết quả tìm kiếm ứng viên. "
            "Chỉ bật nếu bạn muốn doanh nghiệp xem thông tin giới thiệu công khai. "
            "Email và đường dẫn CV không được hiển thị trong danh sách tìm kiếm."
        )
        note.setWordWrap(True)
        privacy_layout.addWidget(note)
        self.visibility = QCheckBox("Cho phép doanh nghiệp tìm thấy hồ sơ giới thiệu của tôi")
        privacy_layout.addWidget(self.visibility)
        privacy_layout.addWidget(button("Lưu cài đặt hiển thị", self._set_visibility, True))
        privacy_layout.addStretch()
        self.tabs.addTab(privacy, "Quyền riêng tư")

        invites = QWidget()
        invites_layout = QVBoxLayout(invites)
        invites_layout.addWidget(button("Làm mới lời mời", self._load_received_invites))
        self.received_table = table(["ID", "Vị trí", "Công ty", "Lời nhắn", "Trạng thái", "Ngày gửi"])
        invites_layout.addWidget(self.received_table, 1)
        answer_buttons = QHBoxLayout()
        answer_buttons.addWidget(button("Chấp nhận lời mời", lambda: self._answer_invite(True), True))
        answer_buttons.addWidget(button("Từ chối lời mời", lambda: self._answer_invite(False)))
        answer_buttons.addStretch()
        invites_layout.addLayout(answer_buttons)
        self.tabs.addTab(invites, "Lời mời tuyển dụng")

    def _company_tabs(self) -> None:
        applicants = QWidget()
        layout = QVBoxLayout(applicants)
        header = QHBoxLayout()
        header.addWidget(QLabel("Vị trí đang tuyển:"))
        self.positions = QComboBox()
        header.addWidget(self.positions, 1)
        header.addWidget(button("Làm mới", self._load_positions, True))
        layout.addLayout(header)
        self.positions.currentIndexChanged.connect(self._load_applicants)
        self.applicants_table = table(["Mã", "Ứng viên", "Giới thiệu", "Trạng thái", "Ngày ứng tuyển", "Phản hồi đề nghị"])
        self.applicants_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.applicants_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.applicants_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.applicants_table, 3)

        hint = QLabel("Chọn một ứng viên trong danh sách, sau đó chọn bước xử lý bên dưới.")
        hint.setObjectName("Status")
        layout.addWidget(hint)
        stages = QTabWidget()
        stages.setObjectName("HiringWorkflowTabs")
        layout.addWidget(stages, 2)

        review = QWidget()
        review_layout = QVBoxLayout(review)
        review_layout.setContentsMargins(12, 14, 12, 12)
        actions = QHBoxLayout()
        actions.addWidget(QLabel("Chuyển trạng thái:"))
        self.stage = QComboBox()
        self.stage.addItem("Đang xem xét", "reviewing")
        self.stage.addItem("Vào danh sách chọn", "shortlisted")
        self.stage.addItem("Từ chối", "rejected")
        actions.addWidget(self.stage)
        actions.addStretch()
        actions.addWidget(button("Cập nhật hồ sơ đã chọn", self._update_selected, True))
        review_layout.addLayout(actions)
        review_layout.addStretch()
        stages.addTab(review, "1. Sàng lọc")

        assessment = QWidget()
        assessment_layout = QVBoxLayout(assessment)
        assessment_layout.setContentsMargins(12, 14, 12, 12)
        assessment_controls = QHBoxLayout()
        assessment_controls.addWidget(QLabel("Bài thi đã công bố:"))
        self.assessment_exams = QComboBox()
        assessment_controls.addWidget(self.assessment_exams, 1)
        assessment_controls.addWidget(button("Làm mới bài thi", self._load_assessment_exams))
        assessment_controls.addWidget(
            button("Mời ứng viên đã chọn làm bài", self._invite_selected_to_exam, True)
        )
        assessment_layout.addLayout(assessment_controls)
        assessment_layout.addStretch()
        stages.addTab(assessment, "2. Bài đánh giá")

        interview = QWidget()
        interview_layout = QVBoxLayout(interview)
        interview_layout.setContentsMargins(12, 14, 12, 12)
        interview_controls = QHBoxLayout()
        self.interview_title = QLineEdit()
        self.interview_title.setPlaceholderText("Tên buổi phỏng vấn")
        self.interview_title.setMaxLength(200)
        self.interview_datetime = QDateTimeEdit()
        self.interview_datetime.setCalendarPopup(True)
        self.interview_datetime.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.interview_datetime.setDateTime(QDateTime.currentDateTime().addDays(1))
        self.interview_url = QLineEdit()
        self.interview_url.setPlaceholderText("Link họp https://... (tùy chọn)")
        interview_controls.addWidget(self.interview_title, 2)
        interview_controls.addWidget(self.interview_datetime, 1)
        interview_controls.addWidget(self.interview_url, 2)
        interview_layout.addLayout(interview_controls)
        interview_layout.addWidget(button(
            "Lên lịch phỏng vấn sau khi công bố kết quả thi",
            self._schedule_selected_interview, True
        ))
        interview_layout.addStretch()
        stages.addTab(interview, "3. Phỏng vấn")

        decision = QWidget()
        decision_layout = QVBoxLayout(decision)
        decision_layout.setContentsMargins(12, 14, 12, 12)
        decision_controls = QHBoxLayout()
        self.hiring_note = QLineEdit()
        self.hiring_note.setMaxLength(2000)
        self.hiring_note.setPlaceholderText("Ghi chú kết quả phỏng vấn (tối đa 2000 ký tự)")
        decision_controls.addWidget(self.hiring_note, 2)
        decision_controls.addWidget(button(
            "Đề nghị tuyển dụng", lambda: self._decide_selected("offered"), True
        ))
        decision_controls.addWidget(button(
            "Từ chối sau phỏng vấn", lambda: self._decide_selected("rejected")
        ))
        decision_layout.addLayout(decision_controls)
        decision_layout.addStretch()
        stages.addTab(decision, "4. Quyết định")
        self.tabs.addTab(applicants, "Hồ sơ ứng tuyển")

        talents = QWidget()
        talent_layout = QVBoxLayout(talents)
        search_bar = QHBoxLayout()
        self.talent_search = QLineEdit()
        self.talent_search.setPlaceholderText("Tìm theo tên hoặc chuyên môn")
        search_bar.addWidget(self.talent_search, 1)
        search_bar.addWidget(button("Tìm ứng viên", self._load_talents, True))
        talent_layout.addLayout(search_bar)
        self.talent_table = table(["ID", "Ứng viên", "Chuyên môn", "Kinh nghiệm (năm)"])
        talent_layout.addWidget(self.talent_table)
        msg = QLabel("Chỉ hiển thị hồ sơ đã được ứng viên cho phép công khai.")
        msg.setObjectName("Status")
        talent_layout.addWidget(msg)
        self.talent_message = QLineEdit()
        self.talent_message.setMaxLength(2000)
        self.talent_message.setPlaceholderText("Lời nhắn gửi ứng viên (không bắt buộc)")
        talent_layout.addWidget(self.talent_message)
        talent_actions = QHBoxLayout()
        talent_actions.addWidget(QLabel("Mời cho vị trí:"))
        self.invite_position = QComboBox()
        talent_actions.addWidget(self.invite_position, 1)
        talent_actions.addWidget(button("Gửi lời mời tuyển dụng", self._invite_selected_candidate, True))
        talent_layout.addLayout(talent_actions)
        self.tabs.addTab(talents, "Khám phá nhân tài")

        sent = QWidget()
        sent_layout = QVBoxLayout(sent)
        sent_layout.addWidget(button("Làm mới lời mời đã gửi", self._load_sent_invites))
        self.sent_table = table(["ID", "Vị trí", "Ứng viên", "Trạng thái", "Ngày gửi"])
        sent_layout.addWidget(self.sent_table, 1)
        sent_layout.addWidget(button("Hủy lời mời đang chờ", self._cancel_sent_invite))
        self.tabs.addTab(sent, "Lời mời đã gửi")

    def _result(self, result, success: str = "") -> bool:
        self.status.setText(success if result.success and success else result.message)
        return bool(result.success)

    def refresh(self) -> None:
        if self.role == "candidate":
            self._load_jobs()
            self._load_applications()
            self._load_saved_jobs()
            self._load_received_invites()
            privacy = self.controller.get_discoverable()
            if privacy.success:
                self.visibility.setChecked(bool(privacy.data))
        else:
            self._load_positions()
            self._load_assessment_exams()
            self._load_talents()
            self._load_sent_invites()

    def _load_jobs(self) -> None:
        result = self.controller.browse_jobs(self.search.text(), self.location.text())
        if self._result(result):
            self._jobs = list(result.data)
            self.jobs_table.setRowCount(0)
            populate(self.jobs_table, self._jobs, ["id", "title", "company_name", "location", "saved", "applied"])
            self.job_cards.blockSignals(True)
            self.job_cards.clear()
            for job in self._jobs:
                markers = []
                if job.get("saved"):
                    markers.append("Đã lưu")
                if job.get("applied"):
                    markers.append("Đã ứng tuyển")
                state = "  •  ".join(markers)
                title = str(job.get("title") or "Vị trí tuyển dụng")
                company = str(job.get("company_name") or "Doanh nghiệp")
                location = str(job.get("location") or "Chưa cập nhật địa điểm")
                card_text = f"{title}\n{company}  •  {location}"
                if state:
                    card_text += f"\n{state}"
                item = QListWidgetItem(card_text)
                self.job_cards.addItem(item)
                item.setSizeHint(QSize(240, 88))
            self.job_cards.blockSignals(False)
            if self._jobs:
                self.job_cards.setCurrentRow(0)
            else:
                self.job_heading.setText("Chưa có vị trí phù hợp")
                self.job_subtitle.setText("Thử tìm kiếm với từ khóa hoặc địa điểm khác.")
                self.details.clear()
            self.status.setText(f"Tìm thấy {len(self._jobs)} vị trí tuyển dụng công khai.")

    def _card_selected(self) -> None:
        row = self.job_cards.currentRow()
        if row >= 0 and row < self.jobs_table.rowCount():
            self.jobs_table.selectRow(row)
            self._job_selected()

    def _job_selected(self) -> None:
        jid = selected_id(self.jobs_table)
        job = next((item for item in self._jobs if item["id"] == jid), None)
        if job:
            self.job_heading.setText(str(job.get("title") or "Vị trí tuyển dụng"))
            self.job_subtitle.setText(f"{job.get('company_name') or 'Doanh nghiệp'}  •  {job.get('location') or 'Chưa cập nhật địa điểm'}")
        self.details.setPlainText(
            f"{job['title']} — {job['company_name']}\n\n"
            f"Mô tả: {job.get('description') or 'Chưa cập nhật'}\n"
            f"Yêu cầu: {job.get('requirements') or 'Chưa cập nhật'}"
            if job else ""
        )

    def _save_selected(self) -> None:
        jid = selected_id(self.jobs_table)
        if jid is None:
            self.status.setText("Hãy chọn một vị trí.")
            return
        if self._result(self.controller.save_job(jid), "Đã lưu vị trí."):
            self._load_jobs()
            self._load_saved_jobs()

    def _unsave_selected(self) -> None:
        jid = selected_id(self.jobs_table)
        if jid is None:
            self.status.setText("Hãy chọn một vị trí.")
            return
        if self._result(self.controller.unsave_job(jid), "Đã bỏ lưu."):
            self._load_jobs()
            self._load_saved_jobs()

    def _apply_selected(self) -> None:
        jid = selected_id(self.jobs_table)
        if jid is None:
            self.status.setText("Hãy chọn vị trí muốn ứng tuyển.")
            return
        if QMessageBox.question(self, "Xác nhận ứng tuyển", "Gửi đơn ứng tuyển cho vị trí đã chọn?") != QMessageBox.StandardButton.Yes:
            return
        if self._result(self.controller.apply(jid, self.cover_letter.toPlainText()), "Đã nộp đơn ứng tuyển thành công."):
            self.cover_letter.clear()
            self._load_jobs()
            self._load_applications()

    def _load_saved_jobs(self) -> None:
        result = self.controller.saved_jobs()
        if self._result(result):
            populate(
                self.saved_table, list(result.data),
                ["id", "title", "company_name", "location", "status", "applied"],
            )

    def _unsave_saved_job(self) -> None:
        job_id = selected_id(self.saved_table)
        if job_id is None:
            self.status.setText("Hãy chọn việc làm đã lưu.")
            return
        if self._result(self.controller.unsave_job(job_id), "Đã bỏ lưu việc làm."):
            self._load_saved_jobs()
            self._load_jobs()

    def _load_applications(self) -> None:
        result = self.controller.my_applications()
        if self._result(result):
            populate(self.apps_table, list(result.data), ["id", "title", "company_name", "status", "applied_at", "decision_note", "offer_response"])

    def _respond_selected_offer(self, accepted: bool) -> None:
        application_id = selected_id(self.apps_table)
        if application_id is None:
            self.status.setText("Hãy chọn đơn có đề nghị tuyển dụng.")
            return
        row = self.apps_table.currentRow()
        status_cell = self.apps_table.item(row, 3)
        response_cell = self.apps_table.item(row, 6)
        if status_cell is None or (status_cell.data(Qt.ItemDataRole.UserRole + 1) or status_cell.text()) != "offered":
            self.status.setText("Chỉ có thể trả lời đơn đã nhận đề nghị tuyển dụng.")
            return
        if response_cell is not None and response_cell.text():
            self.status.setText("Bạn đã phản hồi đề nghị này, không thể trả lời lần nữa.")
            return
        action = "chấp nhận" if accepted else "từ chối"
        if QMessageBox.question(
            self, "Xác nhận đề nghị tuyển dụng",
            f"Bạn chắc chắn muốn {action} đề nghị tuyển dụng này? Phản hồi không thể thay đổi."
        ) != QMessageBox.StandardButton.Yes:
            return
        result = self.controller.respond_to_offer(application_id, accepted)
        if self._result(result, "Đã ghi nhận phản hồi đề nghị tuyển dụng."):
            self._load_applications()

    def _withdraw_selected(self) -> None:
        application_id = selected_id(self.apps_table)
        if application_id is None:
            self.status.setText("Hãy chọn đơn cần rút.")
            return
        if QMessageBox.question(self, "Xác nhận rút đơn", "Bạn muốn rút đơn ứng tuyển này?") != QMessageBox.StandardButton.Yes:
            return
        if self._result(self.controller.withdraw(application_id), "Đã rút đơn."):
            self._load_applications()

    def _set_visibility(self) -> None:
        self._result(
            self.controller.set_discoverable(self.visibility.isChecked()),
            "Đã lưu quyền hiển thị hồ sơ.",
        )

    def _load_positions(self) -> None:
        # Position listing belongs to the existing Company recruitment controller.
        from server.controllers.recruitment_controller import RecruitmentController
        from server.services.recruitment_service import RecruitmentService
        from server.models.recruitment_repository import RecruitmentRepository
        result = RecruitmentController(RecruitmentService(RecruitmentRepository())).list_positions()
        self.positions.blockSignals(True)
        self.positions.clear()
        if result.success:
            for row in result.positions:
                self.positions.addItem(str(row["title"]), int(row["id"]))
        self.positions.blockSignals(False)
        self.invite_position.clear()
        for index in range(self.positions.count()):
            self.invite_position.addItem(self.positions.itemText(index), self.positions.itemData(index))
        self._load_applicants()
        if not result.success:
            self.status.setText(result.message)

    def _load_applicants(self, *args) -> None:
        job_id = self.positions.currentData()
        if job_id is None:
            self.applicants_table.setRowCount(0)
            return
        result = self.controller.applicants(int(job_id))
        if self._result(result):
            populate(self.applicants_table, list(result.data),
                     ["id", "full_name", "headline", "status", "applied_at", "offer_response"])

    def _update_selected(self) -> None:
        application_id = selected_id(self.applicants_table)
        if application_id is None:
            self.status.setText("Hãy chọn hồ sơ ứng tuyển.")
            return
        result = self.controller.update_application_status(application_id, self.stage.currentData())
        if self._result(result, "Đã cập nhật trạng thái."):
            self._load_applicants()

    def _load_assessment_exams(self) -> None:
        result = self.controller.list_assessment_exams()
        self.assessment_exams.clear()
        if not self._result(result):
            return
        for exam in result.data:
            self.assessment_exams.addItem(
                str(exam.get("title") or f"Bài thi #{exam['id']}"),
                int(exam["id"]),
            )

    def _invite_selected_to_exam(self) -> None:
        application_id = selected_id(self.applicants_table)
        exam_id = self.assessment_exams.currentData()
        if application_id is None or exam_id is None:
            self.status.setText("Chọn hồ sơ ứng viên và bài thi đã công bố.")
            return
        row = self.applicants_table.currentRow()
        status_item = self.applicants_table.item(row, 3)
        if status_item is None or (status_item.data(Qt.ItemDataRole.UserRole + 1) or status_item.text()) != "shortlisted":
            self.status.setText("Chỉ gửi bài thi sau khi đưa ứng viên vào danh sách chọn.")
            return
        if QMessageBox.question(
            self, "Xác nhận gửi bài thi",
            "Gửi lời mời làm bài thi cho ứng viên đã chọn?"
        ) != QMessageBox.StandardButton.Yes:
            return
        result = self.controller.invite_applicant_to_exam(
            application_id, int(exam_id)
        )
        if self._result(result, "Đã gửi lời mời làm bài thi."):
            self._load_applicants()

    def _schedule_selected_interview(self) -> None:
        application_id = selected_id(self.applicants_table)
        if application_id is None:
            self.status.setText("Chọn một hồ sơ đã hoàn thành đánh giá.")
            return
        status_item = self.applicants_table.item(self.applicants_table.currentRow(), 3)
        if status_item is None or (status_item.data(Qt.ItemDataRole.UserRole + 1) or status_item.text()) != "assessment":
            self.status.setText("Chỉ lên lịch từ hồ sơ ở bước đánh giá năng lực.")
            return
        title = self.interview_title.text().strip()
        if not title:
            self.status.setText("Nhập tên buổi phỏng vấn.")
            return
        if QMessageBox.question(
            self, "Xác nhận lịch phỏng vấn",
            "Lên lịch phỏng vấn cho ứng viên được chọn?"
        ) != QMessageBox.StandardButton.Yes:
            return
        scheduled_at = self.interview_datetime.dateTime().toString(Qt.DateFormat.ISODate)
        result = self.controller.schedule_application_interview(
            application_id, title, scheduled_at,
            meeting_url=self.interview_url.text().strip() or None,
        )
        if self._result(result, "Đã lên lịch phỏng vấn. Ứng viên có thể xem trong mục Phỏng vấn."):
            self._load_applicants()

    def _decide_selected(self, decision: str) -> None:
        application_id = selected_id(self.applicants_table)
        if application_id is None:
            self.status.setText("Hãy chọn ứng viên đã phỏng vấn.")
            return
        row = self.applicants_table.currentRow()
        stage_item = self.applicants_table.item(row, 3)
        if stage_item is None or (stage_item.data(Qt.ItemDataRole.UserRole + 1) or stage_item.text()) != "interview":
            self.status.setText("Chỉ ra quyết định cuối cùng từ hồ sơ đang phỏng vấn.")
            return
        label = "Đề nghị tuyển dụng" if decision == "offered" else "Từ chối ứng viên"
        if QMessageBox.question(
            self, "Xác nhận kết quả tuyển dụng",
            f"{label} cho hồ sơ được chọn? Buổi phỏng vấn phải hoàn tất."
        ) != QMessageBox.StandardButton.Yes:
            return
        result = self.controller.decide_after_interview(
            application_id, decision, self.hiring_note.text()
        )
        if self._result(result, "Đã ghi nhận quyết định tuyển dụng."):
            self.hiring_note.clear()
            self._load_applicants()

    def _load_talents(self) -> None:
        result = self.controller.discover_candidates(self.talent_search.text())
        if self._result(result):
            populate(self.talent_table, list(result.data),
                     ["id", "full_name", "headline", "years_experience"])

    def _load_received_invites(self) -> None:
        result = self.invitation_controller.received()
        if self._result(result):
            populate(self.received_table, list(result.data),
                     ["id", "job_title", "company_name", "message", "status", "sent_at"])

    def _answer_invite(self, accepted: bool) -> None:
        invite_id = selected_id(self.received_table)
        if invite_id is None:
            self.status.setText("Hãy chọn lời mời tuyển dụng.")
            return
        question = "Chấp nhận lời mời này?" if accepted else "Từ chối lời mời này?"
        if QMessageBox.question(self, "Xác nhận", question) != QMessageBox.StandardButton.Yes:
            return
        if self._result(self.invitation_controller.respond(invite_id, accepted),
                        "Đã phản hồi lời mời."):
            self._load_received_invites()
            if accepted:
                self._load_applications()
                self.status.setText(
                    "Đã chấp nhận lời mời. Vị trí đã được thêm vào "
                    "'Đơn ứng tuyển của tôi'; doanh nghiệp có thể xử lý hồ sơ."
                )
            else:
                self.status.setText("Đã từ chối lời mời tuyển dụng.")

    def _invite_selected_candidate(self) -> None:
        candidate_id = selected_id(self.talent_table)
        job_id = self.invite_position.currentData()
        if candidate_id is None or job_id is None:
            self.status.setText("Hãy chọn ứng viên và vị trí tuyển dụng đã công bố.")
            return
        if QMessageBox.question(self, "Xác nhận", "Gửi lời mời tuyển dụng tới ứng viên này?") != QMessageBox.StandardButton.Yes:
            return
        result = self.invitation_controller.send(
            int(job_id), int(candidate_id), self.talent_message.text(),
        )
        if self._result(result, "Đã gửi lời mời tuyển dụng."):
            self.talent_message.clear()
            self._load_sent_invites()

    def _load_sent_invites(self) -> None:
        result = self.invitation_controller.sent()
        if self._result(result):
            populate(self.sent_table, list(result.data),
                     ["id", "job_title", "candidate_name", "status", "sent_at"])

    def _cancel_sent_invite(self) -> None:
        invite_id = selected_id(self.sent_table)
        if invite_id is None:
            self.status.setText("Hãy chọn lời mời cần hủy.")
            return
        if QMessageBox.question(self, "Xác nhận", "Hủy lời mời đang chờ này?") != QMessageBox.StandardButton.Yes:
            return
        if self._result(self.invitation_controller.cancel(invite_id), "Đã hủy lời mời."):
            self._load_sent_invites()
