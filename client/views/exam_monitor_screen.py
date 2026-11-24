"""Local PySide6 focus monitoring for a Controller-confirmed active session."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QDateTime, QEvent, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.utils.constants import COLOR_OFF_WHITE, COLOR_TEXT_MUTED
from app.utils.styles import primary_button_style, secondary_button_style
from client.components.status_banner import StatusBanner
from client.components.workflow_page import add_workflow_header
from client.views.extended_workflow_contracts import (
    ActiveExamSession,
    ExamMonitorController,
)


class ExamMonitorScreen(QWidget):
    """Monitors focus locally only after the Controller reports an active session."""

    def __init__(
        self,
        controller: ExamMonitorController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._on_back_cb: Callable[[], None] | None = None
        self._session: ActiveExamSession | None = None
        self._remaining_seconds = 0
        self._last_tick = 0.0
        self._monitoring = False
        self._monitoring_started = False
        self._application = QApplication.instance()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        self._build_ui()
        if controller is None:
            self._status.set_status(
                "Chưa có Monitor Controller để xác định phiên thi đang hoạt động. "
                "Không có giám sát nào được bật.",
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
            layout, "Giám sát phiên thi", self._handle_back
        )
        self._status = StatusBanner()
        layout.addWidget(self._status)

        self._session_title = QLabel("Chưa có phiên thi đang hoạt động.")
        self._session_title.setStyleSheet("font-size:18px;font-weight:600;")
        self._session_status = QLabel("")
        self._countdown = QLabel("—")
        self._countdown.setStyleSheet("font-size:32px;font-weight:700;")
        for label in (self._session_title, self._session_status, self._countdown):
            layout.addWidget(label)

        controls = QHBoxLayout()
        self._refresh_button = QPushButton("Kiểm tra phiên")
        self._refresh_button.setStyleSheet(secondary_button_style(font_size=12))
        self._refresh_button.clicked.connect(self.refresh)
        self._start_button = QPushButton("Bật theo dõi cửa sổ")
        self._start_button.setStyleSheet(
            primary_button_style(font_size=12, padding="8px 14px")
        )
        self._start_button.clicked.connect(self._start_monitoring)
        self._stop_button = QPushButton("Dừng theo dõi")
        self._stop_button.setStyleSheet(secondary_button_style(font_size=12))
        self._stop_button.clicked.connect(self._stop_monitoring)
        controls.addWidget(self._refresh_button)
        controls.addWidget(self._start_button)
        controls.addWidget(self._stop_button)
        controls.addStretch()
        layout.addLayout(controls)

        self._camera_status = QLabel(
            "Camera: không được sử dụng. Không có video hoặc hình ảnh camera."
        )
        self._camera_status.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        layout.addWidget(self._camera_status)
        self._camera_status.hide()
        self._local_notice = QLabel(
            "Khi bạn xác nhận bật theo dõi, sự kiện mất focus sẽ được lưu vào "
            "SQLite cùng phiên thi. Không ghi hình, thu âm hoặc chụp màn hình."
        )
        self._local_notice.setWordWrap(True)
        self._local_notice.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        layout.addWidget(self._local_notice)
        self._local_notice.hide()
        self._alerts_table = QTableWidget(0, 2)
        self._alerts_table.setHorizontalHeaderLabels(["Thời điểm", "Cảnh báo cục bộ"])
        self._alerts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._alerts_table, stretch=1)
        self._alerts_table.hide()
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(False)
        self._refresh_button.setEnabled(self._controller is not None)

    def refresh(self) -> None:
        if self._monitoring:
            return
        if self._controller is None:
            self._status.set_status(
                "Chưa có Monitor Controller; tính năng không hoạt động.",
                "unavailable",
            )
            return
        session = self._controller.get_active_session()
        self._session = session
        if session is None:
            self._session_title.setText("Chưa có phiên thi đang hoạt động.")
            self._session_status.setText("")
            self._remaining_seconds = 0
            self._countdown.setText("—")
            self._start_button.setEnabled(False)
            self._status.set_status("Không tìm thấy phiên thi đang hoạt động.", "empty")
            return
        self._session_title.setText(session.title)
        self._session_status.setText(f"Trạng thái phiên: {session.status}")
        self._remaining_seconds = max(0, session.remaining_seconds)
        self._update_countdown()
        can_start = session.status == "in_progress" and self._remaining_seconds > 0
        self._start_button.setEnabled(can_start and not self._monitoring)
        self._status.set_status(
            "Phiên đã xác nhận. Theo dõi focus chỉ chạy trên thiết bị này."
            if can_start
            else "Phiên chưa ở trạng thái có thể theo dõi.",
            "info" if can_start else "unavailable",
        )

    def _start_monitoring(self) -> None:
        if (
            self._controller is None
            or self._session is None
            or self._session.status != "in_progress"
            or self._remaining_seconds <= 0
            or self._monitoring
            or self._application is None
        ):
            return
        confirmation = QMessageBox.question(
            self,
            "Lưu sự kiện focus",
            "Ứng dụng sẽ ghi thời điểm cửa sổ mất focus vào SQLite cùng phiên "
            "thi. Không sử dụng camera, video hoặc ảnh bằng chứng. Tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        started = self._controller.start_monitoring(self._session.id)
        if not started.success:
            self._status.set_status(
                started.message or "Không thể bắt đầu ghi nhận focus.", "error"
            )
            return
        self._monitoring = True
        self._monitoring_started = True
        self._last_tick = time.monotonic()
        self._application.installEventFilter(self)
        self._timer.start()
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self._refresh_button.setEnabled(False)
        self._camera_status.show()
        self._local_notice.show()
        self._alerts_table.show()
        self._status.set_status(
            "Theo dõi focus cục bộ đang bật cho phiên thi đã xác nhận.",
            "success",
        )

    def _tick(self) -> None:
        now = time.monotonic()
        elapsed = max(1, int(now - self._last_tick))
        self._last_tick = now
        self._remaining_seconds = max(0, self._remaining_seconds - elapsed)
        self._update_countdown()
        if self._remaining_seconds == 0:
            if self._controller is not None and self._session is not None:
                timeout = self._controller.record_timeout(self._session.id)
                if not timeout.success:
                    self._status.set_status(timeout.message, "error")
            self._stop_monitoring()
            self._status.set_status(
                "Đã hết thời gian theo dõi cục bộ. Hãy kiểm tra trạng thái nộp "
                "qua Controller.",
                "info",
            )

    def _update_countdown(self) -> None:
        minutes, seconds = divmod(self._remaining_seconds, 60)
        self._countdown.setText(f"{minutes:02d}:{seconds:02d}")

    def eventFilter(self, watched, event):  # noqa: N802
        if (
            self._monitoring
            and event.type() == QEvent.Type.ApplicationDeactivate
        ):
            self._record_focus_alert()
        return super().eventFilter(watched, event)

    def _record_focus_alert(self) -> None:
        if not self._monitoring:
            return
        if self._controller is None or self._session is None:
            return
        result = self._controller.record_focus_lost(self._session.id)
        if not result.success:
            self._status.set_status(
                result.message or "Không thể lưu sự kiện focus vào SQLite.", "error"
            )
            return
        row = self._alerts_table.rowCount()
        self._alerts_table.insertRow(row)
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self._alerts_table.setItem(row, 0, QTableWidgetItem(timestamp))
        self._alerts_table.setItem(
            row, 1, QTableWidgetItem("Ứng dụng mất focus hoặc bị thu nhỏ")
        )
        self._status.set_status(
            "Sự kiện mất focus đã được lưu vào SQLite.",
            "error",
        )

    def _stop_monitoring(self, *, finish_session: bool = True) -> None:
        was_monitoring = self._monitoring
        if self._monitoring and self._application is not None:
            self._application.removeEventFilter(self)
        self._timer.stop()
        self._monitoring = False
        if (
            was_monitoring
            and finish_session
            and self._controller is not None
            and self._session is not None
        ):
            result = self._controller.stop_monitoring(self._session.id)
            if not result.success:
                self._status.set_status(
                    result.message or "Không thể kết thúc phiên giám sát.", "error"
                )
        self._stop_button.setEnabled(False)
        self._refresh_button.setEnabled(self._controller is not None)
        if not self._monitoring_started:
            self._camera_status.hide()
            self._local_notice.hide()
            self._alerts_table.hide()
        self._start_button.setEnabled(
            self._session is not None
            and self._session.status == "in_progress"
            and self._remaining_seconds > 0
            and self._controller is not None
        )

    def hideEvent(self, event):  # noqa: N802
        self._stop_monitoring(finish_session=False)
        super().hideEvent(event)

    def _handle_back(self) -> None:
        self._stop_monitoring(finish_session=False)
        if self._on_back_cb is not None:
            self._on_back_cb()
