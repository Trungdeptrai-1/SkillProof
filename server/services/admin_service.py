"""Administrator use cases for users, skills, and dashboard statistics."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from app.database.connection import db
from server.models.user_model import ROLE_LABELS, UserModel
from server.services.auth_service import SessionManager

logger = logging.getLogger(__name__)

ADMIN_USER_ROLES = tuple(ROLE_LABELS)
SKILL_LEVELS = ("beginner", "intermediate", "advanced", "expert")


@dataclass(frozen=True)
class ManagedSkill:
    """Read model for the fields currently stored in the skills table."""

    id: int
    name: str
    description: str | None
    category: str | None
    level: str
    is_active: bool
    created_at: str

    @classmethod
    def from_row(cls, row) -> "ManagedSkill":
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            category=row["category"],
            level=row["level"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class AdminStatistics:
    total_users: int
    active_users: int
    inactive_users: int
    deleted_users: int
    users_by_role: dict[str, int]
    candidate_profiles: int
    company_profiles: int
    expert_profiles: int
    total_skills: int
    active_skills: int
    inactive_skills: int


class AdminResult:
    SUCCESS = "success"
    NOT_LOGGED_IN = "not_logged_in"
    FORBIDDEN = "forbidden"
    INVALID_INPUT = "invalid_input"
    INVALID_ROLE = "invalid_role"
    INVALID_SKILL_LEVEL = "invalid_skill_level"
    EMPTY_SKILL_NAME = "empty_skill_name"
    USER_NOT_FOUND = "user_not_found"
    LAST_ACTIVE_ADMIN = "last_active_admin"
    SKILL_NOT_FOUND = "skill_not_found"
    SKILL_ALREADY_EXISTS = "skill_already_exists"
    DB_ERROR = "db_error"

    MESSAGES = {
        SUCCESS: "Thao tác thành công.",
        NOT_LOGGED_IN: "Vui lòng đăng nhập trước.",
        FORBIDDEN: "Chỉ quản trị viên mới được phép thực hiện thao tác này.",
        INVALID_INPUT: "Dữ liệu đầu vào không hợp lệ.",
        INVALID_ROLE: "Vai trò người dùng không hợp lệ.",
        INVALID_SKILL_LEVEL: "Cấp độ kỹ năng không hợp lệ.",
        EMPTY_SKILL_NAME: "Tên kỹ năng không được để trống.",
        USER_NOT_FOUND: "Không tìm thấy tài khoản.",
        LAST_ACTIVE_ADMIN: "Không thể vô hiệu hóa quản trị viên đang hoạt động cuối cùng.",
        SKILL_NOT_FOUND: "Không tìm thấy kỹ năng.",
        SKILL_ALREADY_EXISTS: "Tên kỹ năng đã tồn tại.",
        DB_ERROR: "Lỗi cơ sở dữ liệu. Vui lòng thử lại.",
    }

    def __init__(
        self,
        status: str,
        *,
        users: list[UserModel] | None = None,
        user: UserModel | None = None,
        skills: list[ManagedSkill] | None = None,
        skill: ManagedSkill | None = None,
        statistics: AdminStatistics | None = None,
    ) -> None:
        self.status = status
        self.users = users if users is not None else []
        self.user = user
        self.skills = skills if skills is not None else []
        self.skill = skill
        self.statistics = statistics
        self.success = status == self.SUCCESS
        self.message = self.MESSAGES.get(status, "Đã xảy ra lỗi không xác định.")


class AdminService:
    """Authorize and execute administrative operations using the shared DB."""

    @staticmethod
    def _authorization_error() -> AdminResult | None:
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return AdminResult(AdminResult.NOT_LOGGED_IN)
        if session.current_user.role != "admin":
            return AdminResult(AdminResult.FORBIDDEN)
        try:
            account = db.fetchone(
                """
                SELECT role, is_active, is_deleted
                FROM users
                WHERE id = ?
                """,
                (session.current_user.id,),
            )
        except sqlite3.Error as exc:
            logger.error("Database error validating admin session: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)
        if (
            account is None
            or account["role"] != "admin"
            or not account["is_active"]
            or account["is_deleted"]
        ):
            session.end_session()
            return AdminResult(AdminResult.FORBIDDEN)
        return None

    @staticmethod
    def _is_valid_id(value: int) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    def list_users(
        self,
        search: str = "",
        role: str | None = None,
        is_active: bool | None = None,
    ) -> AdminResult:
        denied = self._authorization_error()
        if denied:
            return denied
        if not isinstance(search, str):
            return AdminResult(AdminResult.INVALID_INPUT)
        if role is not None:
            if not isinstance(role, str):
                return AdminResult(AdminResult.INVALID_INPUT)
            if role not in ADMIN_USER_ROLES:
                return AdminResult(AdminResult.INVALID_ROLE)
        if is_active is not None and not isinstance(is_active, bool):
            return AdminResult(AdminResult.INVALID_INPUT)

        conditions = ["is_deleted = 0"]
        params: list[str | int] = []
        term = search.strip()
        if term:
            conditions.append(
                "(username LIKE ? COLLATE NOCASE "
                "OR email LIKE ? COLLATE NOCASE "
                "OR full_name LIKE ? COLLATE NOCASE)"
            )
            pattern = f"%{term}%"
            params.extend((pattern, pattern, pattern))
        if role is not None:
            conditions.append("role = ?")
            params.append(role)
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(int(is_active))

        try:
            rows = db.fetchall(
                f"""
                SELECT id, username, email, full_name, role, avatar_path,
                       is_active, created_at, updated_at
                FROM users
                WHERE {" AND ".join(conditions)}
                ORDER BY created_at DESC, id DESC
                """,
                tuple(params),
            )
        except sqlite3.Error as exc:
            logger.error("Database error listing admin users: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)

        return AdminResult(
            AdminResult.SUCCESS,
            users=[UserModel.from_row(row) for row in rows],
        )

    def set_user_active(self, user_id: int, is_active: bool) -> AdminResult:
        denied = self._authorization_error()
        if denied:
            return denied
        if not self._is_valid_id(user_id) or not isinstance(is_active, bool):
            return AdminResult(AdminResult.INVALID_INPUT)

        connection = None
        try:
            connection = db.get_connection()
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT id, username, email, full_name, role, avatar_path,
                       is_active, created_at, updated_at
                FROM users
                WHERE id = ? AND is_deleted = 0
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                return AdminResult(AdminResult.USER_NOT_FOUND)

            if row["role"] == "admin" and row["is_active"] and not is_active:
                active_admins = connection.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM users
                    WHERE role = 'admin' AND is_active = 1 AND is_deleted = 0
                    """
                ).fetchone()["total"]
                if active_admins <= 1:
                    connection.rollback()
                    return AdminResult(AdminResult.LAST_ACTIVE_ADMIN)

            connection.execute(
                "UPDATE users SET is_active = ? WHERE id = ?",
                (int(is_active), user_id),
            )
            updated = connection.execute(
                """
                SELECT id, username, email, full_name, role, avatar_path,
                       is_active, created_at, updated_at
                FROM users WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
            connection.commit()
        except sqlite3.Error as exc:
            if connection is not None and connection.in_transaction:
                connection.rollback()
            logger.error("Database error changing user status: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)

        return AdminResult(
            AdminResult.SUCCESS,
            user=UserModel.from_row(updated),
        )

    def get_statistics(self) -> AdminResult:
        denied = self._authorization_error()
        if denied:
            return denied

        try:
            user_counts = db.fetchone(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END), 0) AS active,
                    COALESCE(SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END), 0) AS inactive
                FROM users
                WHERE is_deleted = 0
                """
            )
            deleted_count = db.fetchone(
                "SELECT COUNT(*) AS total FROM users WHERE is_deleted = 1"
            )["total"]
            role_rows = db.fetchall(
                """
                SELECT role, COUNT(*) AS total
                FROM users
                WHERE is_deleted = 0
                GROUP BY role
                """
            )
            profile_counts = db.fetchone(
                """
                SELECT
                    (SELECT COUNT(*) FROM candidate_profiles) AS candidates,
                    (SELECT COUNT(*) FROM company_profiles) AS companies,
                    (SELECT COUNT(*) FROM expert_profiles) AS experts,
                    (SELECT COUNT(*) FROM skills) AS skills,
                    (SELECT COUNT(*) FROM skills WHERE is_active = 1) AS active_skills,
                    (SELECT COUNT(*) FROM skills WHERE is_active = 0) AS inactive_skills
                """
            )
        except sqlite3.Error as exc:
            logger.error("Database error retrieving admin statistics: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)

        users_by_role = {role: 0 for role in ADMIN_USER_ROLES}
        for row in role_rows:
            users_by_role[row["role"]] = row["total"]

        return AdminResult(
            AdminResult.SUCCESS,
            statistics=AdminStatistics(
                total_users=user_counts["total"],
                active_users=user_counts["active"],
                inactive_users=user_counts["inactive"],
                deleted_users=deleted_count,
                users_by_role=users_by_role,
                candidate_profiles=profile_counts["candidates"],
                company_profiles=profile_counts["companies"],
                expert_profiles=profile_counts["experts"],
                total_skills=profile_counts["skills"],
                active_skills=profile_counts["active_skills"],
                inactive_skills=profile_counts["inactive_skills"],
            ),
        )

    def list_skills(
        self,
        search: str = "",
        category: str | None = None,
        level: str | None = None,
        is_active: bool | None = None,
    ) -> AdminResult:
        denied = self._authorization_error()
        if denied:
            return denied
        if not isinstance(search, str):
            return AdminResult(AdminResult.INVALID_INPUT)
        if category is not None and not isinstance(category, str):
            return AdminResult(AdminResult.INVALID_INPUT)
        if level is not None:
            if not isinstance(level, str):
                return AdminResult(AdminResult.INVALID_INPUT)
            if level not in SKILL_LEVELS:
                return AdminResult(AdminResult.INVALID_SKILL_LEVEL)
        if is_active is not None and not isinstance(is_active, bool):
            return AdminResult(AdminResult.INVALID_INPUT)

        conditions: list[str] = []
        params: list[str | int] = []
        term = search.strip()
        if term:
            pattern = f"%{term}%"
            conditions.append(
                "(name LIKE ? COLLATE NOCASE "
                "OR COALESCE(description, '') LIKE ? COLLATE NOCASE "
                "OR COALESCE(category, '') LIKE ? COLLATE NOCASE)"
            )
            params.extend((pattern, pattern, pattern))
        if category and category.strip():
            conditions.append("category = ? COLLATE NOCASE")
            params.append(category.strip())
        if level is not None:
            conditions.append("level = ?")
            params.append(level)
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(int(is_active))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        try:
            rows = db.fetchall(
                f"""
                SELECT id, name, description, category, level, is_active, created_at
                FROM skills
                {where}
                ORDER BY name COLLATE NOCASE, id
                """,
                tuple(params),
            )
        except sqlite3.Error as exc:
            logger.error("Database error listing admin skills: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)

        return AdminResult(
            AdminResult.SUCCESS,
            skills=[ManagedSkill.from_row(row) for row in rows],
        )

    def create_skill(
        self,
        name: str,
        description: str = "",
        category: str = "",
        level: str = "beginner",
    ) -> AdminResult:
        denied = self._authorization_error()
        if denied:
            return denied
        invalid = self._validate_skill(name, description, category, level)
        if invalid:
            return invalid

        try:
            connection = db.get_connection()
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO skills (name, description, category, level)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name.strip(),
                        description.strip() or None,
                        category.strip() or None,
                        level,
                    ),
                )
                row = connection.execute(
                    """
                    SELECT id, name, description, category, level, is_active, created_at
                    FROM skills WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: skills.name" in str(exc):
                logger.info("Duplicate skill rejected by database constraint: %s", exc)
                return AdminResult(AdminResult.SKILL_ALREADY_EXISTS)
            logger.error("Database integrity error creating admin skill: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)
        except sqlite3.Error as exc:
            logger.error("Database error creating admin skill: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)

        return AdminResult(
            AdminResult.SUCCESS,
            skill=ManagedSkill.from_row(row),
        )

    def update_skill(
        self,
        skill_id: int,
        name: str,
        description: str = "",
        category: str = "",
        level: str = "beginner",
    ) -> AdminResult:
        denied = self._authorization_error()
        if denied:
            return denied
        if not self._is_valid_id(skill_id):
            return AdminResult(AdminResult.INVALID_INPUT)
        invalid = self._validate_skill(name, description, category, level)
        if invalid:
            return invalid

        try:
            connection = db.get_connection()
            with connection:
                existing = connection.execute(
                    "SELECT id FROM skills WHERE id = ?",
                    (skill_id,),
                ).fetchone()
                if existing is None:
                    return AdminResult(AdminResult.SKILL_NOT_FOUND)
                connection.execute(
                    """
                    UPDATE skills
                    SET name = ?, description = ?, category = ?, level = ?
                    WHERE id = ?
                    """,
                    (
                        name.strip(),
                        description.strip() or None,
                        category.strip() or None,
                        level,
                        skill_id,
                    ),
                )
                row = connection.execute(
                    """
                    SELECT id, name, description, category, level, is_active, created_at
                    FROM skills WHERE id = ?
                    """,
                    (skill_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: skills.name" in str(exc):
                logger.info("Duplicate skill update rejected by database constraint: %s", exc)
                return AdminResult(AdminResult.SKILL_ALREADY_EXISTS)
            logger.error("Database integrity error updating admin skill: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)
        except sqlite3.Error as exc:
            logger.error("Database error updating admin skill: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)

        return AdminResult(
            AdminResult.SUCCESS,
            skill=ManagedSkill.from_row(row),
        )

    def set_skill_active(self, skill_id: int, is_active: bool) -> AdminResult:
        denied = self._authorization_error()
        if denied:
            return denied
        if not self._is_valid_id(skill_id) or not isinstance(is_active, bool):
            return AdminResult(AdminResult.INVALID_INPUT)

        try:
            connection = db.get_connection()
            with connection:
                existing = connection.execute(
                    "SELECT id FROM skills WHERE id = ?",
                    (skill_id,),
                ).fetchone()
                if existing is None:
                    return AdminResult(AdminResult.SKILL_NOT_FOUND)
                connection.execute(
                    "UPDATE skills SET is_active = ? WHERE id = ?",
                    (int(is_active), skill_id),
                )
                row = connection.execute(
                    """
                    SELECT id, name, description, category, level, is_active, created_at
                    FROM skills WHERE id = ?
                    """,
                    (skill_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            logger.error("Database error changing skill status: %s", exc)
            return AdminResult(AdminResult.DB_ERROR)

        return AdminResult(
            AdminResult.SUCCESS,
            skill=ManagedSkill.from_row(row),
        )

    @staticmethod
    def _validate_skill(
        name: str,
        description: str,
        category: str,
        level: str,
    ) -> AdminResult | None:
        if not all(
            isinstance(value, str)
            for value in (name, description, category, level)
        ):
            return AdminResult(AdminResult.INVALID_INPUT)
        if not name.strip():
            return AdminResult(AdminResult.EMPTY_SKILL_NAME)
        if level not in SKILL_LEVELS:
            return AdminResult(AdminResult.INVALID_SKILL_LEVEL)
        return None


admin_service = AdminService()
