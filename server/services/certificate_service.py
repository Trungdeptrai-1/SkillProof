"""Certificate issue, verification, listing, and revocation workflows."""

from __future__ import annotations

import logging
import math
import secrets
import sqlite3
from datetime import datetime
from typing import Protocol

from app.services.auth_service import SessionManager
from server.services.workflow_result import Record, WorkflowResult

logger = logging.getLogger(__name__)


class CertificateModel(Protocol):
    def get_approved_assessment(self, candidate_id: int, skill_id: int) -> Record | None: ...

    def get_account_role(self, user_id: int) -> str | None: ...

    def is_active_candidate(self, candidate_id: int) -> bool: ...

    def get_certificate_for_candidate(
        self, candidate_id: int, skill_id: int
    ) -> Record | None: ...

    def issue_certificate(
        self,
        candidate_id: int,
        skill_id: int,
        *,
        score: float,
        cert_code: str,
        expires_at: str | None,
    ) -> Record | None: ...

    def get_certificate_by_code(self, cert_code: str) -> Record | None: ...

    def get_certificate_by_id(self, certificate_id: int) -> Record | None: ...

    def can_view_certificate(
        self, certificate_id: int, viewer_id: int, role: str
    ) -> bool: ...

    def list_candidate_certificates(self, candidate_id: int) -> tuple[Record, ...]: ...

    def revoke_certificate(self, certificate_id: int) -> Record | None: ...


class CertificateService:
    SUCCESS = "success"
    NOT_LOGGED_IN = "not_logged_in"
    WRONG_ROLE = "wrong_role"
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    RESULT_NOT_APPROVED = "result_not_approved"
    CERTIFICATE_EXISTS = "certificate_exists"
    CERTIFICATE_NOT_ACTIVE = "certificate_not_active"
    DB_ERROR = "db_error"

    _MESSAGES = {
        SUCCESS: "Thao tác thành công.",
        NOT_LOGGED_IN: "Vui lòng đăng nhập trước.",
        WRONG_ROLE: "Bạn không có quyền thực hiện thao tác này.",
        INVALID_INPUT: "Dữ liệu đầu vào không hợp lệ.",
        NOT_FOUND: "Không tìm thấy chứng chỉ.",
        FORBIDDEN: "Bạn không có quyền truy cập chứng chỉ này.",
        RESULT_NOT_APPROVED: "Chưa có kết quả được duyệt để cấp chứng chỉ.",
        CERTIFICATE_EXISTS: "Chứng chỉ cho kỹ năng này đã tồn tại.",
        CERTIFICATE_NOT_ACTIVE: "Chứng chỉ không ở trạng thái có thể thu hồi.",
        DB_ERROR: "Lỗi dữ liệu chứng chỉ. Vui lòng thử lại.",
    }

    def __init__(self, model: CertificateModel) -> None:
        self._model = model

    @classmethod
    def _result(
        cls, status: str, *, record: Record | None = None, value: object | None = None
    ) -> WorkflowResult:
        return WorkflowResult(
            status, cls._MESSAGES[status], record=record, value=value
        )

    @staticmethod
    def _identity(roles: set[str]) -> tuple[int, str] | WorkflowResult:
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return WorkflowResult(
                CertificateService.NOT_LOGGED_IN,
                CertificateService._MESSAGES[CertificateService.NOT_LOGGED_IN],
            )
        if session.current_user.role not in roles:
            return WorkflowResult(
                CertificateService.WRONG_ROLE,
                CertificateService._MESSAGES[CertificateService.WRONG_ROLE],
            )
        return session.current_user.id, session.current_user.role

    @staticmethod
    def _valid_id(value: int) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    def issue(
        self,
        candidate_id: int,
        skill_id: int,
        *,
        expires_at: str | None = None,
    ) -> WorkflowResult:
        identity = self._identity({"admin"})
        if isinstance(identity, WorkflowResult):
            return identity
        if (
            not self._valid_id(candidate_id)
            or not self._valid_id(skill_id)
            or (expires_at is not None and not isinstance(expires_at, str))
        ):
            return self._result(self.INVALID_INPUT)
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
            except ValueError:
                return self._result(self.INVALID_INPUT)
            if expiry <= datetime.now(expiry.tzinfo):
                return self._result(self.INVALID_INPUT)
            expires_at = expiry.isoformat()
        try:
            if (
                self._model.get_account_role(candidate_id) != "candidate"
                or not self._model.is_active_candidate(candidate_id)
            ):
                return self._result(self.NOT_FOUND)
            assessment = self._model.get_approved_assessment(candidate_id, skill_id)
            score = assessment.get("score") if assessment is not None else None
            if (
                assessment is None
                or assessment.get("status") != "approved"
                or not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not math.isfinite(score)
                or not 0 <= score <= 100
            ):
                return self._result(self.RESULT_NOT_APPROVED)
            if self._model.get_certificate_for_candidate(candidate_id, skill_id):
                return self._result(self.CERTIFICATE_EXISTS)
            record = self._model.issue_certificate(
                candidate_id,
                skill_id,
                score=float(score),
                cert_code=secrets.token_urlsafe(24),
                expires_at=expires_at,
            )
        except sqlite3.IntegrityError:
            logger.info("Certificate issuance rejected by a uniqueness constraint")
            return self._result(self.CERTIFICATE_EXISTS)
        except sqlite3.Error:
            logger.exception("Could not issue certificate")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.DB_ERROR)

    def get_mine(self) -> WorkflowResult:
        identity = self._identity({"candidate"})
        if isinstance(identity, WorkflowResult):
            return identity
        try:
            records = self._model.list_candidate_certificates(identity[0])
        except sqlite3.Error:
            logger.exception("Could not list candidate certificates")
            return self._result(self.DB_ERROR)
        return WorkflowResult(
            self.SUCCESS,
            self._MESSAGES[self.SUCCESS],
            records=records,
        )

    def verify(self, cert_code: str) -> WorkflowResult:
        identity = self._identity({"admin", "candidate", "company", "expert"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not isinstance(cert_code, str) or not cert_code.strip() or len(cert_code) > 200:
            return self._result(self.INVALID_INPUT)
        try:
            certificate = self._model.get_certificate_by_code(cert_code.strip())
            if certificate is None:
                return self._result(self.NOT_FOUND)
            certificate_id = certificate.get("id")
            if not self._valid_id(certificate_id):
                return self._result(self.NOT_FOUND)
            if not self._model.can_view_certificate(
                certificate_id, identity[0], identity[1]
            ):
                return self._result(self.FORBIDDEN)
        except sqlite3.Error:
            logger.exception("Could not verify certificate")
            return self._result(self.DB_ERROR)
        status = certificate.get("status")
        expires_at = certificate.get("expires_at")
        if status == "active" and isinstance(expires_at, str) and expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
            except ValueError:
                return self._result(self.DB_ERROR)
            if expiry <= datetime.now(expiry.tzinfo):
                expired_certificate = dict(certificate)
                expired_certificate["status"] = "expired"
                return self._result(
                    self.CERTIFICATE_NOT_ACTIVE, record=expired_certificate
                )
        if status != "active":
            return self._result(self.CERTIFICATE_NOT_ACTIVE, record=certificate)
        return self._result(self.SUCCESS, record=certificate)

    def revoke(self, certificate_id: int) -> WorkflowResult:
        identity = self._identity({"admin"})
        if isinstance(identity, WorkflowResult):
            return identity
        if not self._valid_id(certificate_id):
            return self._result(self.INVALID_INPUT)
        try:
            certificate = self._model.get_certificate_by_id(certificate_id)
            if certificate is None:
                return self._result(self.NOT_FOUND)
            if certificate.get("status") != "active":
                return self._result(self.CERTIFICATE_NOT_ACTIVE)
            expires_at = certificate.get("expires_at")
            if isinstance(expires_at, str) and expires_at:
                try:
                    expiry = datetime.fromisoformat(expires_at)
                except ValueError:
                    return self._result(self.DB_ERROR)
                if expiry <= datetime.now(expiry.tzinfo):
                    return self._result(self.CERTIFICATE_NOT_ACTIVE)
            record = self._model.revoke_certificate(certificate_id)
        except sqlite3.Error:
            logger.exception("Could not revoke certificate")
            return self._result(self.DB_ERROR)
        return self._result(self.SUCCESS, record=record) if record else self._result(self.NOT_FOUND)
