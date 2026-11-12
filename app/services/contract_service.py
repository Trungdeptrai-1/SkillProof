"""
ContractService — Quản lý hợp đồng Company–Expert.

State machine hợp đồng:
  pending_expert → active      (Expert chấp thuận)
  pending_expert → rejected    (Expert từ chối)
  pending_expert → cancelled   (Company rút lại trước khi Expert phản hồi)
  active         → completed   (Company đánh dấu hoàn thành)
  active         → terminated  (Company chấm dứt sớm, auto-cancel tasks)
  active         → cancelled   (Hai bên đồng ý)
  rejected/completed/terminated/cancelled → (trạng thái cuối, không chuyển được)

Phân quyền (tại service, không tin UI):
  - company_id và expert_id lấy từ SessionManager
  - Mọi thao tác kiểm tra chủ sở hữu hợp đồng
  - D4: không cho phép nhiều hợp đồng active cùng cặp Company+Expert
  - D5: user bị soft-delete không tham gia nghiệp vụ mới

Soft-delete: users.is_deleted=1 → không được tạo hợp đồng mới.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Optional

from app.database.connection import db
from app.services.auth_service import SessionManager

logger = logging.getLogger(__name__)

# Hằng số trạng thái
CONTRACT_STATUS = (
    "pending_expert",
    "rejected",
    "active",
    "completed",
    "terminated",
    "cancelled",
)
CONTRACT_TERMINAL = {"rejected", "completed", "terminated", "cancelled"}

# Chuyển trạng thái hợp lệ: (from, to) → role được phép
VALID_TRANSITIONS: dict[tuple[str, str], str] = {
    ("pending_expert", "active"):    "expert",
    ("pending_expert", "rejected"):  "expert",
    ("pending_expert", "cancelled"): "company",
    ("active", "completed"):         "company",
    ("active", "terminated"):        "company",
    ("active", "cancelled"):         "company",
}


# ══════════════════════════════════════════════════════════════════════════════
# DTO
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ContractModel:
    id:               int
    company_id:       int
    expert_id:        int
    contract_code:    str
    status:           str
    start_date:       str
    end_date:         Optional[str]
    notes:            Optional[str]
    rejection_reason: Optional[str]
    terminated_reason: Optional[str]
    created_at:       str
    # Thông tin profile đi kèm (đọc từ JOIN)
    company_name:     Optional[str]   # company_profiles.company_name
    expert_title:     Optional[str]   # expert_profiles.title

    @classmethod
    def from_row(cls, row) -> "ContractModel":
        return cls(
            id               = row["id"],
            company_id       = row["company_id"],
            expert_id        = row["expert_id"],
            contract_code    = row["contract_code"],
            status           = row["status"],
            start_date       = row["start_date"],
            end_date         = row["end_date"],
            notes            = row["notes"],
            rejection_reason = row["rejection_reason"],
            terminated_reason= row["terminated_reason"],
            created_at       = row["created_at"],
            company_name     = row["company_name"],
            expert_title     = row["expert_title"],
        )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_terminal(self) -> bool:
        return self.status in CONTRACT_TERMINAL


# ══════════════════════════════════════════════════════════════════════════════
# Result
# ══════════════════════════════════════════════════════════════════════════════

class ContractResult:
    SUCCESS              = "success"
    NOT_LOGGED_IN        = "not_logged_in"
    WRONG_ROLE           = "wrong_role"
    NOT_FOUND            = "not_found"
    FORBIDDEN            = "forbidden"
    INVALID_TRANSITION   = "invalid_transition"
    ACTIVE_CONTRACT_EXISTS = "active_contract_exists"
    EXPERT_NOT_FOUND     = "expert_not_found"
    EXPERT_UNAVAILABLE   = "expert_unavailable"
    PENDING_TASKS_EXIST  = "pending_tasks_exist"
    DB_ERROR             = "db_error"

    MESSAGES: dict[str, str] = {
        SUCCESS:              "Thao tác thành công.",
        NOT_LOGGED_IN:        "Vui lòng đăng nhập trước.",
        WRONG_ROLE:           "Không có quyền thực hiện thao tác này.",
        NOT_FOUND:            "Không tìm thấy hợp đồng.",
        FORBIDDEN:            "Bạn không có quyền truy cập hợp đồng này.",
        INVALID_TRANSITION:   "Chuyển trạng thái không hợp lệ.",
        ACTIVE_CONTRACT_EXISTS: "Đã có hợp đồng đang hoạt động với chuyên gia này.",
        EXPERT_NOT_FOUND:     "Không tìm thấy chuyên gia.",
        EXPERT_UNAVAILABLE:   "Chuyên gia không khả dụng hoặc tài khoản không hoạt động.",
        PENDING_TASKS_EXIST:  "Vẫn còn nhiệm vụ chưa hoàn thành. Vui lòng xử lý trước.",
        DB_ERROR:             "Lỗi cơ sở dữ liệu. Vui lòng thử lại.",
    }

    def __init__(self, status: str, contract: ContractModel | None = None,
                 contracts: list[ContractModel] | None = None) -> None:
        self.status    = status
        self.contract  = contract
        self.contracts = contracts or []
        self.success   = (status == self.SUCCESS)
        self.message   = self.MESSAGES.get(status, "Lỗi không xác định.")

    def __repr__(self) -> str:
        return f"ContractResult(status={self.status!r})"


# ══════════════════════════════════════════════════════════════════════════════
# Service
# ══════════════════════════════════════════════════════════════════════════════

class ContractService:
    """
    Quản lý hợp đồng Company–Expert.
    Mọi thao tác kiểm tra quyền tại tầng service.
    """

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _require_role(self, *roles: str) -> ContractResult | None:
        s = SessionManager.instance()
        if not s.is_logged_in or s.current_user is None:
            return ContractResult(ContractResult.NOT_LOGGED_IN)
        if s.current_user.role not in roles:
            return ContractResult(ContractResult.WRONG_ROLE)
        return None

    def _current_user_id(self) -> int:
        return SessionManager.instance().current_user.id  # type: ignore[union-attr]

    def _fetch_contract(self, contract_id: int) -> ContractModel | None:
        """Truy vấn contract + tên company + tiêu đề expert."""
        try:
            row = db.fetchone(
                """
                SELECT c.*,
                       cp.company_name,
                       ep.title AS expert_title
                FROM company_expert_contracts c
                LEFT JOIN company_profiles cp ON cp.user_id = c.company_id
                LEFT JOIN expert_profiles   ep ON ep.user_id = c.expert_id
                WHERE c.id = ?
                """,
                (contract_id,),
            )
        except sqlite3.Error:
            return None
        return ContractModel.from_row(row) if row else None

    def _is_user_deleted(self, user_id: int) -> bool:
        try:
            row = db.fetchone("SELECT is_deleted FROM users WHERE id=?", (user_id,))
            return row is None or bool(row["is_deleted"])
        except Exception:
            return True

    # ── Company: Gửi đề nghị hợp tác ─────────────────────────────────────────

    def invite_expert(
        self,
        expert_profile_id: int,
        notes: str = "",
        end_date: str = "",
    ) -> ContractResult:
        """
        Company gửi đề nghị hợp tác tới Expert.
        Hợp đồng tạo với status='pending_expert' — chưa active.
        expert_profile_id: ID của expert_profiles, không phải user_id (D2).
        """
        err = self._require_role("company")
        if err:
            return err

        company_id = self._current_user_id()

        # Kiểm tra company không bị soft-delete
        if self._is_user_deleted(company_id):
            return ContractResult(ContractResult.WRONG_ROLE)

        # Ánh xạ expert_profile_id → user_id (D2)
        try:
            ep_row = db.fetchone(
                """
                SELECT ep.user_id, ep.availability,
                       u.is_active, u.is_deleted
                FROM expert_profiles ep
                JOIN users u ON u.id = ep.user_id
                WHERE ep.id = ?
                """,
                (expert_profile_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error fetching expert: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        if ep_row is None:
            return ContractResult(ContractResult.EXPERT_NOT_FOUND)

        # Kiểm tra expert có thể hợp tác
        if not bool(ep_row["is_active"]) or bool(ep_row["is_deleted"]):
            return ContractResult(ContractResult.EXPERT_UNAVAILABLE)
        if ep_row["availability"] == "unavailable":
            return ContractResult(ContractResult.EXPERT_UNAVAILABLE)

        expert_id = ep_row["user_id"]

        # D4: không cho phép nhiều hợp đồng active cùng cặp
        try:
            active_check = db.fetchone(
                """
                SELECT id FROM company_expert_contracts
                WHERE company_id=? AND expert_id=?
                  AND status IN ('pending_expert','active')
                """,
                (company_id, expert_id),
            )
        except sqlite3.Error as exc:
            logger.error("DB error checking active contract: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        if active_check is not None:
            return ContractResult(ContractResult.ACTIVE_CONTRACT_EXISTS)

        # Tạo hợp đồng
        contract_code = f"CTR-{uuid.uuid4().hex[:8].upper()}"
        try:
            db.execute(
                """
                INSERT INTO company_expert_contracts
                    (company_id, expert_id, contract_code, status,
                     end_date, notes)
                VALUES (?, ?, ?, 'pending_expert', ?, ?)
                """,
                (company_id, expert_id, contract_code,
                 end_date.strip() or None,
                 notes.strip() or None),
            )
        except sqlite3.IntegrityError:
            return ContractResult(ContractResult.ACTIVE_CONTRACT_EXISTS)
        except sqlite3.Error as exc:
            logger.error("DB error creating contract: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        # Lấy contract vừa tạo
        try:
            row = db.fetchone(
                "SELECT id FROM company_expert_contracts WHERE contract_code=?",
                (contract_code,),
            )
            if row:
                contract = self._fetch_contract(row["id"])
                logger.info("Contract created: %s, company=%d, expert=%d",
                            contract_code, company_id, expert_id)
                return ContractResult(ContractResult.SUCCESS, contract=contract)
        except Exception as exc:
            logger.error("DB error fetching new contract: %s", exc)

        return ContractResult(ContractResult.DB_ERROR)

    # ── Expert: Phản hồi đề nghị ──────────────────────────────────────────────

    def accept_contract(self, contract_id: int) -> ContractResult:
        """Expert chấp thuận → active."""
        err = self._require_role("expert")
        if err:
            return err

        expert_id = self._current_user_id()
        contract  = self._fetch_contract(contract_id)

        if contract is None:
            return ContractResult(ContractResult.NOT_FOUND)
        if contract.expert_id != expert_id:
            return ContractResult(ContractResult.FORBIDDEN)
        if contract.status != "pending_expert":
            return ContractResult(ContractResult.INVALID_TRANSITION)

        try:
            db.execute(
                "UPDATE company_expert_contracts SET status='active' WHERE id=?",
                (contract_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error accepting contract: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        logger.info("Contract accepted: id=%d, expert=%d", contract_id, expert_id)
        return ContractResult(ContractResult.SUCCESS, contract=self._fetch_contract(contract_id))

    def reject_contract(self, contract_id: int, reason: str = "") -> ContractResult:
        """Expert từ chối → rejected."""
        err = self._require_role("expert")
        if err:
            return err

        expert_id = self._current_user_id()
        contract  = self._fetch_contract(contract_id)

        if contract is None:
            return ContractResult(ContractResult.NOT_FOUND)
        if contract.expert_id != expert_id:
            return ContractResult(ContractResult.FORBIDDEN)
        if contract.status != "pending_expert":
            return ContractResult(ContractResult.INVALID_TRANSITION)

        try:
            db.execute(
                "UPDATE company_expert_contracts SET status='rejected', rejection_reason=? WHERE id=?",
                (reason.strip() or None, contract_id),
            )
        except sqlite3.Error as exc:
            logger.error("DB error rejecting contract: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        logger.info("Contract rejected: id=%d, expert=%d", contract_id, expert_id)
        return ContractResult(ContractResult.SUCCESS, contract=self._fetch_contract(contract_id))

    # ── Company: Rút lại / Hoàn thành / Chấm dứt ─────────────────────────────

    def cancel_pending_contract(self, contract_id: int) -> ContractResult:
        """Company rút lại đề nghị (pending → cancelled)."""
        err = self._require_role("company")
        if err:
            return err

        company_id = self._current_user_id()
        contract   = self._fetch_contract(contract_id)

        if contract is None:
            return ContractResult(ContractResult.NOT_FOUND)
        if contract.company_id != company_id:
            return ContractResult(ContractResult.FORBIDDEN)
        if contract.status != "pending_expert":
            return ContractResult(ContractResult.INVALID_TRANSITION)

        try:
            db.execute(
                "UPDATE company_expert_contracts SET status='cancelled' WHERE id=?",
                (contract_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error cancelling pending contract: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        return ContractResult(ContractResult.SUCCESS, contract=self._fetch_contract(contract_id))

    def complete_contract(self, contract_id: int) -> ContractResult:
        """
        Company đánh dấu hợp đồng hoàn thành.
        Yêu cầu: không còn task pending/in_progress.
        """
        err = self._require_role("company")
        if err:
            return err

        company_id = self._current_user_id()
        contract   = self._fetch_contract(contract_id)

        if contract is None:
            return ContractResult(ContractResult.NOT_FOUND)
        if contract.company_id != company_id:
            return ContractResult(ContractResult.FORBIDDEN)
        if contract.status != "active":
            return ContractResult(ContractResult.INVALID_TRANSITION)

        # Kiểm tra còn task chưa xong
        try:
            pending = db.fetchone(
                """
                SELECT COUNT(*) as c FROM tasks
                WHERE contract_id=? AND status IN ('pending','in_progress')
                """,
                (contract_id,),
            )
            if pending and pending["c"] > 0:
                return ContractResult(ContractResult.PENDING_TASKS_EXIST)
        except sqlite3.Error as exc:
            logger.error("DB error checking pending tasks: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        try:
            db.execute(
                "UPDATE company_expert_contracts SET status='completed' WHERE id=?",
                (contract_id,),
            )
        except sqlite3.Error as exc:
            logger.error("DB error completing contract: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        logger.info("Contract completed: id=%d", contract_id)
        return ContractResult(ContractResult.SUCCESS, contract=self._fetch_contract(contract_id))

    def terminate_contract(self, contract_id: int, reason: str = "") -> ContractResult:
        """
        Company chấm dứt hợp đồng sớm (D3: auto-cancel tasks pending/in_progress).
        Thực hiện trong transaction.
        """
        err = self._require_role("company")
        if err:
            return err

        company_id = self._current_user_id()
        contract   = self._fetch_contract(contract_id)

        if contract is None:
            return ContractResult(ContractResult.NOT_FOUND)
        if contract.company_id != company_id:
            return ContractResult(ContractResult.FORBIDDEN)
        if contract.status != "active":
            return ContractResult(ContractResult.INVALID_TRANSITION)

        conn = db.get_connection()
        try:
            # D3: Auto-cancel tasks pending/in_progress trong cùng transaction
            conn.execute(
                """
                UPDATE tasks SET status='cancelled',
                    description = COALESCE(description || ' ', '') || '[Auto-cancelled: hợp đồng bị chấm dứt]'
                WHERE contract_id=? AND status IN ('pending','in_progress')
                """,
                (contract_id,),
            )
            conn.execute(
                "UPDATE company_expert_contracts SET status='terminated', terminated_reason=? WHERE id=?",
                (reason.strip() or None, contract_id),
            )
            conn.commit()
        except sqlite3.Error as exc:
            logger.error("DB error terminating contract: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        logger.info("Contract terminated: id=%d, reason=%s", contract_id, reason or "none")
        return ContractResult(ContractResult.SUCCESS, contract=self._fetch_contract(contract_id))

    # ── Xem danh sách ─────────────────────────────────────────────────────────

    def list_my_contracts(
        self,
        status_filter: str | None = None,
    ) -> ContractResult:
        """
        Company xem hợp đồng của mình; Expert xem hợp đồng của mình.
        Lọc theo status nếu cung cấp.
        """
        err = self._require_role("company", "expert")
        if err:
            return err

        user    = SessionManager.instance().current_user
        user_id = user.id  # type: ignore[union-attr]

        where = "c.company_id=?" if user.role == "company" else "c.expert_id=?"  # type: ignore[union-attr]
        params: list = [user_id]

        if status_filter and status_filter in CONTRACT_STATUS:
            where += " AND c.status=?"
            params.append(status_filter)

        try:
            rows = db.fetchall(
                f"""
                SELECT c.*,
                       cp.company_name,
                       ep.title AS expert_title
                FROM company_expert_contracts c
                LEFT JOIN company_profiles cp ON cp.user_id = c.company_id
                LEFT JOIN expert_profiles   ep ON ep.user_id = c.expert_id
                WHERE {where}
                ORDER BY c.created_at DESC
                """,
                tuple(params),
            )
        except sqlite3.Error as exc:
            logger.error("DB error listing contracts: %s", exc)
            return ContractResult(ContractResult.DB_ERROR)

        contracts = [ContractModel.from_row(r) for r in rows]
        return ContractResult(ContractResult.SUCCESS, contracts=contracts)

    def get_contract(self, contract_id: int) -> ContractResult:
        """Lấy chi tiết một hợp đồng. Chỉ Company hoặc Expert sở hữu mới xem được."""
        err = self._require_role("company", "expert")
        if err:
            return err

        user_id = self._current_user_id()
        contract = self._fetch_contract(contract_id)

        if contract is None:
            return ContractResult(ContractResult.NOT_FOUND)

        user_role = SessionManager.instance().current_user.role  # type: ignore[union-attr]
        if user_role == "company" and contract.company_id != user_id:
            return ContractResult(ContractResult.FORBIDDEN)
        if user_role == "expert" and contract.expert_id != user_id:
            return ContractResult(ContractResult.FORBIDDEN)

        return ContractResult(ContractResult.SUCCESS, contract=contract)


# ── Singleton ──────────────────────────────────────────────────────────────────
contract_service = ContractService()
