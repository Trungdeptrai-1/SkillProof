import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from client.views.candidate_special_assessment_screen import (
    CandidateSpecialAssessmentScreen,
)
from client.views.certificate_screen import CertificateScreen
from client.views.exam_monitor_screen import ExamMonitorScreen
from client.views.extended_workflow_contracts import (
    ActiveExamSession,
    CandidatePublishedResult,
    CandidateSpecializedAssessment,
    CertificateEntry,
    CertificatePermissions,
    CertificateVerification,
    InterviewEntry,
    PendingGradingSubmission,
    WorkflowActionResult,
    WorkflowListResult,
)
from client.views.grading_screen import GradingScreen
from client.views.interview_screen import InterviewScreen


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


class CandidateSpecializedControllerMock:
    def __init__(self):
        self.assignments = (
            CandidateSpecializedAssessment(
                11,
                "Python coding",
                "coding",
                "Return the sum of two integers.",
                "in_progress",
                30,
                "Two integers.",
                "One integer.",
                ("Input: 2 3\nOutput: 5",),
                ("python3",),
            ),
            CandidateSpecializedAssessment(
                12,
                "Design note",
                "essay",
                "Describe the trade-offs.",
                "released",
                20,
            ),
        )
        self.saved = []
        self.submitted = []

    def list_assignments(self):
        return WorkflowListResult(True, self.assignments)

    def save_answer(self, assignment_id, answer, language):
        self.saved.append((assignment_id, answer, language))
        return WorkflowActionResult(True, "Saved", "in_progress")

    def submit_answer(self, assignment_id, answer, language):
        self.submitted.append((assignment_id, answer, language))
        return WorkflowActionResult(True, "Submitted", "submitted")

    def get_result(self, assignment_id):
        return CandidatePublishedResult(
            True, released=True, score=8, max_score=10, feedback="Good analysis."
        )


class ManualGradingControllerMock:
    def __init__(self):
        self.submission = PendingGradingSubmission(
            25,
            "Candidate QA",
            "Python essay",
            "essay",
            "Explain immutability.",
            "Tuples cannot be changed.",
            "submitted",
            10,
        )
        self.saved = []
        self.released = []

    def list_submissions_for_grading(self):
        return WorkflowListResult(True, (self.submission,))

    def save_grade(self, submission_id, score, feedback):
        self.saved.append((submission_id, score, feedback))
        self.submission = PendingGradingSubmission(
            25,
            "Candidate QA",
            "Python essay",
            "essay",
            "Explain immutability.",
            "Tuples cannot be changed.",
            "graded",
            10,
            feedback=feedback,
            score=score,
        )
        return WorkflowActionResult(True, "Graded", "graded")

    def release_result(self, submission_id):
        self.released.append(submission_id)
        return WorkflowActionResult(True, "Released", "released")


class ExamMonitorControllerMock:
    def get_active_session(self):
        return ActiveExamSession(9, "Assessment QA", "in_progress", 125)


class InterviewControllerMock:
    def __init__(self):
        self.saved = []

    def list_interviews(self):
        return WorkflowListResult(
            True,
            (
                InterviewEntry(
                    7,
                    "Technical interview",
                    "Candidate QA",
                    "2026-11-25 10:00",
                    "scheduled",
                    "https://meet.example.test/session",
                ),
            ),
        )

    def save_evaluation(self, interview_id, notes):
        self.saved.append((interview_id, notes))
        return WorkflowActionResult(True, "Saved")


class CertificateControllerMock:
    def __init__(self):
        self.issued = []

    def get_permissions(self):
        return CertificatePermissions(can_issue=True, can_verify=True)

    def list_certificates(self):
        return WorkflowListResult(
            True,
            (CertificateEntry(4, "SP-004", "Candidate QA", "Python", "active", "2026-11-24"),),
        )

    def issue_certificate(self, user_id, skill_id, score):
        self.issued.append((user_id, skill_id, score))
        return WorkflowActionResult(True, "Issued")

    def verify_certificate(self, cert_code):
        return CertificateVerification(
            True,
            CertificateEntry(4, cert_code, "Candidate QA", "Python", "active", "2026-11-24"),
        )


def _button(widget, text):
    return next(button for button in widget.findChildren(QPushButton) if button.text() == text)


def test_candidate_specialized_assessment_saves_submits_and_gates_results(
    qt_app, monkeypatch
):
    controller = CandidateSpecializedControllerMock()
    screen = CandidateSpecialAssessmentScreen(controller)
    screen._assignments_table.selectRow(0)
    assert screen._public_cases.toPlainText() == "Input: 2 3\nOutput: 5"
    assert screen._language.currentText() == "python3"

    screen._answer.setPlainText("print(sum(map(int, input().split())))")
    screen._save_button.click()
    assert controller.saved == [
        (11, "print(sum(map(int, input().split())))", "python3")
    ]

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    screen._submit_button.click()
    assert controller.submitted[0][0] == 11
    assert not screen._submit_button.isEnabled()
    screen._submit_button.click()
    assert len(controller.submitted) == 1

    screen._assignments_table.selectRow(1)
    assert screen._result_button.isEnabled()
    screen._result_button.click()
    assert "8 / 10" in screen._status.text()
    controller.get_result = lambda _assignment_id: CandidatePublishedResult(
        True, released=False, score=99, max_score=100
    )
    screen._result_button.click()
    assert "99" not in screen._status.text()
    assert "chưa hiển thị điểm" in screen._status.text()
    screen.close()


def test_candidate_specialized_screen_locks_actions_without_controller(qt_app):
    screen = CandidateSpecialAssessmentScreen()
    assert "Chưa có Candidate Controller" in screen._status.text()
    assert not screen._save_button.isEnabled()
    assert not screen._submit_button.isEnabled()
    assert screen._assignments_table.rowCount() == 0
    screen.close()


def test_manual_grading_saves_and_releases_only_after_grade(qt_app, monkeypatch):
    controller = ManualGradingControllerMock()
    screen = GradingScreen(controller)
    screen._table.selectRow(0)
    assert screen._save_grade_button.isEnabled()
    assert not screen._release_button.isEnabled()
    screen._score.setValue(8)
    screen._feedback.setPlainText("Clear answer.")
    screen._save_grade_button.click()
    assert controller.saved == [(25, 8, "Clear answer.")]

    screen._table.selectRow(0)
    assert screen._release_button.isEnabled()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    screen._release_button.click()
    assert controller.released == [25]
    screen.close()


def test_exam_monitor_only_tracks_controller_confirmed_active_session(qt_app):
    unavailable = ExamMonitorScreen()
    assert "Không có giám sát nào được bật" in unavailable._status.text()
    assert not unavailable._start_button.isEnabled()

    screen = ExamMonitorScreen(ExamMonitorControllerMock())
    assert screen._countdown.text() == "02:05"
    screen._start_button.click()
    assert screen._monitoring
    screen.eventFilter(qt_app, QEvent(QEvent.Type.ApplicationDeactivate))
    assert screen._alerts_table.rowCount() == 1
    assert "Camera: không được sử dụng" in screen._camera_status.text()
    screen._stop_monitoring()
    assert not screen._monitoring
    screen.close()
    unavailable.close()


def test_interview_screen_loads_external_link_and_saves_notes(qt_app):
    controller = InterviewControllerMock()
    screen = InterviewScreen("expert", controller)
    screen._table.selectRow(0)
    assert "https://meet.example.test/session" in screen._meeting_link.text()
    screen._evaluation_notes.setPlainText("Strong communication.")
    screen._save_button.click()
    assert controller.saved == [(7, "Strong communication.")]

    candidate_view = InterviewScreen("candidate", controller)
    assert candidate_view._evaluation_notes.isHidden()
    assert not candidate_view._save_button.isVisible()
    screen.close()
    candidate_view.close()


def test_certificate_screen_respects_controller_permissions(qt_app, monkeypatch):
    controller = CertificateControllerMock()
    screen = CertificateScreen("company", controller)
    assert screen._table.item(0, 0).text() == "SP-004"
    screen._user_id.setValue(13)
    screen._skill_id.setValue(6)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    screen._issue_button.click()
    assert controller.issued == [(13, 6, None)]
    screen._verify_code.setText("SP-004")
    screen._verify_button.click()
    assert "Candidate QA" in screen._verification_status.text()

    candidate_view = CertificateScreen("candidate", controller)
    assert candidate_view._management_section.isHidden()
    screen.close()
    candidate_view.close()


def test_candidate_dashboard_navigates_to_extended_screens_with_unavailable_states(
    qt_app, auth, candidate_user, monkeypatch, fresh_db
):
    import app.database.schema as schema
    from app.ui.main_window import MainWindow
    from client.views.dashboard_screen import DashboardScreen

    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    monkeypatch.setattr(DashboardScreen, "_animate_in", lambda self: None)
    login_result = auth.login(*candidate_user)
    assert login_result.success
    window = MainWindow()
    window._show_dashboard(login_result.user)
    dashboard = window._dashboard

    assessment_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Bài tự luận & Coding")
    )
    assessment_button.click()
    assert window._stack.currentWidget() is window._candidate_special_assessments
    assert "Chưa có Candidate Controller" in window._candidate_special_assessments._status.text()
    window._candidate_special_assessments._back_button.click()
    assert window._stack.currentWidget() is dashboard

    monitor_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Giám sát phiên thi")
    )
    monitor_button.click()
    assert window._stack.currentWidget() is window._exam_monitor
    assert not window._exam_monitor._start_button.isEnabled()
    window._exam_monitor._back_button.click()

    interview_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Phỏng vấn")
    )
    interview_button.click()
    assert window._stack.currentWidget() is window._interview_screen
    assert window._interview_screen._table.rowCount() == 0
    window._interview_screen._back_button.click()

    certificate_button = next(
        button
        for button in dashboard.findChildren(QPushButton)
        if button.text().strip().endswith("Chứng chỉ")
    )
    certificate_button.click()
    assert window._stack.currentWidget() is window._certificate_screen
    assert window._certificate_screen._table.rowCount() == 0
    window._certificate_screen._back_button.click()

    window._show_grading()
    assert window._grading_screen is None
    auth.logout()
    window._discard_extended_screens()
    if hasattr(dashboard, "_anim"):
        dashboard._anim.stop()
    window.hide()
    QTest.qWait(450)
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def test_admin_dashboard_navigates_to_locked_certificate_management(
    qt_app, auth, admin_user, monkeypatch
):
    import app.database.schema as schema
    from app.ui.main_window import MainWindow

    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    login_result = auth.login(*admin_user)
    assert login_result.success
    window = MainWindow()
    window._show_dashboard(login_result.user)
    window._dashboard._certificates_nav_button.click()
    assert window._stack.currentWidget() is window._certificate_screen
    assert "Chưa có Certificate Controller" in window._certificate_screen._status.text()
    assert not window._certificate_screen._issue_button.isEnabled()
    window._certificate_screen._back_button.click()
    assert window._stack.currentWidget() is window._dashboard
    auth.logout()
    window._discard_extended_screens()
    window.hide()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
