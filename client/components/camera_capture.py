"""Qt Multimedia camera capture used by the exam-monitoring view."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import (
    QCamera,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaRecorder,
)
from PySide6.QtMultimediaWidgets import QVideoWidget


@dataclass(frozen=True)
class CameraDeviceOption:
    device_id: bytes
    description: str


class CameraCaptureBackend(QObject):
    state_changed = Signal(str, str)
    recording_changed = Signal(bool)

    def available_devices(self) -> tuple[CameraDeviceOption, ...]:
        raise NotImplementedError

    def start(self, device_id: bytes, video_widget: QVideoWidget) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def start_recording(self, output_path: str) -> None:
        raise NotImplementedError

    def stop_recording(self) -> None:
        raise NotImplementedError

    @property
    def is_active(self) -> bool:
        raise NotImplementedError

    @property
    def is_recording(self) -> bool:
        raise NotImplementedError


class QtCameraCaptureBackend(CameraCaptureBackend):
    """Owns the real camera and recorder; construction does not activate either."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._devices: QMediaDevices | None = None
        self._camera: QCamera | None = None
        self._capture_session: QMediaCaptureSession | None = None
        self._recorder: QMediaRecorder | None = None

    def available_devices(self) -> tuple[CameraDeviceOption, ...]:
        if self._devices is None:
            self._devices = QMediaDevices(self)
            self._devices.videoInputsChanged.connect(self._devices_changed)
        return tuple(
            CameraDeviceOption(bytes(device.id()), device.description())
            for device in QMediaDevices.videoInputs()
        )

    def start(self, device_id: bytes, video_widget: QVideoWidget) -> None:
        self.stop()
        device = next(
            (
                item
                for item in QMediaDevices.videoInputs()
                if bytes(item.id()) == device_id
            ),
            None,
        )
        if device is None:
            self.state_changed.emit("disconnected", "Camera không còn khả dụng.")
            return

        capture_session = QMediaCaptureSession(self)
        camera = QCamera(device, self)
        recorder = QMediaRecorder(self)
        capture_session.setCamera(camera)
        capture_session.setRecorder(recorder)
        capture_session.setVideoOutput(video_widget)
        camera.activeChanged.connect(self._camera_active_changed)
        camera.errorOccurred.connect(self._camera_error)
        recorder.recorderStateChanged.connect(self._recorder_state_changed)
        recorder.errorOccurred.connect(self._recorder_error)
        self._capture_session = capture_session
        self._camera = camera
        self._recorder = recorder
        self.state_changed.emit("connecting", "Đang kết nối camera...")
        camera.start()

    def stop(self) -> None:
        self.stop_recording()
        camera = self._camera
        capture_session = self._capture_session
        recorder = self._recorder
        self._camera = None
        self._capture_session = None
        self._recorder = None
        if camera is not None:
            camera.stop()
        if capture_session is not None:
            capture_session.setVideoOutput(None)
            capture_session.setRecorder(None)
            capture_session.setCamera(None)
            capture_session.deleteLater()
        if recorder is not None:
            recorder.deleteLater()
        if camera is not None:
            camera.deleteLater()
        self.state_changed.emit("off", "Camera đã tắt.")

    def start_recording(self, output_path: str) -> None:
        if (
            self._camera is None
            or not self._camera.isActive()
            or self._recorder is None
        ):
            raise RuntimeError("Camera chưa hoạt động.")
        media_format = QMediaFormat()
        media_format.setFileFormat(QMediaFormat.FileFormat.MPEG4)
        if not media_format.isSupported(QMediaFormat.ConversionMode.Encode):
            raise RuntimeError("Thiết bị không hỗ trợ mã hóa video MPEG-4.")
        self._recorder.setMediaFormat(media_format)
        if not self._recorder.setOutputLocation(QUrl.fromLocalFile(output_path)):
            raise RuntimeError("Không thể thiết lập đường dẫn lưu video.")
        self._recorder.record()

    def stop_recording(self) -> None:
        if self._recorder is not None and self.is_recording:
            self._recorder.stop()

    @property
    def is_active(self) -> bool:
        return self._camera is not None and self._camera.isActive()

    @property
    def is_recording(self) -> bool:
        return (
            self._recorder is not None
            and self._recorder.recorderState()
            == QMediaRecorder.RecorderState.RecordingState
        )

    def _camera_active_changed(self, active: bool) -> None:
        if active:
            self.state_changed.emit("active", "Camera đang hoạt động.")
        elif self._camera is not None:
            self.state_changed.emit("off", "Camera đã tắt.")

    def _camera_error(self, _error: QCamera.Error, message: str) -> None:
        self.stop()
        self.state_changed.emit(
            "error", message or "Camera gặp lỗi kỹ thuật; không kết luận vi phạm."
        )

    def _recorder_state_changed(
        self, state: QMediaRecorder.RecorderState
    ) -> None:
        self.recording_changed.emit(
            state == QMediaRecorder.RecorderState.RecordingState
        )

    def _recorder_error(
        self, _error: QMediaRecorder.Error, message: str
    ) -> None:
        self.recording_changed.emit(False)
        self.state_changed.emit(
            "recording_error",
            message or "Không thể ghi video; phiên camera vẫn có thể tiếp tục.",
        )

    def _devices_changed(self) -> None:
        if self._camera is None:
            return
        connected_ids = {
            bytes(device.id()) for device in QMediaDevices.videoInputs()
        }
        if bytes(self._camera.cameraDevice().id()) not in connected_ids:
            self.stop()
            self.state_changed.emit(
                "disconnected", "Camera bị ngắt kết nối; không kết luận vi phạm."
            )
