"""
TaskService — Quản lý nhiệm vụ được phân công từ Company cho Expert.

State machine:
  pending → in_progress  (Expert nhận)
  pending → cancelled    (Company hoặc Expert cancel)
  in_progress → completed (Expert hoàn thành)
  in_progress → cancelled (Company hoặc Expert cancel)
  completed/cancelled → (trạng thái cuối)

Phân quyền:
  - contract_id bắt buộc tại nghiệp vụ dù DB nullable
  - task.expert_id phải khớp contract.expert_id
  - task.company_id phải khớp contract.company_id
  - company_id và expert_id lấy từ SessionManager
  - Expert không xem task của Expert khác
  - Company không xem task của Company khác
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.database.connection import db
from app.services.auth_service import SessionManager

logger = logging.getLogger(__name__)

TASK_TYPES  = ("grading", "interview", "question_creation", "review")
TASK_STATUS = ("pending", "in_progress", "completed", "cancelled")
TASK_PRIORITY = ("low", "normal", "high", "urgent")

TASK_TYPE_LABELS = {
    "grading":           "Chấm điểm",
    "interview":         "Phỏng vấn",
    "question_creation": "Tạo câu hỏi",
    "review":            "Đánh giá",
}
TASK_STATUS_LABELS = {
    "pending":     "Chờ xử lý",
    "in_progress": "Đang thực hiện",
    "completed":   "Hoàn thành",
    "cancelled":   "Đã hủy",
}
TASK_PRIORITY_LABELS = {
    "low": "Thấp", "normal": "Bình thường",
    "high": "Cao", "urgent": "Khẩn cấp",
}


@dataclass
class TaskModel:
    id:              int
    company_id:      int
    expert_id:       int
    contract_id:     Optional[int]
    title:           str
    description:     Optional[str]
    task_type:       str
    status:          str
    priority:        str
    assigned_at:     str
    due_at:          Optional[str]
    completed_at:    Optional[str]
    exam_session_id: Optional[int]
    interview_id:    Optional[int]
    # From JOIN
    company_name:    Optional[str]
    expert_title:    Optional[str]

    @classmethod
    def from_row(cls, row) -> "TaskModel":
        return cls(
            id              = row["id"],
            company_id      = row["company_id"],
            expert_id       = row["expert_id"],
            contract_id     = row["contract_id"],
            title           = row["title"],
            description     = row["description"],
            task_type       = row["task_type"],
            status          = row["status"],
            priority        = row["priority"],
            assigned_at     = row["assigned_at"],
            due_at          = row["due_at"],
            completed_at    = row["completed_at"],
            exam_session_id = row["exam_session_id"],
            interview_id    = row["interview_id"],
            company_name    = row["company_name"],
            expert_title    = row["expert_title"],
        )

    @property
    def task_type_label(self) -> str:
        return TASK_TYPE_LABELS.get(self.task_type, self.task_type)

    @property
    def status_label(self) -> str:
        return TASK_STATUS_LABELS.get(self.status, self.status)

    @property
    def priority_label(self) -> str:
        return TASK_PRIORITY_LABELS.get(self.priority, self.priority)


class TaskResult:
    SUCCESS              = "success"
    NOT_LOGGED_IN        = "not_logged_in"
    WRONG_ROLE           = "wrong_role"
    NOT_FOUND            = "not_found"
    FORBIDDEN            = "forbidden"
    INVALID_TRANSITION   = "invalid_transition"
    CONTRACT_REQUIRED    = "contract_required"
    CONTRACT_NOT_ACTIVE  = "contract_not_active"
    EXPERT_MISMATCH      = "expert_mismatch"
    COMPANY_MISMATCH     = "company_mismatch"
    INVALID_TASK_TYPE    = "invalid_task_type"
    INVALID_PRIORITY     = "invalid_priority"
    EMPTY_TITLE          = "empty_title"
    INVALID_EXAM_SESSION = "invalid_exam_session"
    INVALID_INTERVIEW    = "invalid_interview"
    DB_ERROR             = "db_error"

    MESSAGES: dict[str, str] = {
        SUCCESS:             "Thao tác thành công.",
        NOT_LOGGED_IN:       "Vui lòng đăng nhập trước.",
        WRONG_ROLE:          "Không có quyền thực hiện thao tác này.",
        NOT_FOUND:           "Không tìm thấy nhiệm vụ.",
        FORBIDDEN:           "Bạn không có quyền truy cập nhiệm vụ này.",
        INVALID_TRANSITION:  "Chuyển trạng thái không hợp lệ.",
        CONTRACT_REQUIRED:   "Hợp đồng là bắt buộc khi tạo nhiệm vụ.",
        CONTRACT_NOT_ACTIVE: "Hợp đồng phải đang active mới được phân công nhiệm vụ.",
        EXPERT_MISMATCH:     "Expert không thuộc hợp đồng này.",
        COMPANY_MISMATCH:    "Company không thuộc hợp đồng này.",
        INVALID_TASK_TYPE:   "Loại nhiệm vụ không hợp lệ.",
        INVALID_PRIORITY:    "Độ ưu tiên không hợp lệ.",
        EMPTY_TITLE:         "Tiêu đề nhiệm vụ không được để trống.",
        INVALID_EXAM_SESSION: "Phiên thi không thuộc quyền quản lý của Company.",
        INVALID_INTERVIEW:   "Phỏng vấn không thuộc quyền quản lý của Company.",
        DB_ERROR:            "Lỗi cơ sở dữ liệu. Vui lòng thử lại.",
    }

    def __init__(self, status: str, task: TaskModel | None = None,
                 tasks: list[TaskModel] | None = None) -> None:
        self.status  = status
        self.task    = task
        self.tasks   = tasks or []
        self.success = (status == self.SUCCESS)
        self.message = self.MESSAGES.get(status, "Lỗi không xác định.")


class TaskService:

    def _require_role(self, *roles: str) -> TaskResult | None:
        s = SessionManager.instance()
        if not s.is_logged_in or s.current_user is None:
            return TaskResult(TaskResult.NOT_LOGGED_IN)
        if s.current_user.role not in roles:
            return TaskResult(TaskResult.WRONG_ROLE)
        return None

    def _current_user_id(self) -> int:
        return SessionManager.instance().current_user.id  # type: ignore[union-attr]

    def _fetch_task(self, task_id: int) -> TaskModel | None:
        try:
            row = db.fetchone(
                """
                SELECT t.*,
                       cp.company_name,
                       ep.title AS expert_title
                FROM tasks t
                LEFT JOIN company_profiles cp ON cp.user_id = t.company_id
                LEFT JOIN expert_profiles   ep ON ep.user_id = t.expert_id
                WHERE t.id = ?
                """,
                (task_id,),
            )
        except sqlite3.Error:
            return None
        return TaskModel.from_row(row) if row else None

    def _validate_contract_for_company(
        self, contract_id: int, company_id: int
    ) -> TaskResult | None:
        """Kiểm tra hợp đồng active và thuộc company_id."""
        try:
            row = db.fetchone(
                "SELECT company_id, expert_id, status FROM company_expert_contracts WHERE id=?",
                (contract_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error checking contract: %s", exc)
            return TaskResult(TaskResult.DB_ERROR)

        if row is None:
            return TaskResult(TaskResult.CONTRACT_REQUIRED)
        if row["company_id"] != company_id:
            return TaskResult(TaskResult.COMPANY_MISMATCH)
        if row["status"] != "active":
            return TaskResult(TaskResult.CONTRACT_NOT_ACTIVE)
        return None  # OK

    # ── Company: Tạo task ─────────────────────────────────────────────────────

    def create_task(
        self,
        contract_id: int,
        title: str,
        task_type: str,
        description: str = "",
        priority: str = "normal",
        due_at: str = "",
        exam_session_id: int | None = None,
        interview_id: int | None = None,
    ) -> TaskResult:
        """
        Company tạo task cho Expert trong hợp đồng.
        contract_id bắt buộc tại nghiệp vụ.
        """
        err = self._require_role("company")
        if err:
            return err

        company_id = self._current_user_id()
        title = title.strip()
        if not title:
            return TaskResult(TaskResult.EMPTY_TITLE)
        if task_type not in TASK_TYPES:
            return TaskResult(TaskResult.INVALID_TASK_TYPE)
        if priority not in TASK_PRIORITY:
            return TaskResult(TaskResult.INVALID_PRIORITY)

        # Validate contract
        contract_err = self._validate_contract_for_company(contract_id, company_id)
        if contract_err:
            return contract_err

        # Lấy expert_id từ contract
        try:
            ctr_row = db.fetchone(
                "SELECT expert_id FROM company_expert_contracts WHERE id=?",
                (contract_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error: %s", exc)
            return TaskResult(TaskResult.DB_ERROR)

        expert_id = ctr_row["expert_id"]

        # Kiểm tra exam_session thuộc Company
        if exam_session_id is not None:
            try:
                es_row = db.fetchone(
                    "SELECT company_id FROM exam_sessions WHERE id=?",
                    (exam_session_id,),
                )
            except sqlite3.Error:
                return TaskResult(TaskResult.DB_ERROR)
            if es_row is None or es_row["company_id"] != company_id:
                return TaskResult(TaskResult.INVALID_EXAM_SESSION)

        # Kiểm tra interview thuộc Company
        if interview_id is not None:
            try:
                iv_row = db.fetchone(
                    "SELECT company_id FROM interviews WHERE id=?",
                    (interview_id,),
                )
            except sqlite3.Error:
                return TaskResult(TaskResult.DB_ERROR)
            if iv_row is None or iv_row["company_id"] != company_id:
                return TaskResult(TaskResult.INVALID_INTERVIEW)

        try:
            db.execute(
                """
                INSERT INTO tasks
                    (company_id, expert_id, contract_id, title, description,
                     task_type, status, priority, due_at,
                     exam_session_id, interview_id)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (company_id, expert_id, contract_id, title,
                 description.strip() or None, task_type, priority,
                 due_at.strip() or None, exam_session_id, interview_id),
            )
        except sqlite3.Error as exc:
            logger.error("DB error creating task: %s", exc)
            return TaskResult(TaskResult.DB_ERROR)

        try:
            row = db.fetchone(
                "SELECT id FROM tasks WHERE company_id=? AND contract_id=? AND title=? ORDER BY id DESC LIMIT 1",
                (company_id, contract_id, title),
            )
            if row:
                task = self._fetch_task(row["id"])
                logger.info("Task created: id=%d, contract=%d", row["id"], contract_id)
                return TaskResult(TaskResult.SUCCESS, task=task)
        except Exception as exc:
            logger.error("DB error fetching task: %s", exc)

        return TaskResult(TaskResult.DB_ERROR)

    # ── Expert: Nhận / Hoàn thành task ───────────────────────────────────────

    def start_task(self, task_id: int) -> TaskResult:
        """Expert nhận task (pending → in_progress)."""
        err = self._require_role("expert")
        if err:
            return err

        expert_id = self._current_user_id()
        task = self._fetch_task(task_id)

        if task is None:
            return TaskResult(TaskResult.NOT_FOUND)
        if task.expert_id != expert_id:
            return TaskResult(TaskResult.FORBIDDEN)
        if task.status != "pending":
            return TaskResult(TaskResult.INVALID_TRANSITION)

        try:
            db.execute(
                "UPDATE tasks SET status='in_progress' WHERE id=?",
                (task_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error starting task: %s", exc)
            return TaskResult(TaskResult.DB_ERROR)

        return TaskResult(TaskResult.SUCCESS, task=self._fetch_task(task_id))

    def complete_task(self, task_id: int) -> TaskResult:
        """Expert hoàn thành task (in_progress → completed)."""
        err = self._require_role("expert")
        if err:
            return err

        expert_id = self._current_user_id()
        task = self._fetch_task(task_id)

        if task is None:
            return TaskResult(TaskResult.NOT_FOUND)
        if task.expert_id != expert_id:
            return TaskResult(TaskResult.FORBIDDEN)
        if task.status != "in_progress":
            return TaskResult(TaskResult.INVALID_TRANSITION)

        try:
            db.execute(
                "UPDATE tasks SET status='completed', completed_at=datetime('now','localtime') WHERE id=?",
                (task_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error completing task: %s", exc)
            return TaskResult(TaskResult.DB_ERROR)

        return TaskResult(TaskResult.SUCCESS, task=self._fetch_task(task_id))

    # ── Chung: Cancel task ────────────────────────────────────────────────────

    def cancel_task(self, task_id: int) -> TaskResult:
        """Company hoặc Expert cancel task (pending/in_progress → cancelled)."""
        err = self._require_role("company", "expert")
        if err:
            return err

        user    = SessionManager.instance().current_user  # type: ignore[union-attr]
        user_id = user.id
        task    = self._fetch_task(task_id)

        if task is None:
            return TaskResult(TaskResult.NOT_FOUND)

        if user.role == "company" and task.company_id != user_id:
            return TaskResult(TaskResult.FORBIDDEN)
        if user.role == "expert" and task.expert_id != user_id:
            return TaskResult(TaskResult.FORBIDDEN)
        if task.status not in ("pending", "in_progress"):
            return TaskResult(TaskResult.INVALID_TRANSITION)

        try:
            db.execute(
                "UPDATE tasks SET status='cancelled' WHERE id=?",
                (task_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error cancelling task: %s", exc)
            return TaskResult(TaskResult.DB_ERROR)

        return TaskResult(TaskResult.SUCCESS, task=self._fetch_task(task_id))

    # ── Danh sách ─────────────────────────────────────────────────────────────

    def list_my_tasks(
        self,
        status_filter: str | None = None,
        contract_id: int | None = None,
    ) -> TaskResult:
        """Company xem task mình tạo; Expert xem task được assign."""
        err = self._require_role("company", "expert")
        if err:
            return err

        user    = SessionManager.instance().current_user  # type: ignore[union-attr]
        user_id = user.id

        where  = "t.company_id=?" if user.role == "company" else "t.expert_id=?"
        params: list = [user_id]

        if status_filter and status_filter in TASK_STATUS:
            where += " AND t.status=?"
            params.append(status_filter)

        if contract_id is not None:
            where += " AND t.contract_id=?"
            params.append(contract_id)

        try:
            rows = db.fetchall(
                f"""
                SELECT t.*,
                       cp.company_name,
                       ep.title AS expert_title
                FROM tasks t
                LEFT JOIN company_profiles cp ON cp.user_id = t.company_id
                LEFT JOIN expert_profiles   ep ON ep.user_id = t.expert_id
                WHERE {where}
                ORDER BY t.assigned_at DESC
                """,
                tuple(params),
            )
        except sqlite3.Error as exc:
            logger.error("DB error listing tasks: %s", exc)
            return TaskResult(TaskResult.DB_ERROR)

        tasks = [TaskModel.from_row(r) for r in rows]
        return TaskResult(TaskResult.SUCCESS, tasks=tasks)


# ── Singleton ──────────────────────────────────────────────────────────────────
task_service = TaskService()
