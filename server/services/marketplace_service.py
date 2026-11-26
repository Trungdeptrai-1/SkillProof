"""Authenticated marketplace actions. Never accept a caller-supplied actor ID."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from app.services.auth_service import SessionManager
from server.models.marketplace_repository import MarketplaceRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MarketplaceResult:
    status: str
    data: Any = None
    message: str = field(init=False)
    success: bool = field(init=False)

    MESSAGES = {
        "success": "Thao tác thành công.",
        "not_logged_in": "Vui lòng đăng nhập.",
        "wrong_role": "Tài khoản không có quyền thực hiện thao tác.",
        "invalid_input": "Thông tin nhập không hợp lệ.",
        "not_found": "Không tìm thấy dữ liệu hoặc không được phép thao tác.",
        "db_error": "Lỗi cơ sở dữ liệu, vui lòng thử lại.",
    }

    def __post_init__(self) -> None:
        self.success = self.status == "success"
        self.message = self.MESSAGES.get(self.status, "Đã có lỗi xảy ra.")


class MarketplaceService:
    def __init__(self, repository: MarketplaceRepository | None = None) -> None:
        self._repo = repository if repository is not None else MarketplaceRepository()

    @staticmethod
    def _actor(required_role: str) -> int | MarketplaceResult:
        session = SessionManager.instance()
        user = session.current_user
        if not session.is_logged_in or user is None:
            return MarketplaceResult("not_logged_in")
        if user.role != required_role:
            return MarketplaceResult("wrong_role")
        return user.id

    @staticmethod
    def _valid_id(value: object) -> bool:
        return type(value) is int and value > 0

    def _invoke(self, action, *args: object) -> MarketplaceResult:
        try:
            data = action(*args)
            if data is None or data is False:
                return MarketplaceResult("not_found")
            return MarketplaceResult("success", data)
        except sqlite3.Error:
            logger.exception("Marketplace database action failed")
            return MarketplaceResult("db_error")

    def browse_jobs(self, search: str = "", location: str = "") -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not isinstance(search, str) or not isinstance(location, str):
            return MarketplaceResult("invalid_input")
        if len(search) > 200 or len(location) > 200:
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.browse_jobs, actor, search, location)

    def apply(self, job_id: int, cover_letter: str = "") -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(job_id) or not isinstance(cover_letter, str) or len(cover_letter) > 4000:
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.apply, actor, job_id, cover_letter)

    def my_applications(self) -> MarketplaceResult:
        actor = self._actor("candidate")
        return actor if isinstance(actor, MarketplaceResult) else self._invoke(self._repo.my_applications, actor)

    def respond_to_offer(self, application_id: int, accepted: bool) -> MarketplaceResult:
        """Reply to an employer's final offer; applicant identity comes from session."""
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(application_id) or type(accepted) is not bool:
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.respond_to_offer, actor, application_id, accepted)

    def saved_jobs(self) -> MarketplaceResult:
        actor = self._actor("candidate")
        return actor if isinstance(actor, MarketplaceResult) else self._invoke(self._repo.saved_jobs, actor)

    def withdraw(self, application_id: int) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(application_id):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.withdraw, actor, application_id)

    def save_job(self, job_id: int) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(job_id):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.save_job, actor, job_id)

    def unsave_job(self, job_id: int) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(job_id):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.unsave_job, actor, job_id)

    def get_discoverable(self) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        try:
            state = self._repo.get_discoverable(actor)
        except sqlite3.Error:
            logger.exception("Could not read Candidate profile visibility")
            return MarketplaceResult("db_error")
        if state is None:
            return MarketplaceResult("not_found")
        return MarketplaceResult("success", state)

    def set_discoverable(self, visible: bool) -> MarketplaceResult:
        actor = self._actor("candidate")
        if isinstance(actor, MarketplaceResult):
            return actor
        if type(visible) is not bool:
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.set_discoverable, actor, visible)

    def discover_candidates(self, search: str = "") -> MarketplaceResult:
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not isinstance(search, str) or len(search) > 200:
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.discover_candidates, actor, search)

    def applicants(self, job_id: int) -> MarketplaceResult:
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(job_id):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.applicants, actor, job_id)

    def list_assessment_exams(self) -> MarketplaceResult:
        """Published assessment papers owned by the signed-in Company."""
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        from server.controllers.exam_controller import ExamController
        from server.models.recruitment_repository import RecruitmentRepository
        from server.services.exam_service import ExamService
        exam_repo = RecruitmentRepository(self._repo.conn)
        result = ExamController(ExamService(exam_repo, exam_repo)).list_exams()
        if not result.success:
            return MarketplaceResult("not_found", {"reason": result.message})
        return MarketplaceResult(
            "success",
            [dict(item) for item in result.exams if item.get("is_published") in (True, 1)],
        )

    def invite_applicant_to_exam(self, application_id: int, exam_id: int) -> MarketplaceResult:
        """Issue a real exam invitation for a shortlisted, Company-owned application."""
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(application_id) or not self._valid_id(exam_id):
            return MarketplaceResult("invalid_input")
        try:
            application = self._repo.application_for_company(actor, application_id)
            if not application or application["status"] != "shortlisted":
                return MarketplaceResult("not_found")
            if application["job_status"] != "published":
                return MarketplaceResult("not_found")
            from server.controllers.exam_controller import ExamController
            from server.models.recruitment_repository import RecruitmentRepository
            from server.services.exam_service import ExamService
            exam_repo = RecruitmentRepository(self._repo.conn)
            exam_result = ExamController(ExamService(exam_repo, exam_repo)).invite_candidate(
                int(application["job_posting_id"]),
                exam_id,
                int(application["candidate_id"]),
            )
            if not exam_result.success:
                return MarketplaceResult("not_found", {"reason": exam_result.message})
            updated = self._repo.mark_assessment_after_exam_invitation(actor, application_id)
            if not updated:
                # Exam invite has been created; report this explicitly for reconciliation.
                return MarketplaceResult("db_error", {"reason": "Exam invitation created, but pipeline stage not updated."})
            return MarketplaceResult("success", dict(exam_result.invitation))
        except sqlite3.Error:
            logger.exception("Unable to hand off application to assessment")
            return MarketplaceResult("db_error")

    def schedule_application_interview(
        self, application_id: int, title: str, scheduled_at: str,
        description: str = "", duration_min: int = 60,
        meeting_url: str | None = None,
    ) -> MarketplaceResult:
        """Schedule only for a released assessment, atomically with stage change."""
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if (not self._valid_id(application_id) or not isinstance(title, str)
                or not isinstance(scheduled_at, str) or not isinstance(description, str)
                or not isinstance(duration_min, int) or isinstance(duration_min, bool)
                or (meeting_url is not None and not isinstance(meeting_url, str))):
            return MarketplaceResult("invalid_input")
        conn = self._repo.conn
        try:
            application = self._repo.application_for_company(actor, application_id)
            if not application or application["status"] != "assessment":
                return MarketplaceResult("not_found")
            candidate_id = int(application["candidate_id"])
            job_id = int(application["job_posting_id"])
            if not self._repo.has_released_assessment(actor, job_id, candidate_id):
                return MarketplaceResult("not_found", {"reason": "Kết quả bài thi chưa được công bố."})

            from app.integration.supplementary_adapters import _InterviewRepositoryAdapter
            from server.controllers.supplementary_workflow_controller import InterviewController
            from server.models.recruitment_repository import RecruitmentRepository
            from server.services.interview_service import InterviewService

            # RecruitmentRepository's nested transaction keeps the interview inside
            # this outer SAVEPOINT until both interview and stage changes succeed.
            conn.execute("SAVEPOINT marketplace_interview_handoff")
            try:
                recruitment = RecruitmentRepository(conn)
                interview = InterviewController(
                    InterviewService(_InterviewRepositoryAdapter(recruitment))
                ).schedule(
                    candidate_id, title, scheduled_at, description=description,
                    duration_min=duration_min, meeting_url=meeting_url,
                )
                if not interview.success:
                    conn.execute("ROLLBACK TO SAVEPOINT marketplace_interview_handoff")
                    conn.execute("RELEASE SAVEPOINT marketplace_interview_handoff")
                    return MarketplaceResult("not_found", {"reason": interview.message})
                change = conn.execute(
                    """UPDATE job_applications SET status='interview',
                       updated_at=datetime('now','localtime')
                       WHERE id=? AND status='assessment'
                         AND EXISTS (
                           SELECT 1 FROM job_postings jp
                           WHERE jp.id=job_applications.job_posting_id
                             AND jp.company_id=?
                         )""", (application_id, actor),
                )
                if change.rowcount != 1:
                    conn.execute("ROLLBACK TO SAVEPOINT marketplace_interview_handoff")
                    conn.execute("RELEASE SAVEPOINT marketplace_interview_handoff")
                    return MarketplaceResult("not_found")
                interview_record = interview.record
                interview_id = interview_record.get("id") if interview_record is not None else None
                if type(interview_id) is not int or interview_id <= 0:
                    conn.execute("ROLLBACK TO SAVEPOINT marketplace_interview_handoff")
                    conn.execute("RELEASE SAVEPOINT marketplace_interview_handoff")
                    return MarketplaceResult("db_error")
                conn.execute(
                    "INSERT INTO application_interviews(application_id,interview_id) VALUES(?,?)",
                    (application_id, interview_id),
                )
                conn.execute("RELEASE SAVEPOINT marketplace_interview_handoff")
                return MarketplaceResult("success", interview_record)
            except Exception:
                conn.execute("ROLLBACK TO SAVEPOINT marketplace_interview_handoff")
                conn.execute("RELEASE SAVEPOINT marketplace_interview_handoff")
                raise
        except sqlite3.Error:
            logger.exception("Unable to schedule applicant interview")
            return MarketplaceResult("db_error")

    def decide_after_interview(
        self, application_id: int, decision: str, note: str = ""
    ) -> MarketplaceResult:
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if (not self._valid_id(application_id)
                or not isinstance(decision, str)
                or decision not in ("offered", "rejected")
                or not isinstance(note, str) or len(note) > 2000):
            return MarketplaceResult("invalid_input")
        return self._invoke(
            self._repo.decide_after_interview, actor, application_id, decision, note
        )

    def update_application_status(self, application_id: int, status: str) -> MarketplaceResult:
        actor = self._actor("company")
        if isinstance(actor, MarketplaceResult):
            return actor
        if not self._valid_id(application_id) or not isinstance(status, str):
            return MarketplaceResult("invalid_input")
        return self._invoke(self._repo.update_application_status, actor, application_id, status)
