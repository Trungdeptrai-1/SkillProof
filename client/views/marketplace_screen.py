"""Two-way job marketplace screens. Data always comes from authenticated Controller."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QTabWidget, QMessageBox, QCheckBox, QAbstractItemView,
)
from server.controllers.marketplace_controller import MarketplaceController
from server.controllers.direct_invitation_controller import DirectInvitationController


STYLE = """
QWidget#MarketplaceRoot { background: #F8FAFC; color: #1E293B; font-family: 'Segoe UI'; }
QLabel#PageTitle { font-size: 24px; font-weight: 700; color: #172B4D; }
QLabel#SectionTitle { font-size: 15px; font-weight: 650; color: #172B4D; }
QLabel#Status { color: #475569; font-size: 12px; }
QLineEdit, QTextEdit, QComboBox { background: white; border: 1px solid #CBD5E1;
    border-radius: 7px; padding: 8px; font-size: 13px; color: #0F172A; }
QPushButton { background: white; color: #1E40AF; border: 1px solid #CBD5E1;
    border-radius: 7px; padding: 8px 12px; font-weight: 600; }
QPushButton:hover { background: #EFF6FF; }
QPushButton#Primary { background: #2563EB; color: white; border: none; }
QPushButton#Primary:hover { background: #1D4ED8; }
QTableWidget { background: white; alternate-background-color: #F8FAFC;
    border: 1px solid #E2E8F0; border-radius: 8px; gridline-color: #E2E8F0; }
QHeaderView::section { background: #EAF0F8; color: #334155;
    padding: 9px; border: none; font-weight: 600; }
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 10px 18px; }
QTabBar::tab:selected { color: #1D4ED8; border-bottom: 2px solid #2563EB; }
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
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return widget


def populate(widget: QTableWidget, rows: list[dict], columns: list[str]) -> None:
    widget.setRowCount(len(rows))
    for row_index, item in enumerate(rows):
        for col_index, field in enumerate(columns):
            cell = QTableWidgetItem(str(item.get(field) or ""))
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
        outer.setContentsMargins(30, 24, 30, 24)
        outer.setSpacing(16)
        header = QHBoxLayout()
        title = QLabel(
            "Khám phá cơ hội việc làm" if self.role == "candidate"
            else "Trung tâm ứng viên"
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

        self.jobs_table = table(["ID", "Vị trí", "Công ty", "Địa điểm", "Đã lưu", "Đã ứng tuyển"])
        self.jobs_table.itemSelectionChanged.connect(self._job_selected)
        layout.addWidget(self.jobs_table, 1)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Chọn một vị trí để xem mô tả và yêu cầu.")
        self.details.setMaximumHeight(115)
        layout.addWidget(self.details)
        self.cover_letter = QTextEdit()
        self.cover_letter.setPlaceholderText("Lời giới thiệu khi ứng tuyển (không bắt buộc, tối đa 4000 ký tự)")
        self.cover_letter.setMaximumHeight(78)
        layout.addWidget(self.cover_letter)
        actions = QHBoxLayout()
        actions.addWidget(button("Lưu việc làm", self._save_selected))
        actions.addWidget(button("Bỏ lưu", self._unsave_selected))
        actions.addStretch()
        actions.addWidget(button("Ứng tuyển ngay", self._apply_selected, True))
        layout.addLayout(actions)
        self.tabs.addTab(explore, "Khám phá việc làm")

        mine = QWidget()
        mine_layout = QVBoxLayout(mine)
        mine_layout.addWidget(button("Làm mới đơn ứng tuyển", self._load_applications))
        self.apps_table = table(["ID", "Vị trí", "Công ty", "Trạng thái", "Ngày ứng tuyển"])
        mine_layout.addWidget(self.apps_table)
        mine_layout.addWidget(button("Rút đơn đã chọn", self._withdraw_selected))
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
        self.applicants_table = table(["ID", "Ứng viên", "Giới thiệu", "Trạng thái", "Ngày ứng tuyển"])
        layout.addWidget(self.applicants_table, 1)
        actions = QHBoxLayout()
        actions.addWidget(QLabel("Chuyển trạng thái:"))
        self.stage = QComboBox()
        self.stage.addItem("Đang xem xét", "reviewing")
        self.stage.addItem("Vào danh sách chọn", "shortlisted")
        self.stage.addItem("Mời đánh giá", "assessment")
        self.stage.addItem("Mời phỏng vấn", "interview")
        self.stage.addItem("Đề nghị tuyển dụng", "offered")
        self.stage.addItem("Từ chối", "rejected")
        actions.addWidget(self.stage)
        actions.addStretch()
        actions.addWidget(button("Cập nhật hồ sơ đã chọn", self._update_selected, True))
        layout.addLayout(actions)
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
            self._load_talents()
            self._load_sent_invites()

    def _load_jobs(self) -> None:
        result = self.controller.browse_jobs(self.search.text(), self.location.text())
        if self._result(result):
            self._jobs = list(result.data)
            self.jobs_table.setRowCount(0)
            populate(self.jobs_table, self._jobs, ["id", "title", "company_name", "location", "saved", "applied"])
            self.status.setText(f"Tìm thấy {len(self._jobs)} vị trí tuyển dụng công khai.")

    def _job_selected(self) -> None:
        jid = selected_id(self.jobs_table)
        job = next((item for item in self._jobs if item["id"] == jid), None)
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
            populate(self.apps_table, list(result.data), ["id", "title", "company_name", "status", "applied_at"])

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
                     ["id", "full_name", "headline", "status", "applied_at"])

    def _update_selected(self) -> None:
        application_id = selected_id(self.applicants_table)
        if application_id is None:
            self.status.setText("Hãy chọn hồ sơ ứng tuyển.")
            return
        result = self.controller.update_application_status(application_id, self.stage.currentData())
        if self._result(result, "Đã cập nhật trạng thái."):
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
