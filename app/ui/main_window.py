"""
Cửa sổ chính SkillProof.
Navigation: FirstRunSetup (nếu cần) → Welcome → Login → Dashboard → Logout
"""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from client.views.admin_dashboard_screen import AdminDashboardScreen
from client.views.candidate_assessment_screen import CandidateAssessmentScreen
from client.views.candidate_profile_screen import CandidateProfileScreen
from client.views.company_profile_screen import CompanyProfileScreen
from client.views.company_recruitment_screen import CompanyRecruitmentScreen
from client.views.contract_management_screen import ContractManagementScreen
from client.views.candidate_special_assessment_screen import (
    CandidateSpecialAssessmentScreen,
)
from client.views.certificate_screen import CertificateScreen
from client.views.dashboard_screen import DashboardScreen
from client.views.exam_monitor_screen import ExamMonitorScreen
from client.views.expert_profile_screen import ExpertProfileScreen
from client.views.expert_search_screen import ExpertSearchScreen
from client.views.first_run_screen import FirstRunScreen
from client.views.grading_screen import GradingScreen
from client.views.interview_screen import InterviewScreen
from client.views.login_screen import LoginScreen
from client.views.register_screen import RegisterScreen
from client.views.skill_management_screen import SkillManagementScreen
from client.views.task_management_screen import TaskManagementScreen
from client.views.user_management_screen import UserManagementScreen
from client.views.welcome_screen import WelcomeScreen
from client.views.recruitment_contracts import (
    CandidateAssessmentController,
    CompanyRecruitmentController,
)
from client.views.extended_workflow_contracts import (
    CandidateSpecializedAssessmentController,
    CertificateController,
    ExamMonitorController,
    InterviewController,
    ManualGradingController,
)
from app.models.user_model            import UserModel
from server.controllers.admin_controller import AdminController
from server.controllers.auth_controller import auth_controller
from app.utils.constants import (
    APP_NAME,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
)


class MainWindow(QMainWindow):
    """Cửa sổ gốc SkillProof."""

    def __init__(
        self,
        *,
        company_recruitment_controller: CompanyRecruitmentController | None = None,
        candidate_assessment_controller: CandidateAssessmentController | None = None,
        candidate_specialized_assessment_controller: (
            CandidateSpecializedAssessmentController | None
        ) = None,
        manual_grading_controller: ManualGradingController | None = None,
        exam_monitor_controller: ExamMonitorController | None = None,
        interview_controller: InterviewController | None = None,
        certificate_controller: CertificateController | None = None,
    ) -> None:
        super().__init__()
        self._dashboard: DashboardScreen | AdminDashboardScreen | None = None
        self._first_run: FirstRunScreen | None  = None
        self._register:  RegisterScreen | None  = None
        self._company_profile: CompanyProfileScreen | None = None
        self._candidate_profile: CandidateProfileScreen | None = None
        self._expert_profile: ExpertProfileScreen | None = None
        self._expert_search: ExpertSearchScreen | None = None
        self._contracts: ContractManagementScreen | None = None
        self._tasks: TaskManagementScreen | None = None
        self._user_management: UserManagementScreen | None = None
        self._skill_management: SkillManagementScreen | None = None
        self._company_recruitment: CompanyRecruitmentScreen | None = None
        self._candidate_assessments: CandidateAssessmentScreen | None = None
        self._candidate_special_assessments: CandidateSpecialAssessmentScreen | None = None
        self._grading_screen: GradingScreen | None = None
        self._exam_monitor: ExamMonitorScreen | None = None
        self._interview_screen: InterviewScreen | None = None
        self._certificate_screen: CertificateScreen | None = None
        if any(
            controller is None
            for controller in (
                candidate_specialized_assessment_controller,
                manual_grading_controller,
                exam_monitor_controller,
                interview_controller,
                certificate_controller,
            )
        ):
            from app.integration.supplementary_adapters import (
                create_supplementary_view_controllers,
            )

            supplementary_defaults = create_supplementary_view_controllers()
        else:
            supplementary_defaults = (None, None, None, None, None)
        self._candidate_specialized_assessment_controller = (
            candidate_specialized_assessment_controller
            if candidate_specialized_assessment_controller is not None
            else supplementary_defaults[0]
        )
        self._manual_grading_controller = (
            manual_grading_controller
            if manual_grading_controller is not None
            else supplementary_defaults[1]
        )
        self._exam_monitor_controller = (
            exam_monitor_controller
            if exam_monitor_controller is not None
            else supplementary_defaults[2]
        )
        self._interview_controller = (
            interview_controller
            if interview_controller is not None
            else supplementary_defaults[3]
        )
        self._certificate_controller = (
            certificate_controller
            if certificate_controller is not None
            else supplementary_defaults[4]
        )
        self._admin_controller = AdminController()
        if (
            company_recruitment_controller is None
            or candidate_assessment_controller is None
        ):
            from app.integration.recruitment_adapters import (
                create_recruitment_view_controllers,
            )

            default_company_controller, default_candidate_controller = (
                create_recruitment_view_controllers()
            )
        else:
            default_company_controller = None
            default_candidate_controller = None
        self._company_recruitment_controller = (
            company_recruitment_controller
            if company_recruitment_controller is not None
            else default_company_controller
        )
        self._candidate_assessment_controller = (
            candidate_assessment_controller
            if candidate_assessment_controller is not None
            else default_candidate_controller
        )
        self._setup_window()
        self._setup_central_widget()
        self._route_initial()

    # ── Cấu hình cửa sổ ──────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
        screen = self.screen().availableGeometry()
        x = (screen.width()  - WINDOW_DEFAULT_WIDTH)  // 2
        y = (screen.height() - WINDOW_DEFAULT_HEIGHT) // 2
        self.move(x, y)

    def _setup_central_widget(self) -> None:
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

    # ── Routing ban đầu ───────────────────────────────────────────────────────

    def _route_initial(self) -> None:
        """Kiểm tra setup_done để chọn màn hình đầu tiên."""
        from app.database.schema import is_first_run
        if is_first_run():
            self._show_first_run()
        else:
            self._show_welcome()

    # ── FirstRun Setup ────────────────────────────────────────────────────────

    def _show_first_run(self) -> None:
        self._first_run = FirstRunScreen()
        self._first_run.on_setup_complete = self._on_first_run_done
        self._stack.addWidget(self._first_run)
        self._stack.setCurrentWidget(self._first_run)

    def _on_first_run_done(self) -> None:
        """Setup xong → chuyển sang Welcome."""
        self._show_welcome()

    # ── Welcome ───────────────────────────────────────────────────────────────

    def _show_welcome(self) -> None:
        if not hasattr(self, "_welcome"):
            self._welcome = WelcomeScreen()
            self._welcome.on_get_started = self._on_go_to_login
            self._welcome.on_learn_more  = self._on_learn_more
            self._stack.addWidget(self._welcome)
        self._stack.setCurrentWidget(self._welcome)

    # ── Login ─────────────────────────────────────────────────────────────────

    def _show_login(self) -> None:
        if not hasattr(self, "_login"):
            self._login = LoginScreen()
            self._login.on_login_success = self._on_login_success
            self._login.on_back          = self._on_back_to_welcome
            self._login.on_go_register   = self._show_register
            self._stack.addWidget(self._login)
        else:
            self._login.reset()
        self._stack.setCurrentWidget(self._login)

    # ── Register ──────────────────────────────────────────────────────────────

    def _show_register(self) -> None:
        """Hiển thị màn hình đăng ký (tạo mới hoặc reset)."""
        if self._register is not None:
            self._stack.removeWidget(self._register)
            self._register.deleteLater()
            self._register = None

        self._register = RegisterScreen()
        self._register.on_register_success = self._on_register_success
        self._register.on_back_to_login    = self._on_back_to_login
        self._stack.addWidget(self._register)
        self._stack.setCurrentWidget(self._register)

    def _on_register_success(self, user: UserModel) -> None:
        """Đăng ký xong → chuyển về Login để user đăng nhập."""
        self._show_login()

    def _on_back_to_login(self) -> None:
        """Register → Login."""
        self._show_login()

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _show_dashboard(self, user: UserModel) -> None:
        self._discard_admin_screens()
        self._discard_recruitment_screens()
        self._discard_extended_screens()
        if self._dashboard is not None:
            self._stack.removeWidget(self._dashboard)
            self._dashboard.deleteLater()
            self._dashboard = None

        if user.role == "admin":
            dashboard = AdminDashboardScreen(
                user,
                controller=self._admin_controller,
            )
            dashboard.on_logout = self._on_logout
            dashboard.on_open_users = self._show_user_management
            dashboard.on_open_skills = self._show_skill_management
            dashboard.on_open_certificates = self._show_certificates
        else:
            dashboard = DashboardScreen(user)
            dashboard.on_logout = self._on_logout
            dashboard.on_open_candidate_profile = self._show_candidate_profile
            dashboard.on_open_company_profile = self._show_company_profile
            dashboard.on_open_expert_profile = self._show_expert_profile
            dashboard.on_open_expert_search = self._show_expert_search
            dashboard.on_open_contracts = self._show_contracts
            dashboard.on_open_tasks = self._show_tasks
            dashboard.on_open_company_recruitment = self._show_company_recruitment
            dashboard.on_open_candidate_assessments = self._show_candidate_assessments
            dashboard.on_open_extended_workflow = self._show_extended_workflow
        self._dashboard = dashboard
        self._stack.addWidget(self._dashboard)
        self._stack.setCurrentWidget(self._dashboard)

    def _discard_admin_screens(self) -> None:
        for attribute in ("_user_management", "_skill_management"):
            screen = getattr(self, attribute)
            if screen is not None:
                self._stack.removeWidget(screen)
                screen.deleteLater()
                setattr(self, attribute, None)

    def _discard_recruitment_screens(self) -> None:
        for attribute in ("_company_recruitment", "_candidate_assessments"):
            screen = getattr(self, attribute)
            if screen is not None:
                self._stack.removeWidget(screen)
                screen.deleteLater()
                setattr(self, attribute, None)

    def _discard_extended_screens(self) -> None:
        for attribute in (
            "_candidate_special_assessments",
            "_grading_screen",
            "_exam_monitor",
            "_interview_screen",
            "_certificate_screen",
        ):
            screen = getattr(self, attribute)
            if screen is not None:
                self._stack.removeWidget(screen)
                screen.deleteLater()
                setattr(self, attribute, None)

    def _is_admin_session(self) -> bool:
        from app.services.auth_service import SessionManager

        session = SessionManager.instance()
        return bool(
            session.is_logged_in
            and session.current_user is not None
            and session.current_user.role == "admin"
        )

    @staticmethod
    def _has_session_role(role: str) -> bool:
        from app.services.auth_service import SessionManager

        session = SessionManager.instance()
        return bool(
            session.is_logged_in
            and session.current_user is not None
            and session.current_user.role == role
        )

    def _show_user_management(self) -> None:
        if not self._is_admin_session():
            return
        if self._user_management is not None:
            self._stack.removeWidget(self._user_management)
            self._user_management.deleteLater()
        self._user_management = UserManagementScreen(
            controller=self._admin_controller
        )
        self._user_management.on_back = self._on_admin_management_back
        self._stack.addWidget(self._user_management)
        self._stack.setCurrentWidget(self._user_management)

    def _show_skill_management(self) -> None:
        if not self._is_admin_session():
            return
        if self._skill_management is not None:
            self._stack.removeWidget(self._skill_management)
            self._skill_management.deleteLater()
        self._skill_management = SkillManagementScreen(
            controller=self._admin_controller
        )
        self._skill_management.on_back = self._on_admin_management_back
        self._stack.addWidget(self._skill_management)
        self._stack.setCurrentWidget(self._skill_management)

    def _on_admin_management_back(self) -> None:
        if self._dashboard is not None and self._is_admin_session():
            self._stack.setCurrentWidget(self._dashboard)

    def _show_company_recruitment(self) -> None:
        if not self._has_session_role("company"):
            return
        if self._company_recruitment is None:
            self._company_recruitment = CompanyRecruitmentScreen(
                controller=self._company_recruitment_controller
            )
            self._company_recruitment.on_back = self._on_recruitment_back
            self._stack.addWidget(self._company_recruitment)
        else:
            self._company_recruitment.refresh()
        self._stack.setCurrentWidget(self._company_recruitment)

    def _show_candidate_assessments(self) -> None:
        if not self._has_session_role("candidate"):
            return
        if self._candidate_assessments is None:
            self._candidate_assessments = CandidateAssessmentScreen(
                controller=self._candidate_assessment_controller
            )
            self._candidate_assessments.on_back = self._on_recruitment_back
            self._stack.addWidget(self._candidate_assessments)
        else:
            self._candidate_assessments.refresh_invitations()
        self._stack.setCurrentWidget(self._candidate_assessments)

    def _on_recruitment_back(self) -> None:
        if self._dashboard is not None:
            self._stack.setCurrentWidget(self._dashboard)

    def _show_extended_workflow(self, route: str) -> None:
        routes = {
            "candidate_specialized": self._show_candidate_special_assessments,
            "exam_monitor": self._show_exam_monitor,
            "manual_grading": self._show_grading,
            "interviews": self._show_interviews,
            "certificates": self._show_certificates,
        }
        callback = routes.get(route)
        if callback is not None:
            callback()

    def _show_candidate_special_assessments(self) -> None:
        if not self._has_session_role("candidate"):
            return
        if self._candidate_special_assessments is None:
            self._candidate_special_assessments = CandidateSpecialAssessmentScreen(
                controller=self._candidate_specialized_assessment_controller
            )
            self._candidate_special_assessments.on_back = self._on_extended_workflow_back
            self._stack.addWidget(self._candidate_special_assessments)
        else:
            self._candidate_special_assessments.refresh()
        self._stack.setCurrentWidget(self._candidate_special_assessments)

    def _show_exam_monitor(self) -> None:
        if not self._has_session_role("candidate"):
            return
        if self._exam_monitor is None:
            self._exam_monitor = ExamMonitorScreen(
                controller=self._exam_monitor_controller
            )
            self._exam_monitor.on_back = self._on_extended_workflow_back
            self._stack.addWidget(self._exam_monitor)
        else:
            self._exam_monitor.refresh()
        self._stack.setCurrentWidget(self._exam_monitor)

    def _show_grading(self) -> None:
        if not (
            self._has_session_role("company")
            or self._has_session_role("expert")
        ):
            return
        if self._grading_screen is None:
            self._grading_screen = GradingScreen(
                controller=self._manual_grading_controller
            )
            self._grading_screen.on_back = self._on_extended_workflow_back
            self._stack.addWidget(self._grading_screen)
        else:
            self._grading_screen.refresh()
        self._stack.setCurrentWidget(self._grading_screen)

    def _show_interviews(self) -> None:
        from app.services.auth_service import SessionManager

        session = SessionManager.instance()
        if (
            not session.is_logged_in
            or session.current_user is None
            or session.current_user.role not in {"candidate", "company", "expert"}
        ):
            return
        if self._interview_screen is None:
            self._interview_screen = InterviewScreen(
                role=session.current_user.role,
                controller=self._interview_controller,
            )
            self._interview_screen.on_back = self._on_extended_workflow_back
            self._stack.addWidget(self._interview_screen)
        else:
            self._interview_screen.refresh()
        self._stack.setCurrentWidget(self._interview_screen)

    def _show_certificates(self) -> None:
        from app.services.auth_service import SessionManager

        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return
        role = session.current_user.role
        if role not in {"candidate", "company", "expert", "admin"}:
            return
        if self._certificate_screen is None:
            self._certificate_screen = CertificateScreen(
                role=role,
                controller=self._certificate_controller,
            )
            self._certificate_screen.on_back = self._on_extended_workflow_back
            self._stack.addWidget(self._certificate_screen)
        else:
            self._certificate_screen.refresh()
        self._stack.setCurrentWidget(self._certificate_screen)

    def _on_extended_workflow_back(self) -> None:
        if self._dashboard is not None:
            self._stack.setCurrentWidget(self._dashboard)

    # ── Company Profile ───────────────────────────────────────────────────────

    def _show_company_profile(self) -> None:
        """Hiển thị màn hình hồ sơ doanh nghiệp (chỉ role='company')."""
        from app.services.auth_service import SessionManager
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return
        if session.current_user.role != "company":
            return  # Không hiển thị cho role khác

        if self._company_profile is not None:
            self._stack.removeWidget(self._company_profile)
            self._company_profile.deleteLater()
            self._company_profile = None

        self._company_profile = CompanyProfileScreen()
        self._company_profile.on_back = self._on_company_profile_back
        self._stack.addWidget(self._company_profile)
        self._stack.setCurrentWidget(self._company_profile)

    def _on_company_profile_back(self) -> None:
        """Company Profile → Dashboard."""
        if self._dashboard is not None:
            self._stack.setCurrentWidget(self._dashboard)

    # ── Candidate Profile ──────────────────────────────────────────────────────

    def _show_candidate_profile(self) -> None:
        """Hiển thị màn hình hồ sơ ứng viên (chỉ role='candidate')."""
        from app.services.auth_service import SessionManager
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return
        if session.current_user.role != "candidate":
            return

        if self._candidate_profile is not None:
            self._stack.removeWidget(self._candidate_profile)
            self._candidate_profile.deleteLater()
            self._candidate_profile = None

        self._candidate_profile = CandidateProfileScreen()
        self._candidate_profile.on_back = self._on_candidate_profile_back
        self._stack.addWidget(self._candidate_profile)
        self._stack.setCurrentWidget(self._candidate_profile)

    def _on_candidate_profile_back(self) -> None:
        """Candidate Profile → Dashboard."""
        if self._dashboard is not None:
            self._stack.setCurrentWidget(self._dashboard)

    # ── Expert Profile ────────────────────────────────────────────────────────

    def _show_expert_profile(self) -> None:
        """Hiển thị màn hình hồ sơ chuyên gia (chỉ role='expert')."""
        from app.services.auth_service import SessionManager
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return
        if session.current_user.role != "expert":
            return

        if self._expert_profile is not None:
            self._stack.removeWidget(self._expert_profile)
            self._expert_profile.deleteLater()
            self._expert_profile = None

        self._expert_profile = ExpertProfileScreen()
        self._expert_profile.on_back = self._on_expert_profile_back
        self._stack.addWidget(self._expert_profile)
        self._stack.setCurrentWidget(self._expert_profile)

    def _on_expert_profile_back(self) -> None:
        """Expert Profile → Dashboard."""
        if self._dashboard is not None:
            self._stack.setCurrentWidget(self._dashboard)

    # ── Expert Search ─────────────────────────────────────────────────────────

    def _show_expert_search(self) -> None:
        """Hiển thị màn hình tìm kiếm chuyên gia (chỉ role='company')."""
        from app.services.auth_service import SessionManager
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return
        if session.current_user.role != "company":
            return

        if self._expert_search is not None:
            self._stack.removeWidget(self._expert_search)
            self._expert_search.deleteLater()
            self._expert_search = None

        self._expert_search = ExpertSearchScreen()
        self._expert_search.on_back = self._on_expert_search_back
        self._expert_search.on_view_contracts = self._show_contracts
        self._stack.addWidget(self._expert_search)
        self._stack.setCurrentWidget(self._expert_search)

    def _on_expert_search_back(self) -> None:
        """Expert Search → Dashboard."""
        if self._dashboard is not None:
            self._stack.setCurrentWidget(self._dashboard)

    # ── Contract Management ───────────────────────────────────────────────────

    def _show_contracts(self) -> None:
        """Hiển thị màn hình quản lý hợp đồng (company hoặc expert)."""
        from app.services.auth_service import SessionManager
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return
        if session.current_user.role not in ("company", "expert"):
            return

        if self._contracts is not None:
            self._stack.removeWidget(self._contracts)
            self._contracts.deleteLater()
            self._contracts = None

        self._contracts = ContractManagementScreen()
        self._contracts.on_back = self._on_contracts_back
        self._contracts.on_find_experts = self._show_expert_search
        self._stack.addWidget(self._contracts)
        self._stack.setCurrentWidget(self._contracts)

    def _on_contracts_back(self) -> None:
        """Contract Management → Dashboard."""
        if self._dashboard is not None:
            self._stack.setCurrentWidget(self._dashboard)

    # ── Task Management ───────────────────────────────────────────────────────

    def _show_tasks(self) -> None:
        """Hiển thị màn hình quản lý nhiệm vụ (company hoặc expert)."""
        from app.services.auth_service import SessionManager
        session = SessionManager.instance()
        if not session.is_logged_in or session.current_user is None:
            return
        if session.current_user.role not in ("company", "expert"):
            return

        if self._tasks is not None:
            self._stack.removeWidget(self._tasks)
            self._tasks.deleteLater()
            self._tasks = None

        self._tasks = TaskManagementScreen()
        self._tasks.on_back = self._on_tasks_back
        self._stack.addWidget(self._tasks)
        self._stack.setCurrentWidget(self._tasks)

    def _on_tasks_back(self) -> None:
        """Task Management → Dashboard."""
        if self._dashboard is not None:
            self._stack.setCurrentWidget(self._dashboard)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_go_to_login(self) -> None:
        self._show_login()

    def _on_back_to_welcome(self) -> None:
        self._stack.setCurrentWidget(self._welcome)

    def _on_login_success(self, user: UserModel) -> None:
        self._show_dashboard(user)

    def _on_logout(self) -> None:
        self._discard_admin_screens()
        self._discard_recruitment_screens()
        self._discard_extended_screens()
        self._show_login()

    def _on_learn_more(self) -> None:
        QMessageBox.information(
            self, "Về SkillProof",
            f"<b>{APP_NAME}</b><br><br>"
            "Hệ thống quản lý và chứng nhận kỹ năng chuyên nghiệp.<br><br>"
            "<b>Tính năng:</b><br>"
            "• Quản lý hồ sơ kỹ năng<br>"
            "• Đánh giá năng lực theo chuẩn<br>"
            "• Cấp và xác thực chứng chỉ<br>"
            "• Theo dõi lộ trình học tập",
        )

    # ── Đóng ứng dụng ────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        from app.database.connection import db
        from app.services.auth_service import auth_service
        auth_controller.logout()
        db.close()
        event.accept()
