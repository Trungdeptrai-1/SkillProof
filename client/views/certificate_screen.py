"""Certificate listing, issuance, and verification view."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.utils.constants import COLOR_OFF_WHITE
from app.utils.styles import primary_button_style, secondary_button_style
from client.components.status_banner import StatusBanner
from client.components.workflow_page import add_workflow_header
from client.views.extended_workflow_contracts import CertificateController


class CertificateScreen(QWidget):
    """Certificate actions are gated by permissions from the real Controller."""

    _MANAGER_ROLES = {"company", "expert", "admin"}

    def __init__(
        self,
        role: str,
        controller: CertificateController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._role = role
        self._controller = controller
        self._on_back_cb: Callable[[], None] | None = None
        self.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        self._build_ui()
        if controller is None:
            self._status.set_status(
                "Chưa có Certificate Controller. Danh sách, cấp mới và xác minh "
                "chưa được kết nối; không có chứng chỉ mẫu.",
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
            layout, "Chứng chỉ kỹ năng", self._handle_back
        )
        self._status = StatusBanner()
        layout.addWidget(self._status)

        self._refresh_button = QPushButton("Tải chứng chỉ")
        self._refresh_button.setStyleSheet(secondary_button_style(font_size=12))
        self._refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self._refresh_button, alignment=Qt.AlignmentFlag.AlignRight)
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            [
                "Mã chứng chỉ",
                "Chủ sở hữu",
                "Kỹ năng",
                "Điểm",
                "Trạng thái",
                "Cấp ngày",
                "Hết hạn",
            ]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self._table, stretch=1)

        self._management_section = QWidget()
        management = QHBoxLayout(self._management_section)
        management.setContentsMargins(0, 0, 0, 0)
        verify_form = QFormLayout()
        self._verify_code = QLineEdit()
        self._verify_code.setPlaceholderText("Nhập mã chứng chỉ")
        self._verify_button = QPushButton("Xác minh")
        self._verify_button.setStyleSheet(secondary_button_style(font_size=12))
        self._verify_button.clicked.connect(self._verify_certificate)
        verify_form.addRow("Mã chứng chỉ", self._verify_code)
        verify_form.addRow(self._verify_button)
        management.addLayout(verify_form)

        issue_form = QFormLayout()
        self._user_id = QSpinBox()
        self._user_id.setRange(0, 2147483647)
        self._user_id.setSpecialValueText("Chọn Candidate")
        self._user_id.setValue(0)
        self._skill_id = QSpinBox()
        self._skill_id.setRange(0, 2147483647)
        self._skill_id.setSpecialValueText("Chọn kỹ năng")
        self._skill_id.setValue(0)
        self._issue_button = QPushButton("Cấp chứng chỉ")
        self._issue_button.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._issue_button.clicked.connect(self._issue_certificate)
        issue_form.addRow("Candidate ID", self._user_id)
        issue_form.addRow("Skill ID", self._skill_id)
        issue_form.addRow(self._issue_button)
        management.addLayout(issue_form)
        self._revoke_button = QPushButton("Thu hồi chứng chỉ đã chọn")
        self._revoke_button.setStyleSheet(secondary_button_style(font_size=12))
        self._revoke_button.clicked.connect(self._revoke_certificate)
        issue_form.addRow(self._revoke_button)
        layout.addWidget(self._management_section)
        self._verification_status = QLabel("")
        self._verification_status.setWordWrap(True)
        layout.addWidget(self._verification_status)

        if self._role == "candidate":
            self._management_section.hide()
        self._refresh_button.setEnabled(self._controller is not None)
        self._set_management_enabled(False, False)
        self._revoke_button.setEnabled(False)

    def refresh(self) -> None:
        if self._controller is None:
            self._status.set_status(
                "Chưa có Certificate Controller; thao tác đang khóa.",
                "unavailable",
            )
            return
        permissions = self._controller.get_permissions()
        can_manage = self._role in self._MANAGER_ROLES
        self._set_management_enabled(
            can_manage and permissions.can_issue,
            can_manage and permissions.can_verify,
        )
        self._revoke_button.setVisible(self._role == "admin")
        self._revoke_button.setEnabled(False)
        self._status.set_status("Đang tải chứng chỉ...", "loading")
        result = self._controller.list_certificates()
        self._table.setRowCount(0)
        if not result.success:
            self._status.set_status(
                result.message or "Không thể tải chứng chỉ.", "error"
            )
            return
        for certificate in result.items:
            row = self._table.rowCount()
            self._table.insertRow(row)
            values = (
                certificate.cert_code,
                certificate.subject_name,
                certificate.skill_name,
                f"{certificate.score:g}" if certificate.score is not None else "—",
                certificate.status,
                certificate.issued_at,
                certificate.expires_at or "Không thời hạn",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, certificate.id)
                self._table.setItem(row, column, cell)
        self._status.set_status(
            "" if result.items else "Chưa có chứng chỉ.",
            "info" if result.items else "empty",
        )
        self._revoke_button.setEnabled(False)

    def _set_management_enabled(self, can_issue: bool, can_verify: bool) -> None:
        self._issue_button.setEnabled(can_issue)
        self._user_id.setEnabled(can_issue)
        self._skill_id.setEnabled(can_issue)
        self._verify_code.setEnabled(can_verify)
        self._verify_button.setEnabled(can_verify)

    def _issue_certificate(self) -> None:
        if self._controller is None or self._role not in self._MANAGER_ROLES:
            return
        if self._user_id.value() <= 0 or self._skill_id.value() <= 0:
            self._status.set_status(
                "Nhập Candidate ID và Skill ID hợp lệ.", "error"
            )
            return
        confirmation = QMessageBox.question(
            self,
            "Cấp chứng chỉ",
            "Xác nhận cấp chứng chỉ cho Candidate và kỹ năng đã chọn?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        result = self._controller.issue_certificate(
            self._user_id.value(), self._skill_id.value(), None
        )
        self._status.set_status(
            result.message or (
                "Đã cấp chứng chỉ."
                if result.success
                else "Không thể cấp chứng chỉ."
            ),
            "success" if result.success else "error",
        )
        if result.success:
            self.refresh()

    def _selection_changed(self) -> None:
        row = self._table.currentRow()
        cell = self._table.item(row, 0) if row >= 0 else None
        certificate_id = cell.data(Qt.ItemDataRole.UserRole) if cell else None
        self._revoke_button.setEnabled(
            self._controller is not None
            and self._role == "admin"
            and isinstance(certificate_id, int)
        )

    def _verify_certificate(self) -> None:
        if self._controller is None or self._role not in self._MANAGER_ROLES:
            return
        code = self._verify_code.text().strip()
        if not code:
            self._verification_status.setText("Vui lòng nhập mã chứng chỉ.")
            return
        result = self._controller.verify_certificate(code)
        if not result.success or result.certificate is None:
            self._verification_status.setText(
                result.message or "Không tìm thấy chứng chỉ hợp lệ."
            )
            return
        certificate = result.certificate
        score = (
            f" | Điểm: {certificate.score:g}"
            if certificate.score is not None
            else ""
        )
        self._verification_status.setText(
            f"Mã {certificate.cert_code} — {certificate.subject_name} — "
            f"{certificate.skill_name} — {certificate.status}{score}"
        )

    def _revoke_certificate(self) -> None:
        if self._controller is None or self._role != "admin":
            return
        row = self._table.currentRow()
        cell = self._table.item(row, 0) if row >= 0 else None
        certificate_id = cell.data(Qt.ItemDataRole.UserRole) if cell else None
        if not isinstance(certificate_id, int):
            self._status.set_status("Chọn chứng chỉ cần thu hồi.", "error")
            return
        confirmation = QMessageBox.question(
            self,
            "Thu hồi chứng chỉ",
            "Chứng chỉ đã thu hồi không thể được kích hoạt lại. Tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        result = self._controller.revoke_certificate(certificate_id)
        self._status.set_status(
            result.message or (
                "Đã thu hồi chứng chỉ."
                if result.success
                else "Không thể thu hồi chứng chỉ."
            ),
            "success" if result.success else "error",
        )
        if result.success:
            self.refresh()

    def _handle_back(self) -> None:
        if self._on_back_cb is not None:
            self._on_back_cb()
