import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from app.utils.helpers import hash_password
from client.views.candidate_assessment_screen import CandidateAssessmentScreen
from client.views.company_recruitment_screen import CompanyRecruitmentScreen
from client.views.recruitment_contracts import (
    ActionResult,
    Assessment,
    AssessmentResultRow,
    Candidate,
    CandidateInvitation,
    CandidateResult,
    CandidateResultResponse,
    ExamDetails,
    ExamLoadResult,
    ExamOption,
    ExamQuestion,
    ListResult,
    Position,
    QuestionDraft,
    QuestionAuthor,
    SubmitResult,
)


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


class CompanyRecruitmentMock:
    def __init__(self):
        self.positions = [
            Position(
                3,
                "Python Developer",
                "Hanoi",
                "published",
                "API role",
                "Python",
            )
        ]
        self.assessments = [Assessment(5, "Python Basics", 30, 2)]
        self.candidates = [Candidate(8, "Candidate QA", "candidate@example.test")]
        self.question_authors = [
            QuestionAuthor(77, "Expert QA", "expert@example.test")
        ]
        self.results = [
            AssessmentResultRow(
                "Candidate QA",
                "Python Developer",
                "Python Basics",
                8,
                10,
                "graded",
                "2026-11-23 10:00",
                exam_id=5,
                invitation_id=41,
            )
        ]
        self.created_positions = []
        self.updated_positions = []
        self.created_assessments = []
        self.invitations = []
        self.released_exams = []

    def list_positions(self):
        return ListResult(True, tuple(self.positions))

    def create_position(
        self, title, description, requirements, location, status
    ):
        self.created_positions.append(
            (title, description, requirements, location, status)
        )
        return ActionResult(True)

    def update_position(
        self, position_id, title, description, requirements, location, status
    ):
        self.updated_positions.append(
            (position_id, title, description, requirements, location, status)
        )
        return ActionResult(True)

    def list_assessments(self):
        return ListResult(True, tuple(self.assessments))

    def list_contracted_experts(self):
        return ListResult(True, tuple(self.question_authors))

    def create_assessment(
        self, title, description, duration_minutes, questions, *, expert_id
    ):
        self.created_assessments.append(
            (title, description, duration_minutes, questions, expert_id)
        )
        return ActionResult(True)

    def list_candidates(self, search=""):
        candidates = tuple(
            candidate
            for candidate in self.candidates
            if search.casefold() in candidate.full_name.casefold()
            or search.casefold() in candidate.email.casefold()
        )
        return ListResult(True, candidates)

    def send_invitation(self, position_id, assessment_id, candidate_id):
        self.invitations.append((position_id, assessment_id, candidate_id))
        return ActionResult(True)

    def list_results(self):
        return ListResult(True, tuple(self.results))

    def release_results(self, exam_id):
        self.released_exams.append(exam_id)
        return ActionResult(True)


class CandidateAssessmentMock:
    def __init__(self):
        self.invitations = [
            CandidateInvitation(
                41,
                "SkillProof Co.",
                "Python Developer",
                "Python Basics",
                30,
                "scheduled",
            )
        ]
        self.exam = ExamDetails(
            41,
            "Python Basics",
            30,
            (
                ExamQuestion(
                    11,
                    "Which type is immutable?",
                    (
                        ExamOption(101, "list"),
                        ExamOption(102, "tuple"),
                    ),
                ),
                ExamQuestion(
                    12,
                    "Which keyword defines a function?",
                    (
                        ExamOption(103, "func"),
                        ExamOption(104, "def"),
                    ),
                ),
            ),
        )
        self.saved_answers = []
        self.submit_calls = []
        self.fail_invitation_refresh = False
        self.exam_response = ExamLoadResult(True, self.exam)
        self.submit_response = SubmitResult(
            True,
            CandidateResult(41, 8, 10, "completed", "2026-11-23 10:00"),
        )

    def list_invitations(self):
        if self.fail_invitation_refresh:
            return ListResult(False, message="Invitation refresh failed")
        return ListResult(True, tuple(self.invitations))

    def get_exam(self, invitation_id):
        assert invitation_id == 41
        return self.exam_response

    def save_answer(self, invitation_id, question_id, option_id):
        self.saved_answers.append((invitation_id, question_id, option_id))
        return ActionResult(True)

    def submit_exam(self, invitation_id):
        self.submit_calls.append(invitation_id)
        return self.submit_response

    def get_result(self, invitation_id):
        return CandidateResultResponse(
            True,
            CandidateResult(invitation_id, 8, 10, "completed"),
        )


def _button(widget, label):
    return next(
        button
        for button in widget.findChildren(QPushButton)
        if button.text().strip().endswith(label)
    )


def test_company_recruitment_views_validate_and_call_controller(qt_app):
    controller = CompanyRecruitmentMock()
    screen = CompanyRecruitmentScreen(controller)

    assert screen._positions_table.rowCount() == 1
    assert screen._assessments_table.rowCount() == 1
    assert screen._results_table.rowCount() == 1

    screen._positions_table.selectRow(0)
    assert screen._position_edit.isEnabled()
    screen._position_edit.click()
    screen._position_title.setText("Senior Python Developer")
    screen._position_save.click()
    assert controller.updated_positions == [
        (3, "Senior Python Developer", "API role", "Python", "Hanoi", "published")
    ]

    screen._position_title.setText("")
    screen._position_save.click()
    assert "bắt buộc" in screen._status.text()
    assert len(controller.created_positions) == 0
    screen._position_title.setText("Data Analyst")
    screen._position_location.setText("Remote")
    screen._position_description.setPlainText("Analytics role")
    screen._position_requirements.setPlainText("SQL")
    screen._position_status.setCurrentIndex(
        screen._position_status.findData("published")
    )
    screen._position_save.click()
    assert controller.created_positions == [
        ("Data Analyst", "Analytics role", "SQL", "Remote", "published")
    ]

    screen._question_prompt.setText("Which type is immutable?")
    screen._question_options[0].setText("list")
    screen._question_options[1].setText("tuple")
    screen._correct_option.setCurrentIndex(1)
    screen._question_add.click()
    assert screen._questions_table.rowCount() == 1
    screen._assessment_title.setText("Python Fundamentals")
    screen._assessment_create.click()
    assert controller.created_assessments == [
        (
            "Python Fundamentals",
            "",
            60,
            (QuestionDraft("Which type is immutable?", ("list", "tuple"), 1),),
            77,
        )
    ]

    screen._invite_position.setCurrentIndex(0)
    screen._invite_assessment.setCurrentIndex(0)
    screen._invite_candidate.setCurrentIndex(0)
    screen._send_invitation.click()
    assert controller.invitations == [(3, 5, 8)]
    assert screen._candidates_status.text() == "Đã tìm thấy 1 ứng viên."
    screen._results_table.selectRow(0)
    assert screen._results_release.isEnabled()
    screen._results_release.click()
    assert controller.released_exams == [5]
    screen.deleteLater()


def test_company_controller_errors_empty_and_unavailable_states(qt_app):
    unavailable = CompanyRecruitmentScreen()
    assert not unavailable._position_save.isEnabled()
    assert "chưa được cung cấp" in unavailable._status.text()

    class EmptyController(CompanyRecruitmentMock):
        def list_positions(self):
            return ListResult(True)

        def list_assessments(self):
            return ListResult(False, message="Assessment API unavailable")

        def list_candidates(self, search=""):
            return ListResult(True)

        def list_results(self):
            return ListResult(True)

    screen = CompanyRecruitmentScreen(EmptyController())
    assert screen._positions_table.rowCount() == 0
    assert screen._positions_status.text() == "Chưa có vị trí tuyển dụng."
    assert screen._assessments_status.text() == "Assessment API unavailable"
    assert screen._candidates_status.text() == "Không tìm thấy ứng viên."
    assert "Assessment API unavailable" in screen._status.text()
    screen.deleteLater()
    unavailable.deleteLater()


def test_company_cannot_create_exam_without_contracted_question_author(qt_app):
    class NoContractedExperts(CompanyRecruitmentMock):
        def list_contracted_experts(self):
            return ListResult(True)

    screen = CompanyRecruitmentScreen(NoContractedExperts())

    assert not screen._assessment_create.isEnabled()
    assert "Chưa có Expert" in screen._question_author_status.text()
    screen.deleteLater()


def test_candidate_saves_answers_confirms_and_prevents_duplicate_submission(
    qt_app, monkeypatch
):
    controller = CandidateAssessmentMock()
    screen = CandidateAssessmentScreen(controller)
    assert screen._invitations_table.rowCount() == 1
    screen._invitations_table.selectRow(0)
    screen._start_exam_button.click()
    assert screen._tabs.currentWidget() is screen._exam_tab
    assert screen._question_counter.text() == "Câu 1 / 2"

    screen._save_answer_button.click()
    assert "Chọn một đáp án" in screen._status.text()
    assert controller.saved_answers == []
    screen._option_buttons[102].click()
    screen._save_answer_button.click()
    assert controller.saved_answers == [(41, 11, 102)]
    assert screen._progress_label.text() == "Đã lưu 1 / 2 đáp án"

    screen._next_question.click()
    assert screen._question_counter.text() == "Câu 2 / 2"
    screen._previous_question.click()
    assert screen._question_counter.text() == "Câu 1 / 2"

    screen._option_buttons[101].click()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    screen._submit_exam_button.click()
    assert controller.submit_calls == []
    assert "Lưu các đáp án" in screen._status.text()
    screen._option_buttons[102].click()

    controller.fail_invitation_refresh = True
    answers = iter(
        (
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: next(answers)
    )
    screen._submit_exam_button.click()
    assert controller.submit_calls == []
    assert not screen._submitted

    screen._submit_exam_button.click()
    assert controller.submit_calls == [41]
    assert screen._submitted
    assert not screen._submit_exam_button.isEnabled()
    assert screen._result_score.text() == "Điểm: 8 / 10"
    assert "Invitation refresh failed" in screen._status.text()
    screen._submit_exam()
    assert controller.submit_calls == [41]
    screen.deleteLater()


def test_candidate_submission_failure_can_retry_and_empty_inbox_is_visible(
    qt_app, monkeypatch
):
    controller = CandidateAssessmentMock()
    controller.submit_response = SubmitResult(False, message="Temporary failure")
    screen = CandidateAssessmentScreen(controller)
    screen._invitations_table.selectRow(0)
    screen._open_selected_exam()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    screen._submit_exam()
    assert controller.submit_calls == [41]
    assert not screen._submitted
    assert screen._submit_exam_button.isEnabled()
    assert screen._status.text() == "Temporary failure"

    class EmptyController(CandidateAssessmentMock):
        def list_invitations(self):
            return ListResult(True)

    empty = CandidateAssessmentScreen(EmptyController())
    assert empty._invitations_table.rowCount() == 0
    assert empty._status.text() == "Bạn chưa có lời mời làm bài."
    screen.deleteLater()
    empty.deleteLater()


def test_candidate_exam_load_failure_clears_previous_exam_and_controls(qt_app):
    controller = CandidateAssessmentMock()
    screen = CandidateAssessmentScreen(controller)
    screen._invitations_table.selectRow(0)
    screen._open_selected_exam()
    assert screen._exam is not None

    controller.exam_response = ExamLoadResult(False, message="Exam unavailable")
    screen._open_selected_exam()
    assert screen._exam is None
    assert screen._active_invitation is None
    assert not screen._submit_exam_button.isEnabled()
    assert screen._status.text() == "Exam unavailable"
    screen.deleteLater()


def test_candidate_screen_without_controller_disables_exam_actions(qt_app):
    screen = CandidateAssessmentScreen()
    assert not screen._invitations_refresh.isEnabled()
    assert not screen._save_answer_button.isEnabled()
    assert not screen._submit_exam_button.isEnabled()
    assert "chưa được cung cấp" in screen._status.text()
    screen.deleteLater()


@pytest.mark.parametrize(
    ("role", "menu_label", "screen_attribute"),
    [
        ("company", "Tuyển dụng & đánh giá", "_company_recruitment"),
        ("candidate", "Lời mời làm bài", "_candidate_assessments"),
    ],
)
def test_main_window_routes_recruitment_views_by_role(
    fresh_db,
    auth,
    qt_app,
    monkeypatch,
    role,
    menu_label,
    screen_attribute,
):
    import app.database.schema as schema
    from app.ui.main_window import MainWindow
    from app.utils.helpers import hash_password

    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    email = f"{role}@recruitment.example.test"
    fresh_db.execute(
        "INSERT INTO users(username,email,password,full_name,role,is_active) "
        "VALUES(?,?,?,?,?,1)",
        (role, email, hash_password("RecruitmentPass1"), role.title(), role),
    )
    login = auth.login(email, "RecruitmentPass1")
    assert login.success

    company_controller = CompanyRecruitmentMock()
    candidate_controller = CandidateAssessmentMock()
    window = MainWindow(
        company_recruitment_controller=company_controller,
        candidate_assessment_controller=candidate_controller,
    )
    window._show_dashboard(login.user)
    _button(window._dashboard, menu_label).click()

    screen = getattr(window, screen_attribute)
    assert screen is not None
    assert window._stack.currentWidget() is screen
    assert screen._controller is (
        company_controller if role == "company" else candidate_controller
    )
    if role == "candidate":
        screen._submitted_invitation_ids.add(41)
        screen.on_back()
        _button(window._dashboard, menu_label).click()
        assert window._candidate_assessments is screen
        screen._invitations_table.selectRow(0)
        assert not screen._start_exam_button.isEnabled()
    window.close()


def test_main_window_uses_real_recruitment_adapters_by_default(
    fresh_db, auth, qt_app, monkeypatch
):
    import app.database.schema as schema
    from app.integration.recruitment_adapters import (
        CandidateAssessmentAdapter,
        CompanyRecruitmentAdapter,
    )
    from app.ui.main_window import MainWindow
    from app.utils.helpers import hash_password

    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    email = "default-company@recruitment.example.test"
    password = "RecruitmentPass1"
    fresh_db.execute(
        """
        INSERT INTO users(username,email,password,full_name,role,is_active)
        VALUES(?,?,?,?,?,1)
        """,
        ("default-company", email, hash_password(password), "Default Company", "company"),
    )
    login = auth.login(email, password)
    assert login.success

    window = MainWindow()
    assert isinstance(
        window._company_recruitment_controller, CompanyRecruitmentAdapter
    )
    assert isinstance(
        window._candidate_assessment_controller, CandidateAssessmentAdapter
    )
    window._show_dashboard(login.user)
    _button(window._dashboard, "Tuyển dụng & đánh giá").click()
    assert window._company_recruitment is not None
    assert window._company_recruitment._position_save.isEnabled()
    assert window._company_recruitment._positions_table.rowCount() == 0
    window.close()


def _create_user(database, username, role):
    email = f"{username}@recruitment.example.test"
    password = "RecruitmentPass1"
    database.execute(
        """
        INSERT INTO users
            (username, email, password, full_name, role, is_active, is_deleted)
        VALUES (?, ?, ?, ?, ?, 1, 0)
        """,
        (username, email, hash_password(password), username.title(), role),
    )
    return email, password


def test_company_and_candidate_complete_recruitment_flow_through_real_ui(
    fresh_db, auth, qt_app, monkeypatch
):
    import app.database.schema as schema
    from app.ui.main_window import MainWindow
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(schema, "is_first_run", lambda: False)
    company_email, company_password = _create_user(
        fresh_db, "ui-recruitment-company", "company"
    )
    candidate_email, candidate_password = _create_user(
        fresh_db, "ui-recruitment-candidate", "candidate"
    )
    expert_email, _ = _create_user(fresh_db, "ui-recruitment-expert", "expert")
    company_id = fresh_db.fetchone(
        "SELECT id FROM users WHERE email = ?", (company_email,)
    )["id"]
    expert_id = fresh_db.fetchone(
        "SELECT id FROM users WHERE email = ?", (expert_email,)
    )["id"]
    fresh_db.execute(
        """
        INSERT INTO company_expert_contracts
            (company_id, expert_id, contract_code, status)
        VALUES (?, ?, 'UI-RECRUITMENT-EXPERT-001', 'active')
        """,
        (company_id, expert_id),
    )

    company_login = auth.login(company_email, company_password)
    assert company_login.success
    window = MainWindow()
    window._show_dashboard(company_login.user)
    _button(window._dashboard, "Tuyển dụng & đánh giá").click()
    company_screen = window._company_recruitment

    company_screen._position_title.setText("Python Engineer")
    company_screen._position_location.setText("Remote")
    company_screen._position_description.setPlainText("Build desktop software")
    company_screen._position_requirements.setPlainText("Python")
    company_screen._position_status.setCurrentIndex(
        company_screen._position_status.findData("published")
    )
    company_screen._position_save.click()
    assert company_screen._positions_table.rowCount() == 1
    position_id = company_screen._positions[0].id
    assert fresh_db.fetchone(
        "SELECT status FROM job_postings WHERE id = ?", (position_id,)
    )["status"] == "published"

    company_screen._assessment_title.setText("Python Fundamentals")
    company_screen._question_prompt.setText("Which type is immutable?")
    company_screen._question_options[0].setText("list")
    company_screen._question_options[1].setText("tuple")
    company_screen._correct_option.setCurrentIndex(1)
    company_screen._question_add.click()
    assert company_screen._assessment_create.isEnabled()
    company_screen._assessment_create.click()
    assert company_screen._assessments_table.rowCount() == 1
    exam_id = company_screen._assessments[0].id

    company_screen._invite_position.setCurrentIndex(
        company_screen._invite_position.findData(position_id)
    )
    company_screen._invite_assessment.setCurrentIndex(
        company_screen._invite_assessment.findData(exam_id)
    )
    candidate_id = fresh_db.fetchone(
        "SELECT id FROM users WHERE email = ?", (candidate_email,)
    )["id"]
    company_screen._invite_candidate.setCurrentIndex(
        company_screen._invite_candidate.findData(candidate_id)
    )
    company_screen._send_invitation.click()
    assert fresh_db.fetchone(
        "SELECT id FROM recruitment_invitations WHERE candidate_id = ?",
        (candidate_id,),
    )

    auth.logout()
    candidate_login = auth.login(candidate_email, candidate_password)
    assert candidate_login.success
    window._show_dashboard(candidate_login.user)
    _button(window._dashboard, "Lời mời làm bài").click()
    candidate_screen = window._candidate_assessments
    assert candidate_screen._invitations_table.rowCount() == 1
    candidate_screen._invitations_table.selectRow(0)
    candidate_screen._start_exam_button.click()
    question_id = candidate_screen._exam.questions[0].id
    correct_option_id = candidate_screen._exam.questions[0].options[1].id
    candidate_screen._option_buttons[correct_option_id].click()
    candidate_screen._save_answer_button.click()
    assert fresh_db.fetchone(
        "SELECT selected_option_id FROM exam_answers WHERE question_id = ?",
        (question_id,),
    )["selected_option_id"] == correct_option_id
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    candidate_screen._submit_exam_button.click()
    assert not candidate_screen._submit_exam_button.isEnabled()
    assert fresh_db.fetchone(
        "SELECT status FROM recruitment_submissions"
    )["status"] == "graded"
    candidate_screen._submit_exam()
    assert fresh_db.fetchone(
        "SELECT COUNT(*) AS count FROM recruitment_submissions"
    )["count"] == 1

    auth.logout()
    company_login = auth.login(company_email, company_password)
    assert company_login.success
    window._show_dashboard(company_login.user)
    _button(window._dashboard, "Tuyển dụng & đánh giá").click()
    company_screen = window._company_recruitment
    assert company_screen._results_table.rowCount() == 1
    company_screen._results_table.selectRow(0)
    assert company_screen._results_release.isEnabled()
    company_screen._results_release.click()
    assert fresh_db.fetchone(
        "SELECT status FROM recruitment_submissions"
    )["status"] == "released"

    auth.logout()
    candidate_login = auth.login(candidate_email, candidate_password)
    assert candidate_login.success
    window._show_dashboard(candidate_login.user)
    _button(window._dashboard, "Lời mời làm bài").click()
    candidate_screen = window._candidate_assessments
    candidate_screen._invitations_table.selectRow(0)
    assert candidate_screen._view_result_button.isEnabled()
    candidate_screen._view_result_button.click()
    assert candidate_screen._result_score.text() == "Điểm: 10 / 10"
    assert "released" in candidate_screen._result_status.text()
    window.close()
