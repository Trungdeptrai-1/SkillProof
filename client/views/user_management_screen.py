"""Admin user-management view with an injectable Controller contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.user_model import ROLE_LABELS, UserModel
from app.utils.constants import (
    COLOR_ERROR,
    COLOR_LIGHT_GRAY,
    COLOR_NAVY_DARK,
    COLOR_OFF_WHITE,
    COLOR_TEXT_DARK,
    COLOR_TEXT_MUTED,
    COLOR_WHITE,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from app.utils.styles import primary_button_style, secondary_button_style


@dataclass(frozen=True)
class UserListResult:
    success: bool
    users: tuple[UserModel, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class UserActionResult:
    success: bool
    message: str = ""


class UserManagementController(Protocol):
    """Expected API for a future admin user-management Controller."""

    def list_users(self) -> UserListResult: ...

    def set_user_active(self, user_id: int, is_active: bool) -> UserActionResult: ...


class UserManagementScreen(QWidget):
    """Browse and activate/deactivate users when a real Controller is supplied."""

    def __init__(
        self,
        controller: UserManagementController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._controller = controller
        self._on_back_cb = None
        self._users: tuple[UserModel, ...] = ()
        self._setup_ui()
        if self._controller is None:
            self._set_unavailable()
        else:
            self.refresh()

    @property
    def on_back(self):
        return self._on_back_cb

    @on_back.setter
    def on_back(self, callback) -> None:
        self._on_back_cb = callback

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Quản lý người dùng")
        title.setStyleSheet(
            f"color:{COLOR_NAVY_DARK};font-size:23px;font-weight:700;"
        )
        self._back_button = QPushButton("← Quay lại")
        self._back_button.setStyleSheet(secondary_button_style(font_size=12))
        self._back_button.clicked.connect(self._handle_back)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._back_button)
        layout.addLayout(header)

        subtitle = QLabel(
            "Danh sách và trạng thái tài khoản; các thao tác cần Controller "
            "quản trị người dùng."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:13px;")
        layout.addWidget(subtitle)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            f"color:{COLOR_ERROR};background:{COLOR_WHITE};"
            "border:1px solid #F1C7C7;border-radius:8px;padding:12px;"
        )
        layout.addWidget(self._status_label)

        controls = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Lọc theo tên, email hoặc vai trò")
        self._search_input.setFixedHeight(38)
        self._search_input.textChanged.connect(self._apply_filter)
        self._refresh_button = QPushButton("Tải lại")
        self._refresh_button.setStyleSheet(secondary_button_style(font_size=12))
        self._refresh_button.clicked.connect(self.refresh)
        self._toggle_active_button = QPushButton("Khoá tài khoản")
        self._toggle_active_button.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._toggle_active_button.clicked.connect(self._toggle_selected_user)
        controls.addWidget(self._search_input, stretch=1)
        controls.addWidget(self._refresh_button)
        controls.addWidget(self._toggle_active_button)
        layout.addLayout(controls)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Mã", "Họ tên", "Email", "Vai trò", "Trạng thái"]
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self._table, stretch=1)

        self._toggle_active_button.setEnabled(False)

    def _set_unavailable(self) -> None:
        self._show_error(
            "Chưa có User Management Controller để tải hoặc thay đổi tài khoản. "
            "Không hiển thị dữ liệu giả; tích hợp Controller trước khi dùng "
            "các thao tác quản trị."
        )
        self._table.setEnabled(False)
        self._search_input.setEnabled(False)
        self._refresh_button.setEnabled(False)
        self._toggle_active_button.setEnabled(False)

    def refresh(self) -> None:
        if self._controller is None:
            self._set_unavailable()
            return

        result = self._controller.list_users()
        self._table.clearContents()
        self._table.setRowCount(0)
        self._users = ()
        if not result.success:
            self._show_error(
                result.message or "Không thể tải danh sách người dùng."
            )
            self._toggle_active_button.setEnabled(False)
            return

        self._users = result.users
        self._status_label.setText(
            f"Đã tải {len(self._users)} tài khoản."
            if self._users
            else "Controller trả về danh sách rỗng."
        )
        self._status_label.setStyleSheet(
            f"color:{COLOR_TEXT_MUTED};background:{COLOR_WHITE};"
            f"border:1px solid {COLOR_LIGHT_GRAY};border-radius:8px;padding:12px;"
        )
        self._table.setRowCount(len(self._users))
        for row, user in enumerate(self._users):
            values = (
                str(user.id),
                user.display_name,
                user.email,
                ROLE_LABELS.get(user.role, user.role),
                "Đã xoá"
                if user.is_deleted
                else "Đang hoạt động"
                if user.is_active
                else "Đã khoá",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, user.id)
                self._table.setItem(row, column, item)
        self._apply_filter(self._search_input.text())
        self._selection_changed()

    def _apply_filter(self, query: str) -> None:
        needle = query.strip().casefold()
        for row in range(self._table.rowCount()):
            searchable = " ".join(
                self._table.item(row, column).text()
                for column in range(1, self._table.columnCount())
                if self._table.item(row, column) is not None
            )
            self._table.setRowHidden(row, needle not in searchable.casefold())

    def _selection_changed(self) -> None:
        row = self._table.currentRow()
        user = self._selected_user(row)
        self._toggle_active_button.setEnabled(
            self._controller is not None
            and user is not None
            and not user.is_deleted
        )
        if user is not None:
            self._toggle_active_button.setText(
                "Tài khoản đã xoá"
                if user.is_deleted
                else "Khoá tài khoản"
                if user.is_active
                else "Mở khoá tài khoản"
            )

    def _selected_user(self, row: int) -> UserModel | None:
        if row < 0:
            return None
        user_id_item = self._table.item(row, 0)
        if user_id_item is None:
            return None
        user_id = user_id_item.data(Qt.ItemDataRole.UserRole)
        return next((user for user in self._users if user.id == user_id), None)

    def _toggle_selected_user(self) -> None:
        if self._controller is None:
            self._set_unavailable()
            return
        user = self._selected_user(self._table.currentRow())
        if user is None:
            self._show_error("Chọn một tài khoản trước khi tiếp tục.")
            return

        if user.is_deleted:
            self._show_error("Không thể thay đổi tài khoản đã xoá.")
            return
        result = self._controller.set_user_active(user.id, not user.is_active)
        if not result.success:
            self._show_error(
                result.message or "Không thể cập nhật trạng thái tài khoản."
            )
            return
        self.refresh()

    def _show_error(self, message: str) -> None:
        self._status_label.setStyleSheet(
            f"color:{COLOR_ERROR};background:{COLOR_WHITE};"
            "border:1px solid #F1C7C7;border-radius:8px;padding:12px;"
        )
        self._status_label.setText(message)

    def _handle_back(self) -> None:
        if self._on_back_cb is not None:
            self._on_back_cb()
