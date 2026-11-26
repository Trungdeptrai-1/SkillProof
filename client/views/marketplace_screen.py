"""Two-way job marketplace screens. Data always comes from authenticated Controller."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDateTime, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QTabWidget, QMessageBox, QCheckBox, QAbstractItemView, QDateTimeEdit,
    QListWidget, QListWidgetItem, QFrame, QSizePolicy, QScrollArea,
)
from server.controllers.marketplace_controller import MarketplaceController
from server.controllers.direct_invitation_controller import DirectInvitationController
from client.components.talent_feed import candidate_card, candidate_avatar, experience_label
from client.components.candidate_marketplace_cards import list_card, status_label


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
QListWidget#TalentFeed { background: transparent; border: none; outline: none; }
QListWidget#TalentFeed::item { background: #FFFFFF; border: 1px solid #DEE7F2;
    border-radius: 14px; margin-bottom: 10px; }
QListWidget#TalentFeed::item:hover { border: 1px solid #7EAAE5; background: #F8FBFF; }
QListWidget#TalentFeed::item:selected { background: #EAF4FF; border: 2px solid #3185D9; }
QFrame#TalentCard { background: transparent; border: none; }
QLabel#TalentCardName { font-size: 16px; font-weight: 700; color: #122B49; }
QLabel#TalentCardHeadline { font-size: 13px; font-weight: 600; color: #2E68A8; }
QLabel#TalentCardMeta { font-size: 12px; color: #4C647D; }
QLabel#TalentCardBio { font-size: 12px; color: #677A91; }
QFrame#TalentDetailPanel { background: #FFFFFF; border: 1px solid #DEE7F2; border-radius: 14px; }
QScrollArea#TalentDetailsScroll { background: transparent; border: none; }
QWidget#TalentProfileHeader { background: transparent; border: none; }
QLabel#TalentDetailName { font-size: 22px; font-weight: 700; color: #122B49; }
QLabel#TalentDetailHeadline { font-size: 14px; color: #2E68A8; font-weight: 600; }
QLabel#TalentDetailMeta { font-size: 12px; color: #66778F; }
QListWidget#CandidateFeed { background: transparent; border: none; outline: none; }
QListWidget#CandidateFeed::item { background: #FFFFFF; border: 1px solid #DEE7F1; border-radius: 12px; margin-bottom: 9px; }
QListWidget#CandidateFeed::item:selected { background: #EAF4FF; border: 2px solid #3185D9; }
QListWidget#CandidateFeed::item:hover { border: 1px solid #91B6E8; }
QFrame#CandidateListCard { background: transparent; border: none; }
QLabel#CandidateCardMarker { background: #E9F1FC; border-radius: 11px; color: #2A67A8; font-size: 21px; }
QLabel#CandidateCardTitle { font-size: 15px; font-weight: 700; color: #152E4C; }
QLabel#CandidateCardCompany { color: #41658E; font-size: 13px; }
QLabel#CandidateCardMeta { color: #73859B; font-size: 11px; }
QLabel#CandidateCardStatus { background: #EAF3FF; color: #215F9D; border: 1px solid #CFE1F6;
    border-radius: 9px; padding: 8px; font-size: 11px; font-weight: 600; }
QFrame#CandidateSidePanel { background: white; border: 1px solid #DFE7F1; border-radius: 13px; }
QLabel#CandidateDetailHeading { color: #152E4C; font-size: 19px; font-weight: 700; }
QLabel#CandidateDetailBody { color: #526B85; font-size: 13px; }
QFrame#PrivacyPanel { background: #FFFFFF; border: 1px solid #DFE7F1; border-radius: 14px; }
QLabel#TalentEmpty { color: #5E738E; font-size: 13px; background: transparent; }
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
        self._talents: list[dict] = []
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

        # Candidate journey tabs: feed-based navigation + contextual action panels.
        mine = QWidget()
        mine_layout = QVBoxLayout(mine)
        mine_layout.setSpacing(15)
        mine_layout.addWidget(self._candidate_section_heading(
            "Đơn ứng tuyển của tôi",
            "Theo dõi tiến độ xét duyệt hồ sơ, phản hồi đề nghị tuyển dụng và quản lý đơn."
        ))
        mine_layout.addWidget(button("Làm mới đơn ứng tuyển", self._load_applications),
                              alignment=Qt.AlignmentFlag.AlignRight)
        self.apps_table = table(["ID", "Vị trí", "Công ty", "Trạng thái",
                                 "Ngày ứng tuyển", "Phản hồi tuyển dụng", "Trả lời đề nghị"])
        self.apps_feed, apps_detail, self.apps_heading, self.apps_summary = self._candidate_feed_sections(
            "Chọn một đơn ứng tuyển", "Trạng thái, phản hồi và các thao tác sẽ hiển thị ở đây."
        )
        self.apps_table.itemSelectionChanged.connect(
            lambda: self._candidate_model_selected("applications")
        )
        apps_actions = QVBoxLayout()
        self.withdraw_button = button("Rút đơn ứng tuyển", self._withdraw_selected)
        self.accept_offer_button = button(
            "Chấp nhận đề nghị", lambda: self._respond_selected_offer(True), True
        )
        self.decline_offer_button = button(
            "Từ chối đề nghị", lambda: self._respond_selected_offer(False)
        )
        apps_actions.addWidget(self.withdraw_button)
        apps_actions.addWidget(self.accept_offer_button)
        apps_actions.addWidget(self.decline_offer_button)
        apps_detail.addLayout(apps_actions)
        apps_detail.addStretch()
        self._candidate_feed_layout(mine_layout, self.apps_feed, apps_detail)
        self.tabs.addTab(mine, "Đơn ứng tuyển của tôi")

        saved = QWidget()
        saved_layout = QVBoxLayout(saved)
        saved_layout.setSpacing(15)
        saved_layout.addWidget(self._candidate_section_heading(
            "Việc làm đã lưu",
            "Danh sách công việc bạn quan tâm. Bạn có thể quay lại xem và quản lý việc đã lưu."
        ))
        saved_layout.addWidget(button("Làm mới việc đã lưu", self._load_saved_jobs),
                               alignment=Qt.AlignmentFlag.AlignRight)
        self.saved_table = table(["ID", "Vị trí", "Công ty", "Địa điểm", "Trạng thái", "Đã ứng tuyển"])
        self.saved_feed, saved_detail, self.saved_heading, self.saved_summary = self._candidate_feed_sections(
            "Chọn công việc đã lưu", "Xem tình trạng tin tuyển dụng và bỏ lưu khi không còn quan tâm."
        )
        self.saved_table.itemSelectionChanged.connect(
            lambda: self._candidate_model_selected("saved")
        )
        self.unsave_button = button("Bỏ lưu công việc", self._unsave_saved_job)
        saved_detail.addWidget(self.unsave_button)
        saved_detail.addStretch()
        self._candidate_feed_layout(saved_layout, self.saved_feed, saved_detail)
        self.tabs.addTab(saved, "Việc làm đã lưu")

        privacy = QWidget()
        privacy_layout = QVBoxLayout(privacy)
        privacy_layout.setSpacing(18)
        privacy_layout.addWidget(self._candidate_section_heading(
            "Quyền riêng tư hồ sơ",
            "Bạn kiểm soát việc doanh nghiệp có thể tìm thấy hồ sơ giới thiệu của mình hay không."
        ))
        privacy_box = QFrame()
        privacy_box.setObjectName("PrivacyPanel")
        privacy_inner = QVBoxLayout(privacy_box)
        privacy_inner.setContentsMargins(25, 25, 25, 25)
        privacy_inner.setSpacing(16)
        privacy_title = QLabel("Hiển thị hồ sơ với nhà tuyển dụng")
        privacy_title.setObjectName("CandidateDetailHeading")
        privacy_inner.addWidget(privacy_title)
        self.privacy_status = QLabel("Đang kiểm tra cài đặt công khai hồ sơ...")
        self.privacy_status.setObjectName("CandidateDetailBody")
        privacy_inner.addWidget(self.privacy_status)
        note = QLabel(
            "Mặc định hồ sơ của bạn không hiển thị trong kết quả tìm kiếm ứng viên. "
            "Khi bật công khai, doanh nghiệp chỉ thấy tên, vị trí chuyên môn, "
            "số năm kinh nghiệm và phần giới thiệu. Email cùng đường dẫn CV vẫn được giữ riêng tư."
        )
        note.setWordWrap(True)
        note.setObjectName("CandidateDetailBody")
        privacy_inner.addWidget(note)
        self.visibility = QCheckBox("Cho phép doanh nghiệp tìm thấy hồ sơ giới thiệu của tôi")
        self.visibility.toggled.connect(self._update_privacy_preview)
        privacy_inner.addWidget(self.visibility)
        privacy_inner.addWidget(button("Lưu quyền hiển thị", self._set_visibility, True),
                                alignment=Qt.AlignmentFlag.AlignLeft)
        privacy_layout.addWidget(privacy_box)
        privacy_layout.addStretch()
        self.tabs.addTab(privacy, "Quyền riêng tư")

        invites = QWidget()
        invites_layout = QVBoxLayout(invites)
        invites_layout.setSpacing(15)
        invites_layout.addWidget(self._candidate_section_heading(
            "Lời mời tuyển dụng",
            "Xem doanh nghiệp đã kết nối với bạn và trả lời các lời mời phù hợp."
        ))
        invites_layout.addWidget(button("Làm mới lời mời", self._load_received_invites),
                                 alignment=Qt.AlignmentFlag.AlignRight)
        self.received_table = table(["ID", "Vị trí", "Công ty", "Lời nhắn", "Trạng thái", "Ngày gửi"])
        self.invites_feed, invites_detail, self.invites_heading, self.invites_summary = self._candidate_feed_sections(
            "Chọn một lời mời", "Đọc nội dung lời mời từ doanh nghiệp trước khi quyết định."
        )
        self.received_table.itemSelectionChanged.connect(
            lambda: self._candidate_model_selected("invites")
        )
        self.invite_accept_button = button(
            "Chấp nhận lời mời", lambda: self._answer_invite(True), True
        )
        self.invite_decline_button = button(
            "Từ chối lời mời", lambda: self._answer_invite(False)
        )
        invites_detail.addWidget(self.invite_accept_button)
        invites_detail.addWidget(self.invite_decline_button)
        invites_detail.addStretch()
        self._candidate_feed_layout(invites_layout, self.invites_feed, invites_detail)
        self.tabs.addTab(invites, "Lời mời tuyển dụng")

        self._candidate_data = {"applications": [], "saved": [], "invites": []}
        for kind, feed in (
            ("applications", self.apps_feed),
            ("saved", self.saved_feed),
            ("invites", self.invites_feed),
        ):
            feed.itemSelectionChanged.connect(
                lambda selected_kind=kind: self._candidate_feed_selected(selected_kind)
            )
        self._refresh_candidate_action_states()

    def _candidate_section_heading(self, heading: str, description: str) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 8, 0, 6)
        layout.setSpacing(5)
        title = QLabel(heading)
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel(description)
        subtitle.setObjectName("CandidateDetailBody")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        return wrap

    def _candidate_feed_sections(
        self, heading: str, description: str
    ) -> tuple[QListWidget, QVBoxLayout, QLabel, QLabel]:
        feed = QListWidget()
        feed.setObjectName("CandidateFeed")
        feed.setSpacing(4)
        feed.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QFrame()
        panel.setObjectName("CandidateSidePanel")
        panel.setMinimumWidth(290)
        panel.setMaximumWidth(520)
        side = QVBoxLayout(panel)
        side.setContentsMargins(23, 22, 23, 22)
        side.setSpacing(14)
        title = QLabel(heading)
        title.setObjectName("CandidateDetailHeading")
        title.setWordWrap(True)
        summary = QLabel(description)
        summary.setObjectName("CandidateDetailBody")
        summary.setWordWrap(True)
        side.addWidget(title)
        side.addWidget(summary)
        feed.setProperty("detail_panel", panel)
        return feed, side, title, summary

    def _candidate_feed_layout(self, parent: QVBoxLayout,
                               feed: QListWidget, detail: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(18)
        row.addWidget(feed, 5)
        panel = detail.parentWidget()
        row.addWidget(panel, 4)
        parent.addLayout(row, 1)

    def _candidate_model_selected(self, kind: str) -> None:
        table_widget, feed, *_ = self._candidate_views(kind)
        row = table_widget.currentRow()
        if 0 <= row < len(self._candidate_data.get(kind, [])) and feed.currentRow() != row:
            feed.setCurrentRow(row)

    def _candidate_feed_selected(self, kind: str) -> None:
        model, feed, title, summary = self._candidate_views(kind)
        row = feed.currentRow()
        data = self._candidate_data.get(kind, [])
        selected = data[row] if 0 <= row < len(data) else None
        if selected is not None:
            model.blockSignals(True)
            model.selectRow(row)
            model.blockSignals(False)
        title.setText(
            str((selected.get("title") or selected.get("job_title") or "Vị trí tuyển dụng"))
            if selected else "Chưa chọn mục nào"
        )
        if selected is None:
            summary.setText("Chọn một thẻ bên trái để xem thông tin và thao tác phù hợp.")
        elif kind == "applications":
            summary.setText(
                f"Doanh nghiệp: {selected.get('company_name') or 'Chưa cập nhật'}\n"
                f"Trạng thái: {status_label(selected.get('status'))}\n"
                f"Phản hồi: {selected.get('decision_note') or 'Chưa có phản hồi'}\n"
                f"Đề nghị: {status_label(selected.get('offer_response'))}"
            )
        elif kind == "saved":
            summary.setText(
                f"Doanh nghiệp: {selected.get('company_name') or 'Chưa cập nhật'}\n"
                f"Địa điểm: {selected.get('location') or 'Chưa cập nhật'}\n"
                f"Tình trạng: {status_label(selected.get('status'))}"
            )
        else:
            summary.setText(
                f"Doanh nghiệp: {selected.get('company_name') or 'Chưa cập nhật'}\n"
                f"Trạng thái: {status_label(selected.get('status'))}\n"
                f"Lời nhắn: {selected.get('message') or 'Không có lời nhắn'}"
            )
        self._refresh_candidate_action_states()

    def _candidate_views(self, kind: str):
        return {
            "applications": (self.apps_table, self.apps_feed, self.apps_heading, self.apps_summary),
            "saved": (self.saved_table, self.saved_feed, self.saved_heading, self.saved_summary),
            "invites": (self.received_table, self.invites_feed, self.invites_heading, self.invites_summary),
        }[kind]

    def _fill_candidate_feed(self, kind: str, rows: list[dict]) -> None:
        model, feed, *_ = self._candidate_views(kind)
        self._candidate_data[kind] = rows
        feed.blockSignals(True)
        feed.clear()
        for row in rows:
            item = QListWidgetItem()
            item.setSizeHint(QSize(300, 132))
            feed.addItem(item)
            feed.setItemWidget(item, list_card(row, kind))
        feed.blockSignals(False)
        if rows:
            feed.setCurrentRow(0)
        else:
            item = QListWidgetItem("Chưa có dữ liệu trong mục này. Các hoạt động mới sẽ xuất hiện ở đây.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setSizeHint(QSize(300, 100))
            feed.addItem(item)
            model.clearSelection()
            self._candidate_feed_selected(kind)

    def _refresh_candidate_action_states(self) -> None:
        if not hasattr(self, "_candidate_data"):
            return
        selected = {}
        for kind in self._candidate_data:
            _, feed, *_ = self._candidate_views(kind)
            row = feed.currentRow()
            selected[kind] = self._candidate_data[kind][row] if 0 <= row < len(self._candidate_data[kind]) else None
        app = selected["applications"]
        offer_pending = bool(app and app.get("status") == "offered" and not app.get("offer_response"))
        self.accept_offer_button.setEnabled(offer_pending)
        self.decline_offer_button.setEnabled(offer_pending)
        self.withdraw_button.setEnabled(bool(app and app.get("status") in ("submitted", "reviewing", "shortlisted")))
        self.unsave_button.setEnabled(selected["saved"] is not None)
        invitation = selected["invites"]
        pending = bool(invitation and invitation.get("status") == "pending")
        self.invite_accept_button.setEnabled(pending)
        self.invite_decline_button.setEnabled(pending)

    def _update_privacy_preview(self, checked: bool) -> None:
        if hasattr(self, "privacy_status"):
            self.privacy_status.setText(
                "Hồ sơ sẽ được công khai sau khi bạn nhấn Lưu quyền hiển thị."
                if checked else "Hồ sơ sẽ được ẩn sau khi bạn nhấn Lưu quyền hiển thị."
            )

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
        talent_layout.setContentsMargins(0, 10, 0, 0)
        talent_layout.setSpacing(16)

        # Search is an ordinary controller query; no fake recommendation scores.
        discovery_intro = QLabel("Tìm ứng viên phù hợp với đội ngũ của bạn")
        discovery_intro.setObjectName("PageTitle")
        talent_layout.addWidget(discovery_intro)
        discovery_note = QLabel(
            "Khám phá hồ sơ nghề nghiệp đã được ứng viên tự nguyện công khai. "
            "Chọn một hồ sơ để xem thêm và gửi lời mời tuyển dụng."
        )
        discovery_note.setWordWrap(True)
        discovery_note.setObjectName("Status")
        talent_layout.addWidget(discovery_note)

        search_bar = QHBoxLayout()
        search_bar.setSpacing(10)
        self.talent_search = QLineEdit()
        self.talent_search.setPlaceholderText("Tìm theo tên hoặc vị trí chuyên môn (Python, QA, Data...)")
        self.talent_search.setMaxLength(200)
        self.talent_search.returnPressed.connect(self._load_talents)
        search_bar.addWidget(self.talent_search, 1)
        search_bar.addWidget(button("Tìm ứng viên", self._load_talents, True))
        talent_layout.addLayout(search_bar)

        self.talent_count = QLabel("")
        self.talent_count.setObjectName("SectionTitle")
        talent_layout.addWidget(self.talent_count)

        # Hidden compatibility/selection model: existing controller workflows use
        # selected_id(self.talent_table). The new feed is the visible interaction.
        self.talent_table = table(["ID", "Ứng viên", "Chuyên môn", "Kinh nghiệm (năm)"])
        self.talent_table.itemSelectionChanged.connect(self._talent_table_selected)

        columns = QHBoxLayout()
        columns.setSpacing(18)
        listing = QVBoxLayout()
        listing.setContentsMargins(0, 0, 0, 0)
        self.talent_feed = QListWidget()
        self.talent_feed.setObjectName("TalentFeed")
        self.talent_feed.setSpacing(4)
        self.talent_feed.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.talent_feed.itemSelectionChanged.connect(self._talent_card_selected)
        listing.addWidget(self.talent_feed, 1)
        columns.addLayout(listing, 5)

        # The detail form must scroll independently of the candidate feed.
        # Without an internal scroll area Qt compresses the avatar, text edits,
        # and combo boxes into each other on normal laptop screen heights.
        detail_scroll = QScrollArea()
        detail_scroll.setObjectName("TalentDetailsScroll")
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.talent_detail_scroll = detail_scroll

        panel = QFrame()
        panel.setObjectName("TalentDetailPanel")
        panel.setMinimumHeight(615)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 22, 22, 22)
        panel_layout.setSpacing(12)

        identity = QWidget()
        identity.setObjectName("TalentProfileHeader")
        identity_layout = QHBoxLayout(identity)
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(16)

        self.talent_avatar = QLabel()
        self.talent_avatar.setFixedSize(72, 72)
        self.talent_avatar.setPixmap(candidate_avatar("Ứng viên", 72))
        identity_layout.addWidget(self.talent_avatar, 0, Qt.AlignmentFlag.AlignTop)

        name_column = QVBoxLayout()
        name_column.setSpacing(5)
        self.talent_name = QLabel("Chọn hồ sơ ứng viên")
        self.talent_name.setObjectName("TalentDetailName")
        self.talent_name.setWordWrap(True)
        self.talent_name.setMinimumHeight(30)
        name_column.addWidget(self.talent_name)
        self.talent_headline = QLabel("Thông tin nghề nghiệp được công khai sẽ xuất hiện tại đây.")
        self.talent_headline.setObjectName("TalentDetailHeadline")
        self.talent_headline.setWordWrap(True)
        name_column.addWidget(self.talent_headline)
        self.talent_experience = QLabel("")
        self.talent_experience.setObjectName("TalentDetailMeta")
        name_column.addWidget(self.talent_experience)
        identity_layout.addLayout(name_column, 1)
        panel_layout.addWidget(identity)

        about_title = QLabel("Giới thiệu bản thân")
        about_title.setObjectName("SectionTitle")
        panel_layout.addWidget(about_title)
        self.talent_bio = QLabel("Chọn một ứng viên ở danh sách bên trái để xem giới thiệu.")
        self.talent_bio.setWordWrap(True)
        self.talent_bio.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.talent_bio.setObjectName("TalentCardMeta")
        panel_layout.addWidget(self.talent_bio)
        panel_layout.addSpacing(8)

        invite_heading = QLabel("Mời ứng viên ứng tuyển")
        invite_heading.setObjectName("SectionTitle")
        panel_layout.addWidget(invite_heading)
        panel_layout.addWidget(QLabel("Vị trí tuyển dụng"))
        self.invite_position = QComboBox()
        self.invite_position.setMinimumHeight(44)
        self.invite_position.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.invite_position.currentIndexChanged.connect(
            lambda *_: self._refresh_talent_detail(
                self._talents[self.talent_feed.currentRow()]
                if 0 <= self.talent_feed.currentRow() < len(self._talents) else None
            )
        )
        panel_layout.addWidget(self.invite_position)
        self.talent_message = QTextEdit()
        self.talent_message.setMinimumHeight(92)
        self.talent_message.setMaximumHeight(110)
        self.talent_message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.talent_message.setPlaceholderText("Lời mời giới thiệu vị trí và lý do bạn muốn kết nối (không bắt buộc)")
        self.talent_message.textChanged.connect(self._limit_talent_message)
        panel_layout.addWidget(self.talent_message)
        self.talent_invite_button = button(
            "Gửi lời mời tuyển dụng", self._invite_selected_candidate, True
        )
        panel_layout.addWidget(self.talent_invite_button)
        self.talent_privacy = QLabel(
            "Thông tin liên hệ và đường dẫn CV riêng tư không hiển thị trong tìm kiếm."
        )
        self.talent_privacy.setObjectName("TalentDetailMeta")
        self.talent_privacy.setWordWrap(True)
        panel_layout.addSpacing(6)
        panel_layout.addWidget(self.talent_privacy)
        panel_layout.addStretch(1)
        detail_scroll.setWidget(panel)
        columns.addWidget(detail_scroll, 4)
        talent_layout.addLayout(columns, 1)
        self._refresh_talent_detail(None)
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
                self.privacy_status.setText(
                    "Hồ sơ đang được phép xuất hiện trong tìm kiếm của doanh nghiệp."
                    if bool(privacy.data) else "Hồ sơ hiện không được công khai trong tìm kiếm."
                )
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
            rows = list(result.data)
            populate(self.saved_table, rows,
                     ["id", "title", "company_name", "location", "status", "applied"])
            self._fill_candidate_feed("saved", rows)

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
            rows = list(result.data)
            populate(self.apps_table, rows,
                     ["id", "title", "company_name", "status", "applied_at", "decision_note", "offer_response"])
            self._fill_candidate_feed("applications", rows)

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

    def _limit_talent_message(self) -> None:
        # QTextEdit has no maxLength property; enforce the service's 2000 limit.
        text = self.talent_message.toPlainText()
        if len(text) > 2000:
            cursor = self.talent_message.textCursor()
            position = min(cursor.position(), 2000)
            self.talent_message.blockSignals(True)
            self.talent_message.setPlainText(text[:2000])
            cursor.setPosition(position)
            self.talent_message.setTextCursor(cursor)
            self.talent_message.blockSignals(False)

    def _talent_card_selected(self) -> None:
        row = self.talent_feed.currentRow()
        if 0 <= row < self.talent_table.rowCount():
            self.talent_table.blockSignals(True)
            self.talent_table.selectRow(row)
            self.talent_table.blockSignals(False)
            self._refresh_talent_detail(self._talents[row])

    def _talent_table_selected(self) -> None:
        row = self.talent_table.currentRow()
        if 0 <= row < self.talent_feed.count() and row != self.talent_feed.currentRow():
            self.talent_feed.setCurrentRow(row)

    def _refresh_talent_detail(self, candidate: dict | None) -> None:
        selected = candidate is not None
        name = str(candidate.get("full_name") or "Ứng viên") if selected else "Chọn hồ sơ ứng viên"
        self.talent_name.setText(name)
        self.talent_avatar.setPixmap(candidate_avatar(name, 72))
        self.talent_headline.setText(
            str(candidate.get("headline") or "Chưa cập nhật chuyên môn")
            if selected else "Chọn một thẻ hồ sơ để xem thông tin chuyên môn."
        )
        self.talent_experience.setText(
            experience_label(candidate.get("years_experience")) if selected else ""
        )
        self.talent_bio.setText(
            str(candidate.get("bio") or "Ứng viên chưa thêm phần giới thiệu.")
            if selected else "Giới thiệu sẽ xuất hiện sau khi bạn chọn ứng viên."
        )
        self.talent_invite_button.setEnabled(selected and self.invite_position.currentData() is not None)

    def _load_talents(self) -> None:
        result = self.controller.discover_candidates(self.talent_search.text())
        if not self._result(result):
            self._talents = []
            self.talent_table.setRowCount(0)
            self.talent_feed.clear()
            self.talent_count.setText("Không thể tải hồ sơ. Vui lòng thử lại.")
            self._refresh_talent_detail(None)
            return
        self._talents = list(result.data or [])
        self.talent_table.blockSignals(True)
        populate(self.talent_table, self._talents,
                 ["id", "full_name", "headline", "years_experience"])
        self.talent_table.blockSignals(False)
        self.talent_feed.blockSignals(True)
        self.talent_feed.clear()
        for candidate in self._talents:
            item = QListWidgetItem()
            item.setSizeHint(QSize(300, 145))
            self.talent_feed.addItem(item)
            self.talent_feed.setItemWidget(item, candidate_card(candidate))
        self.talent_feed.blockSignals(False)
        count = len(self._talents)
        self.talent_count.setText(f"{count} hồ sơ ứng viên công khai")
        if count:
            self.talent_feed.setCurrentRow(0)
            self._talent_card_selected()
        else:
            empty = QListWidgetItem(
                "Chưa tìm thấy hồ sơ phù hợp. Thử từ khóa khác hoặc tìm kiếm tất cả."
            )
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            empty.setSizeHint(QSize(250, 100))
            self.talent_feed.addItem(empty)
            self._refresh_talent_detail(None)

    def _load_received_invites(self) -> None:
        result = self.invitation_controller.received()
        if self._result(result):
            rows = list(result.data)
            populate(self.received_table, rows,
                     ["id", "job_title", "company_name", "message", "status", "sent_at"])
            self._fill_candidate_feed("invites", rows)

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
            int(job_id), int(candidate_id), self.talent_message.toPlainText(),
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
