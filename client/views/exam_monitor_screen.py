"""Local PySide6 focus monitoring for a Controller-confirmed active session."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QDateTime, QEvent, Qt, QTimer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.utils.constants import COLOR_OFF_WHITE, COLOR_TEXT_MUTED
from app.utils.styles import primary_button_style, secondary_button_style
from client.components.camera_capture import (
    CameraCaptureBackend,
    CameraDeviceOption,
    QtCameraCaptureBackend,
)
from client.components.status_banner import StatusBanner
from client.components.workflow_page import add_workflow_header
from client.views.extended_workflow_contracts import (
    ActiveExamSession,
    CameraRecordingPathProvider,
    ExamMonitorController,
)


class ExamMonitorScreen(QWidget):
    """Monitors confirmed sessions; camera and recording require separate consent."""

    def __init__(
        self,
        controller: ExamMonitorController | None = None,
        parent: QWidget | None = None,
        *,
        camera_backend: CameraCaptureBackend | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._camera_backend = camera_backend or QtCameraCaptureBackend(self)
        self._camera_devices: tuple[CameraDeviceOption, ...] = ()
        self._camera_state = "off"
        self._camera_unavailable_reported = False
        self._on_back_cb: Callable[[], None] | None = None
        self._session: ActiveExamSession | None = None
        self._remaining_seconds = 0
        self._last_tick = 0.0
        self._monitoring = False
        self._alert_count = 0
        self._application = QApplication.instance()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self.setStyleSheet(f"background:{COLOR_OFF_WHITE};")
        self._build_ui()
        self._camera_backend.state_changed.connect(self._camera_state_changed)
        self._camera_backend.recording_changed.connect(self._recording_state_changed)
        self._update_record_controls()
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

        self._alert_count_label = QLabel("Cảnh báo đã ghi: 0")
        layout.addWidget(self._alert_count_label)

        self._camera_status = QLabel("Camera: chưa bật.")
        self._camera_status.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        layout.addWidget(self._camera_status)
        self._camera_preview = QVideoWidget()
        self._camera_preview.setStyleSheet("background:#101820;")
        self._camera_placeholder = QLabel(
            "Hình ảnh camera chỉ xuất hiện sau khi bạn đồng ý bật camera."
        )
        self._camera_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_placeholder.setWordWrap(True)
        self._camera_placeholder.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        self._camera_preview_stack = QStackedWidget()
        self._camera_preview_stack.setMinimumHeight(150)
        self._camera_preview_stack.addWidget(self._camera_placeholder)
        self._camera_preview_stack.addWidget(self._camera_preview)
        layout.addWidget(self._camera_preview_stack)
        camera_controls = QHBoxLayout()
        self._camera_device = QComboBox()
        self._camera_start_button = QPushButton("Bật camera")
        self._camera_start_button.setStyleSheet(
            secondary_button_style(font_size=12)
        )
        self._camera_start_button.clicked.connect(self._start_camera)
        self._camera_stop_button = QPushButton("Tắt camera")
        self._camera_stop_button.setStyleSheet(
            secondary_button_style(font_size=12)
        )
        self._camera_stop_button.clicked.connect(self._stop_camera)
        self._record_button = QPushButton("Ghi video")
        self._record_button.setStyleSheet(
            secondary_button_style(font_size=12)
        )
        self._record_button.clicked.connect(self._start_recording)
        self._stop_record_button = QPushButton("Dừng ghi")
        self._stop_record_button.setStyleSheet(
            secondary_button_style(font_size=12)
        )
        self._stop_record_button.clicked.connect(self._stop_recording)
        self._record_status = QLabel(
            "Ghi hình chưa khả dụng: Controller chưa cấp đường dẫn lưu video."
        )
        self._record_status.setWordWrap(True)
        self._record_status.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        camera_controls.addWidget(self._camera_device)
        camera_controls.addWidget(self._camera_start_button)
        camera_controls.addWidget(self._camera_stop_button)
        camera_controls.addWidget(self._record_button)
        camera_controls.addWidget(self._stop_record_button)
        layout.addLayout(camera_controls)
        layout.addWidget(self._record_status)
        self._local_notice = QLabel(
            "Theo dõi focus chỉ bắt đầu sau khi bạn xác nhận. Camera tách biệt "
            "và chỉ bật sau consent riêng; lỗi camera là cảnh báo kỹ thuật, "
            "không phải kết luận gian lận. Ghi video cần consent riêng và "
            "đường dẫn do Controller cung cấp."
        )
        self._local_notice.setWordWrap(True)
        self._local_notice.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        layout.addWidget(self._local_notice)
        self._local_notice.hide()
        self._alerts_table = QTableWidget(0, 2)
        self._alerts_table.setHorizontalHeaderLabels(["Thời điểm", "Cảnh báo cục bộ"])
        self._alerts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._alerts_table, stretch=1)
        self._alerts_table.setMinimumHeight(70)
        self._alerts_table.hide()
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(False)
        self._camera_device.setEnabled(False)
        self._camera_start_button.setEnabled(False)
        self._camera_stop_button.setEnabled(False)
        self._record_button.setEnabled(False)
        self._stop_record_button.setEnabled(False)
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
        previous_session = self._session
        self._session = session
        if session is None:
            self._timer.stop()
            if self._camera_state in {"connecting", "active"}:
                self._stop_camera()
            self._session_title.setText("Chưa có phiên thi đang hoạt động.")
            self._session_status.setText("")
            self._remaining_seconds = 0
            self._countdown.setText("—")
            self._start_button.setEnabled(False)
            self._camera_start_button.setEnabled(False)
            self._status.set_status("Không tìm thấy phiên thi đang hoạt động.", "empty")
            return
        self._session_title.setText(session.title)
        self._session_status.setText(f"Trạng thái phiên: {session.status}")
        self._remaining_seconds = max(0, session.remaining_seconds)
        self._update_countdown()
        can_start = session.status == "in_progress" and self._remaining_seconds > 0
        if (
            self._camera_state in {"connecting", "active"}
            and (
                not can_start
                or (
                    previous_session is not None
                    and previous_session.id != session.id
                )
            )
        ):
            self._stop_camera()
        camera_busy = self._camera_state in {"connecting", "active"}
        self._start_button.setEnabled(
            can_start and not self._monitoring
        )
        self._camera_start_button.setEnabled(
            can_start and not camera_busy
        )
        self._camera_device.setEnabled(
            bool(self._camera_devices) and not camera_busy
        )
        if can_start and self.isVisible():
            self._last_tick = time.monotonic()
            self._timer.start()
        elif not can_start:
            self._timer.stop()
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
            "thi. Thao tác này chỉ bật theo dõi focus; camera và ghi video "
            "có consent riêng. Tiếp tục?",
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
            self._timer.stop()
            if (
                self._monitoring
                and self._controller is not None
                and self._session is not None
            ):
                timeout = self._controller.record_timeout(self._session.id)
                if not timeout.success:
                    self._status.set_status(timeout.message, "error")
                else:
                    self._append_alert("Hết thời gian phiên thi")
            self._stop_monitoring()
            self._stop_camera()
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
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self._append_alert("Ứng dụng mất focus hoặc bị thu nhỏ", timestamp)
        self._status.set_status(
            "Sự kiện mất focus đã được lưu vào SQLite.",
            "error",
        )

    def _append_alert(self, message: str, timestamp: str | None = None) -> None:
        row = self._alerts_table.rowCount()
        self._alerts_table.insertRow(row)
        self._alerts_table.setItem(
            row,
            0,
            QTableWidgetItem(
                timestamp
                or QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            ),
        )
        self._alerts_table.setItem(row, 1, QTableWidgetItem(message))
        self._alert_count += 1
        self._alert_count_label.setText(f"Cảnh báo đã ghi: {self._alert_count}")

    def _start_camera(self) -> None:
        if (
            self._session is None
            or self._session.status != "in_progress"
            or self._remaining_seconds <= 0
            or self._camera_backend.is_active
        ):
            return
        confirmation = QMessageBox.question(
            self,
            "Cho phép sử dụng camera",
            "Camera sẽ được bật để hiển thị trực tiếp trên màn hình phiên thi. "
            "Hình ảnh không được gửi đi hoặc ghi lại nếu bạn không chấp thuận "
            "riêng việc ghi video. Bật camera?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        try:
            self._camera_devices = self._camera_backend.available_devices()
        except (OSError, RuntimeError) as error:
            self._camera_state_changed(
                "error", f"Không thể truy cập danh sách camera: {error}"
            )
            return
        self._camera_device.clear()
        for device in self._camera_devices:
            self._camera_device.addItem(device.description, device.device_id)
        if not self._camera_devices:
            self._camera_state_changed(
                "disconnected",
                "Không tìm thấy camera. Đây là cảnh báo kỹ thuật, không phải "
                "kết luận vi phạm.",
            )
            return
        device_index = self._camera_device.currentIndex()
        if not 0 <= device_index < len(self._camera_devices):
            self._camera_state_changed(
                "error", "Không xác định được camera đã chọn."
            )
            return
        device_id = self._camera_devices[device_index].device_id
        try:
            self._camera_backend.start(device_id, self._camera_preview)
        except (OSError, RuntimeError, ValueError) as error:
            self._camera_state_changed(
                "error",
                f"Không thể bật camera: {error}. Không kết luận vi phạm.",
            )

    def _stop_camera(self) -> None:
        if (
            self._camera_state == "off"
            and not self._camera_backend.is_active
            and not self._camera_backend.is_recording
        ):
            return
        self._camera_backend.stop()

    def _camera_state_changed(self, state: str, message: str) -> None:
        if (
            state in {"error", "disconnected"}
            and "không kết luận" not in message.lower()
        ):
            message = f"{message} Đây là cảnh báo kỹ thuật, không kết luận vi phạm."
        self._set_camera_state(state, message)
        if state == "active":
            self._camera_unavailable_reported = False
            self._camera_preview_stack.setCurrentWidget(self._camera_preview)
            self._camera_start_button.setEnabled(False)
            self._camera_stop_button.setEnabled(True)
            self._camera_device.setEnabled(False)
            self._update_record_controls()
            return
        if state == "connecting":
            self._camera_start_button.setEnabled(False)
            self._camera_stop_button.setEnabled(True)
            self._camera_device.setEnabled(False)
            self._update_record_controls()
        elif state in {"error", "disconnected"}:
            self._camera_preview_stack.setCurrentWidget(self._camera_placeholder)
            self._camera_stop_button.setEnabled(False)
            self._camera_start_button.setEnabled(
                self._session is not None
                and self._session.status == "in_progress"
                and self._remaining_seconds > 0
            )
            self._camera_device.setEnabled(bool(self._camera_devices))
            self._report_camera_unavailable()
            self._update_record_controls()
        elif state == "recording_error":
            if self._camera_backend.is_active:
                self._camera_preview_stack.setCurrentWidget(self._camera_preview)
            self._update_record_controls()
        elif state == "off":
            self._camera_preview_stack.setCurrentWidget(self._camera_placeholder)
            self._camera_stop_button.setEnabled(False)
            self._camera_start_button.setEnabled(
                self._session is not None
                and self._session.status == "in_progress"
                and self._remaining_seconds > 0
            )
            self._camera_device.setEnabled(bool(self._camera_devices))
            self._update_record_controls()

    def _set_camera_state(self, state: str, message: str) -> None:
        self._camera_state = state
        labels = {
            "connecting": "đang kết nối",
            "active": "đang hoạt động",
            "disconnected": "mất kết nối",
            "error": "lỗi",
            "recording_error": "lỗi ghi hình",
            "off": "đã tắt",
        }
        label = labels.get(state, state)
        self._camera_status.setText(f"Camera: {label}. {message}".strip())

    def _report_camera_unavailable(self) -> None:
        if (
            self._camera_unavailable_reported
            or not self._monitoring
            or self._controller is None
            or self._session is None
        ):
            return
        self._camera_unavailable_reported = True
        result = self._controller.record_camera_unavailable(self._session.id)
        if result.success:
            self._append_alert("Camera gặp sự cố kỹ thuật")
        else:
            self._status.set_status(
                "Camera gặp sự cố kỹ thuật; Controller chưa xác nhận đã lưu "
                f"cảnh báo: {result.message}",
                "error",
            )

    def _start_recording(self) -> None:
        if (
            self._controller is None
            or self._session is None
            or not self._camera_backend.is_active
            or not isinstance(self._controller, CameraRecordingPathProvider)
            or self._camera_backend.is_recording
        ):
            return
        try:
            output_path = self._controller.get_video_recording_path(
                self._session.id
            )
        except (OSError, ValueError) as error:
            self._record_status.setText(f"Không thể lấy đường dẫn ghi video: {error}")
            return
        if not isinstance(output_path, str) or not output_path.strip():
            self._record_status.setText(
                "Ghi hình chưa khả dụng: Controller chưa cấp đường dẫn lưu video."
            )
            return
        path = Path(output_path).expanduser()
        if (
            not path.is_absolute()
            or path.suffix.lower() != ".mp4"
            or not path.parent.is_dir()
            or not os.access(path.parent, os.W_OK)
            or path.exists()
            or path.is_symlink()
        ):
            self._record_status.setText(
                "Controller trả về đường dẫn video không hợp lệ hoặc có thể "
                "ghi đè tệp hiện có; không bắt đầu ghi."
            )
            return
        confirmation = QMessageBox.question(
            self,
            "Đồng ý ghi video",
            "Video sẽ được ghi cục bộ vào:\n"
            f"{path}\n\nBản ghi chỉ bắt đầu sau khi bạn đồng ý. Tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        try:
            self._camera_backend.start_recording(str(path))
        except (OSError, RuntimeError, ValueError) as error:
            self._record_status.setText(f"Không thể bắt đầu ghi video: {error}")

    def _recording_state_changed(self, recording: bool) -> None:
        self._record_status.setText(
            "Đang ghi video cục bộ sau khi bạn đồng ý."
            if recording
            else "Không ghi video."
        )
        self._stop_record_button.setEnabled(recording)
        self._update_record_controls()

    def _stop_recording(self) -> None:
        if self._camera_backend.is_recording:
            self._camera_backend.stop_recording()

    def _update_record_controls(self) -> None:
        has_recording_path = isinstance(
            self._controller, CameraRecordingPathProvider
        )
        can_record = (
            has_recording_path
            and self._camera_backend.is_active
            and not self._camera_backend.is_recording
        )
        self._record_button.setEnabled(can_record)
        self._stop_record_button.setEnabled(self._camera_backend.is_recording)
        if not has_recording_path:
            self._record_status.setText(
                "Ghi hình chưa khả dụng: Controller chưa cấp đường dẫn lưu video."
            )
        elif self._camera_backend.is_recording:
            self._record_status.setText(
                "Đang ghi video cục bộ sau khi bạn đồng ý."
            )
        elif self._camera_backend.is_active:
            self._record_status.setText(
                "Có thể bắt đầu ghi sau khi bạn đồng ý riêng."
            )
        else:
            self._record_status.setText(
                "Ghi video chỉ khả dụng sau khi bật camera và xác nhận consent."
            )

    def _stop_monitoring(self, *, finish_session: bool = True) -> None:
        was_monitoring = self._monitoring
        if self._monitoring and self._application is not None:
            self._application.removeEventFilter(self)
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
        self._start_button.setEnabled(
            self._session is not None
            and self._session.status == "in_progress"
            and self._remaining_seconds > 0
            and self._controller is not None
        )

    def hideEvent(self, event):  # noqa: N802
        self._timer.stop()
        self._stop_monitoring(finish_session=False)
        self._stop_camera()
        super().hideEvent(event)

    def closeEvent(self, event):  # noqa: N802
        self._timer.stop()
        self._stop_monitoring(finish_session=False)
        self._stop_camera()
        super().closeEvent(event)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if self._controller is not None:
            self.refresh()

    def _handle_back(self) -> None:
        self._timer.stop()
        self._stop_monitoring(finish_session=False)
        self._stop_camera()
        if self._on_back_cb is not None:
            self._on_back_cb()
