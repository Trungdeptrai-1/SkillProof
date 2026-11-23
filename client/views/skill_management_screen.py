"""Admin skill-catalog view with an injectable Controller contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.utils.constants import (
    COLOR_ERROR,
    COLOR_LIGHT_GRAY,
    COLOR_NAVY_DARK,
    COLOR_OFF_WHITE,
    COLOR_TEXT_MUTED,
    COLOR_WHITE,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from app.utils.styles import primary_button_style, secondary_button_style
from server.models.skill_model import SkillModel

SKILL_LEVELS = ("beginner", "intermediate", "advanced", "expert")


@dataclass(frozen=True)
class SkillListResult:
    success: bool
    skills: tuple[SkillModel, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class SkillActionResult:
    success: bool
    skill: SkillModel | None = None
    message: str = ""


class SkillManagementController(Protocol):
    """Expected API for a future skill-catalog Controller."""

    def list_skills(self) -> SkillListResult: ...

    def create_skill(
        self, name: str, category: str, level: str, description: str
    ) -> SkillActionResult: ...

    def update_skill(
        self,
        skill_id: int,
        name: str,
        category: str,
        level: str,
        description: str,
    ) -> SkillActionResult: ...

    def set_skill_active(
        self, skill_id: int, is_active: bool
    ) -> SkillActionResult: ...


class SkillManagementScreen(QWidget):
    """Edit a skill catalog only when the host injects a real Controller."""

    def __init__(
        self,
        controller: SkillManagementController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._controller = controller
        self._on_back_cb = None
        self._skills: tuple[SkillModel, ...] = ()
        self._editing_skill_id: int | None = None
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
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Quản lý danh mục kỹ năng")
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
            "Danh mục có trong schema SQLite; chưa có Skill Controller để "
            "đọc hoặc lưu dữ liệu thật."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-size:13px;")
        layout.addWidget(subtitle)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            f"color:{COLOR_ERROR};background:{COLOR_WHITE};"
            "border:1px solid #F1C7C7;border-radius:8px;padding:10px;"
        )
        layout.addWidget(self._status_label)

        content = QHBoxLayout()
        content.setSpacing(16)
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Mã", "Tên kỹ năng", "Danh mục", "Cấp độ", "Trạng thái"]
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
        content.addWidget(self._table, stretch=3)

        form = QWidget()
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(16, 12, 16, 12)
        form_layout.setSpacing(10)
        form.setStyleSheet(
            f"background:{COLOR_WHITE};border:1px solid {COLOR_LIGHT_GRAY};"
            "border-radius:10px;"
        )
        form_layout.addWidget(QLabel("Thông tin kỹ năng"))
        fields = QFormLayout()
        self._name_input = QLineEdit()
        self._category_input = QLineEdit()
        self._level_combo = QComboBox()
        for level in SKILL_LEVELS:
            self._level_combo.addItem(level.title(), level)
        self._description_input = QTextEdit()
        self._description_input.setMaximumHeight(100)
        fields.addRow("Tên *", self._name_input)
        fields.addRow("Danh mục", self._category_input)
        fields.addRow("Cấp độ", self._level_combo)
        fields.addRow("Mô tả", self._description_input)
        form_layout.addLayout(fields)

        self._save_button = QPushButton("Thêm kỹ năng")
        self._save_button.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._save_button.clicked.connect(self._save_skill)
        self._edit_button = QPushButton("Sửa mục đã chọn")
        self._edit_button.setStyleSheet(secondary_button_style(font_size=12))
        self._edit_button.clicked.connect(self._begin_edit)
        self._toggle_active_button = QPushButton("Ngừng sử dụng")
        self._toggle_active_button.setStyleSheet(secondary_button_style(font_size=12))
        self._toggle_active_button.clicked.connect(self._toggle_active)
        self._clear_button = QPushButton("Xoá biểu mẫu")
        self._clear_button.setStyleSheet(secondary_button_style(font_size=12))
        self._clear_button.clicked.connect(self._clear_form)
        self._refresh_button = QPushButton("Tải lại danh sách")
        self._refresh_button.setStyleSheet(secondary_button_style(font_size=12))
        self._refresh_button.clicked.connect(self.refresh)
        for button in (
            self._save_button,
            self._edit_button,
            self._toggle_active_button,
            self._clear_button,
            self._refresh_button,
        ):
            form_layout.addWidget(button)
        form_layout.addStretch()
        content.addWidget(form, stretch=2)
        layout.addLayout(content, stretch=1)
        self._edit_button.setEnabled(False)
        self._toggle_active_button.setEnabled(False)

    def _set_unavailable(self) -> None:
        self._show_error(
            "Skill Management Controller chưa được cung cấp. Các thao tác "
            "được khoá và danh sách không chứa dữ liệu giả."
        )
        self._table.setEnabled(False)
        for widget in (
            self._name_input,
            self._category_input,
            self._level_combo,
            self._description_input,
            self._save_button,
            self._edit_button,
            self._toggle_active_button,
            self._clear_button,
            self._refresh_button,
        ):
            widget.setEnabled(False)

    def refresh(self) -> None:
        if self._controller is None:
            self._set_unavailable()
            return

        result = self._controller.list_skills()
        self._skills = ()
        self._table.clearContents()
        self._table.setRowCount(0)
        if not result.success:
            self._show_error(
                result.message or "Không thể tải danh mục kỹ năng."
            )
            return

        self._skills = result.skills
        self._status_label.setStyleSheet(
            f"color:{COLOR_TEXT_MUTED};background:{COLOR_WHITE};"
            f"border:1px solid {COLOR_LIGHT_GRAY};border-radius:8px;padding:10px;"
        )
        self._status_label.setText(
            f"Đã tải {len(self._skills)} kỹ năng."
            if self._skills
            else "Danh mục kỹ năng đang trống."
        )
        self._table.setRowCount(len(self._skills))
        for row, skill in enumerate(self._skills):
            values = (
                str(skill.id),
                skill.name,
                skill.category or "",
                skill.level.title(),
                "Đang dùng" if skill.is_active else "Ngừng dùng",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, skill.id)
                self._table.setItem(row, column, item)
        self._selection_changed()

    def _selected_skill(self) -> SkillModel | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        skill_id = item.data(Qt.ItemDataRole.UserRole)
        return next((skill for skill in self._skills if skill.id == skill_id), None)

    def _selection_changed(self) -> None:
        skill = self._selected_skill()
        enabled = self._controller is not None and skill is not None
        self._edit_button.setEnabled(enabled)
        self._toggle_active_button.setEnabled(enabled)
        if skill is not None:
            self._toggle_active_button.setText(
                "Ngừng sử dụng" if skill.is_active else "Kích hoạt"
            )

    def _begin_edit(self) -> None:
        skill = self._selected_skill()
        if skill is None:
            return
        self._editing_skill_id = skill.id
        self._name_input.setText(skill.name)
        self._category_input.setText(skill.category or "")
        index = self._level_combo.findData(skill.level)
        if index >= 0:
            self._level_combo.setCurrentIndex(index)
        self._description_input.setPlainText(skill.description or "")
        self._save_button.setText("Lưu thay đổi")

    def _save_skill(self) -> None:
        if self._controller is None:
            self._set_unavailable()
            return
        name = self._name_input.text().strip()
        if not name:
            self._show_error("Tên kỹ năng không được để trống.")
            return
        category = self._category_input.text().strip()
        level = self._level_combo.currentData()
        description = self._description_input.toPlainText().strip()
        if not level:
            self._show_error("Chọn cấp độ kỹ năng hợp lệ.")
            return
        if self._editing_skill_id is None:
            result = self._controller.create_skill(
                name, category, level, description
            )
        else:
            result = self._controller.update_skill(
                self._editing_skill_id, name, category, level, description
            )
        if not result.success:
            self._show_error(
                result.message or "Không thể lưu kỹ năng."
            )
            return
        self._editing_skill_id = None
        self._clear_form()
        self.refresh()

    def _toggle_active(self) -> None:
        skill = self._selected_skill()
        if self._controller is None or skill is None:
            return
        result = self._controller.set_skill_active(
            skill.id, not skill.is_active
        )
        if not result.success:
            self._show_error(
                result.message or "Không thể cập nhật kỹ năng."
            )
            return
        self.refresh()

    def _show_error(self, message: str) -> None:
        self._status_label.setStyleSheet(
            f"color:{COLOR_ERROR};background:{COLOR_WHITE};"
            "border:1px solid #F1C7C7;border-radius:8px;padding:10px;"
        )
        self._status_label.setText(message)

    def _clear_form(self) -> None:
        self._editing_skill_id = None
        self._name_input.clear()
        self._category_input.clear()
        self._level_combo.setCurrentIndex(0)
        self._description_input.clear()
        self._save_button.setText("Thêm kỹ năng")

    def _handle_back(self) -> None:
        if self._on_back_cb is not None:
            self._on_back_cb()
