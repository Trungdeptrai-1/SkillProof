"""Certificate screen only exposes actions allowed by the current Controller."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from client.views.certificate_screen import CertificateScreen
from client.views.extended_workflow_contracts import (
    CertificatePermissions,
    WorkflowListResult,
)


class VerifyOnlyController:
    def get_permissions(self):
        return CertificatePermissions(can_issue=False, can_verify=True)

    def list_certificates(self):
        return WorkflowListResult(True, items=())


def test_company_verification_hides_unauthorized_issuance():
    app = QApplication.instance() or QApplication([])
    screen = CertificateScreen("company", VerifyOnlyController())
    assert screen._issue_panel.isHidden()
    assert not screen._verify_panel.isHidden()
    assert not screen._management_section.isHidden()
    assert not screen._issue_button.isEnabled()
    screen.close()
    screen.deleteLater()
    app.processEvents()


def test_candidate_sees_only_their_certificates():
    app = QApplication.instance() or QApplication([])
    screen = CertificateScreen("candidate", VerifyOnlyController())
    assert screen._management_section.isHidden()
    screen.close()
    screen.deleteLater()
    app.processEvents()
