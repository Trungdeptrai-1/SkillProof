"""Mock-backed tests for workflows awaiting recruitment and exam Models."""

import sqlite3
from unittest.mock import Mock

import pytest

from server.controllers.exam_controller import ExamController
from server.controllers.recruitment_controller import RecruitmentController
from server.models.user_model import UserModel
from server.services.exam_service import (
    ExamModel,
    ExamOption,
    ExamResult,
    ExamService,
)
from server.services.recruitment_service import (
    RecruitmentModel,
    RecruitmentResult,
    RecruitmentService,
)
from app.services.auth_service import SessionManager


@pytest.fixture(autouse=True)
def reset_session():
    SessionManager._instance = None
    yield
    SessionManager._instance = None


def _session(role: str, user_id: int = 41) -> None:
    SessionManager.instance().start_session(
        UserModel(
            id=user_id,
            username=f"{role}-{user_id}",
            email=f"{role}-{user_id}@test.local",
            full_name="Test Account",
            role=role,
            avatar_path=None,
            is_active=True,
            created_at="2026-01-01",
            updated_at="2026-01-01",
        )
    )


def _recruitment_controller():
    model = Mock(spec=RecruitmentModel)
    service = RecruitmentService(model)
    return model, RecruitmentController(service)


def _exam_controller():
    model = Mock(spec=ExamModel)
    recruitment_model = Mock(spec=RecruitmentModel)
    service = ExamService(model, recruitment_model)
    return model, recruitment_model, ExamController(service)


def _active_session():
    return {
        "status": "in_progress",
        "started_at": "2999-01-01T00:00:00",
        "duration_min": 60,
    }


def test_company_can_create_update_get_and_list_its_positions():
    _session("company", 12)
    model, controller = _recruitment_controller()
    position = {
        "id": 8,
        "company_id": 12,
        "title": "Engineer",
        "status": "draft",
    }
    published_position = {
        "id": 8,
        "company_id": 12,
        "title": "Senior Engineer",
        "status": "published",
    }
    model.create_job_posting.return_value = position
    model.update_job_posting.return_value = published_position
    model.get_job_posting.return_value = position
    model.list_job_postings.return_value = [position]

    created = controller.create_position(
        "  Engineer  ", "  Product team  ", "  Python  ", "  Remote  "
    )
    updated = controller.update_position(8, "Senior Engineer", status="published")
    fetched = controller.get_position(8)
    listed = controller.list_positions()

    assert created.success and created.position == position
    model.create_job_posting.assert_called_once_with(
        12,
        title="Engineer",
        description="Product team",
        requirements="Python",
        location="Remote",
        status="draft",
    )
    assert updated.success and fetched.success and listed.positions == [position]
    model.update_job_posting.assert_called_once_with(
        12,
        8,
        title="Senior Engineer",
        description="",
        requirements="",
        location="",
        status="published",
    )
    assert model.get_job_posting.call_args_list == [
        ((12, 8), {}),
        ((12, 8), {}),
    ]
    model.list_job_postings.assert_called_once_with(12)


def test_company_position_access_is_scoped_and_input_checked():
    _session("company", 12)
    model, controller = _recruitment_controller()
    model.get_job_posting.return_value = None
    model.update_job_posting.return_value = None

    assert controller.get_position(999).status == RecruitmentResult.POSITION_NOT_FOUND
    assert (
        controller.update_position(999, "New title").status
        == RecruitmentResult.POSITION_NOT_FOUND
    )
    assert controller.create_position("  ").status == RecruitmentResult.EMPTY_TITLE
    assert (
        controller.create_position("Engineer", status="invalid").status
        == RecruitmentResult.INVALID_STATUS
    )
    assert controller.get_position(True).status == RecruitmentResult.INVALID_INPUT
    assert model.get_job_posting.call_args_list == [
        ((12, 999), {}),
        ((12, 999), {}),
    ]
    model.update_job_posting.assert_not_called()


def test_recruitment_requires_company_role_and_handles_sqlite_errors():
    model, controller = _recruitment_controller()
    assert controller.list_positions().status == RecruitmentResult.NOT_LOGGED_IN
    _session("candidate")
    assert controller.create_position("Engineer").status == RecruitmentResult.WRONG_ROLE
    model.create_job_posting.assert_not_called()

    _session("company")
    model.create_job_posting.side_effect = sqlite3.OperationalError("locked")
    assert controller.create_position("Engineer").status == RecruitmentResult.DB_ERROR


def test_recruitment_controller_rejects_bad_shapes_without_service_call():
    service = Mock(spec=RecruitmentService)
    controller = RecruitmentController(service)

    assert controller.create_position(None).status == RecruitmentResult.INVALID_INPUT
    assert controller.update_position(True, "Engineer").status == RecruitmentResult.INVALID_INPUT
    service.create_position.assert_not_called()
    service.update_position.assert_not_called()


def test_company_can_create_exam_and_add_multiple_choice_question():
    _session("company", 12)
    model, _, controller = _exam_controller()
    exam = {
        "id": 5,
        "created_by": 12,
        "title": "Python",
        "is_published": False,
    }
    published_exam = {**exam, "is_published": True}
    question = {"id": 21, "title": "Which is immutable?"}
    model.create_exam.return_value = exam
    model.get_exam_for_company.return_value = exam
    model.add_question.return_value = question
    model.publish_exam.return_value = published_exam

    created = controller.create_exam("  Python  ", "  Basics  ", 45, 50)
    added = controller.add_question(
        5,
        "Immutable type",
        "Choose the immutable type.",
        [
            ExamOption("List", False),
            ExamOption("Tuple", True),
        ],
        5,
        "easy",
    )

    assert created.success and created.exam == exam
    model.create_exam.assert_called_once_with(
        12,
        title="Python",
        description="Basics",
        duration_min=45,
        total_points=50.0,
    )
    assert added.success and added.question == question
    model.add_question.assert_called_once_with(
        12,
        5,
        title="Immutable type",
        content="Choose the immutable type.",
        difficulty="easy",
        points=5.0,
        options=(ExamOption("List", False), ExamOption("Tuple", True)),
    )
    published = controller.publish_exam(5)
    assert published.success and published.exam == published_exam
    model.publish_exam.assert_called_once_with(12, 5)


@pytest.mark.parametrize(
    "options",
    [
        [ExamOption("Only one", True)],
        [ExamOption("A", False), ExamOption("B", False)],
        [ExamOption("A", True), ExamOption("B", True)],
        [ExamOption("", True), ExamOption("B", False)],
    ],
)
def test_question_requires_two_options_and_exactly_one_answer_key(options):
    _session("company")
    model, _, controller = _exam_controller()
    model.get_exam_for_company.return_value = {"id": 4}

    result = controller.add_question(4, "Question", "Prompt", options)

    assert result.status == ExamResult.INVALID_OPTIONS
    model.add_question.assert_not_called()


def test_company_exam_validation_ownership_and_candidate_role():
    _session("company", 12)
    model, recruitment_model, controller = _exam_controller()
    recruitment_model.get_job_posting.return_value = {
        "id": 7,
        "status": "published",
    }

    assert controller.create_exam("Test", duration_min=0).status == ExamResult.INVALID_DURATION
    assert controller.create_exam("Test", total_points=float("inf")).status == ExamResult.INVALID_POINTS
    model.create_exam.assert_not_called()

    model.get_exam_for_company.return_value = None
    assert controller.add_question(
        9, "Q", "Prompt", [ExamOption("A", True), ExamOption("B", False)]
    ).status == ExamResult.EXAM_NOT_FOUND
    assert (
        controller.invite_candidate(7, 9, 15).status
        == ExamResult.EXAM_NOT_FOUND
    )
    model.add_question.assert_not_called()
    model.get_user_role.assert_not_called()

    model.get_exam_for_company.return_value = {"id": 9, "is_published": True}
    model.get_user_role.return_value = "student"
    assert (
        controller.invite_candidate(7, 9, 15).status
        == ExamResult.INVALID_CANDIDATE
    )
    model.invite_candidate.assert_not_called()


def test_company_can_invite_candidate_view_submissions_and_release_results():
    _session("company", 12)
    model, recruitment_model, controller = _exam_controller()
    exam = {"id": 9, "created_by": 12, "is_published": True}
    job = {"id": 7, "company_id": 12, "status": "published"}
    invitation = {"id": 23, "candidate_id": 15, "status": "pending"}
    submissions = [{"candidate_id": 15, "score": 8, "max_score": 10}]
    recruitment_model.get_job_posting.return_value = job
    model.get_exam_for_company.return_value = exam
    model.get_user_role.return_value = "candidate"
    model.invite_candidate.return_value = invitation
    model.list_company_submissions.return_value = submissions
    model.release_results.return_value = {"id": 9, "status": "released"}

    invited = controller.invite_candidate(
        7, 9, 15, "2999-01-01T10:00:00"
    )
    viewed = controller.list_submissions(9)
    released = controller.release_results(9)

    assert invited.success and invited.invitation == invitation
    model.invite_candidate.assert_called_once_with(
        12, 7, 9, 15, "2999-01-01T10:00:00"
    )
    assert viewed.success and viewed.submissions == submissions
    assert released.success
    model.list_company_submissions.assert_called_once_with(12, 9)
    model.release_results.assert_called_once_with(12, 9)
    recruitment_model.get_job_posting.assert_called_once_with(12, 7)


def test_candidate_can_list_only_own_invitations_and_start_exam():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    invitation = {"id": 23, "candidate_id": 15, "status": "pending"}
    pending = {
        "id": 23,
        "candidate_id": 15,
        "status": "pending",
        "expires_at": "2999-01-01T10:00:00",
    }
    accepted = {
        "id": 23,
        "candidate_id": 15,
        "status": "accepted",
        "exam_session_id": 23,
    }
    started = _active_session()
    model.list_candidate_invitations.return_value = [invitation]
    model.get_candidate_invitation.return_value = pending
    model.accept_candidate_invitation.return_value = accepted
    model.get_candidate_session.return_value = {"status": "scheduled"}
    model.start_session_once.return_value = (True, started)

    invitations = controller.list_invitations()
    acceptance = controller.accept_invitation(23)
    result = controller.start_exam(23)

    assert invitations.success and invitations.invitations == [invitation]
    assert acceptance.success and acceptance.invitation == accepted
    assert result.success and result.invitation == started
    model.list_candidate_invitations.assert_called_once_with(15)
    model.get_candidate_session.assert_called_once_with(23, 15)
    model.start_session_once.assert_called_once_with(23, 15)
    model.get_candidate_invitation.assert_called_once_with(23, 15)
    model.accept_candidate_invitation.assert_called_once_with(23, 15)


def test_candidate_cannot_accept_expired_invitation():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_invitation.return_value = {
        "id": 23,
        "status": "pending",
        "expires_at": "2000-01-01T00:00:00",
    }

    result = controller.accept_invitation(23)

    assert result.status == ExamResult.INVITATION_EXPIRED
    model.expire_candidate_invitation.assert_called_once_with(23, 15)
    model.accept_candidate_invitation.assert_not_called()


def test_candidate_invitation_payload_does_not_expose_unreleased_results():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.list_candidate_invitations.return_value = [
        {
            "id": 23,
            "candidate_id": 15,
            "status": "accepted",
            "score": 8,
            "results_released": False,
            "answers": [{"question_id": 31, "selected_option_id": 2}],
        }
    ]

    result = controller.list_invitations()

    assert result.success
    invitation = result.invitations[0]
    assert invitation["id"] == 23
    assert "score" not in invitation
    assert "results_released" not in invitation
    assert "answers" not in invitation


def test_candidate_cannot_access_another_users_exam_session():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = None

    result = controller.start_exam(23)

    assert result.status == ExamResult.INVITATION_NOT_FOUND
    model.get_candidate_session.assert_called_once_with(23, 15)
    model.start_session_once.assert_not_called()


def test_candidate_question_payload_redacts_answer_keys():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = _active_session()
    model.list_candidate_questions.return_value = [
        {
            "id": 31,
            "title": "Question",
            "correct_option_id": 2,
            "reference_answer": "secret",
            "options": [
                {"id": 1, "content": "Wrong", "is_correct": False},
                {"id": 2, "content": "Right", "is_correct": True},
            ],
        }
    ]

    result = controller.list_questions(23)

    assert result.success
    question = result.questions[0]
    assert question["id"] == 31
    assert "correct_option_id" not in question
    assert "reference_answer" not in question
    assert all("is_correct" not in option for option in question["options"])


def test_candidate_question_payload_includes_only_its_saved_option():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = _active_session()
    model.list_candidate_questions.return_value = [
        {
            "id": 31,
            "title": "Question",
            "selected_option_id": 2,
            "options": [
                {"id": 1, "content": "Wrong", "is_correct": False},
                {"id": 2, "content": "Right", "is_correct": True},
            ],
        }
    ]

    result = controller.list_questions(23)

    assert result.success
    question = result.questions[0]
    assert question["selected_option_id"] == 2
    assert all("is_correct" not in option for option in question["options"])


def test_candidate_cannot_change_answers_after_submission():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = {"status": "completed"}

    result = controller.save_answer(23, 31, 2)

    assert result.status == ExamResult.INVALID_SESSION_STATE
    model.save_candidate_answer.assert_not_called()


def test_candidate_can_save_answer_for_an_in_progress_session():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = _active_session()
    answer = {"question_id": 31, "selected_option_id": 2}
    model.save_candidate_answer.return_value = answer

    result = controller.save_answer(23, 31, 2)

    assert result.success and result.answer == answer
    model.save_candidate_answer.assert_called_once_with(23, 15, 31, 2)


def test_expired_exam_rejects_answer_changes_but_grades_saved_answers():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = {
        "status": "in_progress",
        "started_at": "2000-01-01T00:00:00",
        "duration_min": 60,
    }

    expired_answer = controller.save_answer(23, 31, 2)

    assert expired_answer.status == ExamResult.EXAM_EXPIRED
    model.save_candidate_answer.assert_not_called()

    model.get_grading_questions.return_value = [
        {
            "id": 31,
            "points": 3,
            "options": [
                {"id": 1, "is_correct": False},
                {"id": 2, "is_correct": True},
            ],
        }
    ]
    model.get_candidate_answers.return_value = []
    model.complete_session_once.return_value = (
        True,
        {"id": 23, "status": "completed", "score": 0, "max_score": 3},
    )

    submitted = controller.submit_exam(23)

    assert submitted.success
    assert submitted.score is None
    assert submitted.max_score is None
    assert submitted.result == {"status": "submitted"}
    model.complete_session_once.assert_called_once()


def test_submission_automatically_grades_once_and_is_idempotent():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = _active_session()
    model.get_grading_questions.return_value = [
        {
            "id": 31,
            "points": 5,
            "options": [
                {"id": 1, "is_correct": False},
                {"id": 2, "is_correct": True},
            ],
        },
        {
            "id": 32,
            "points": 3,
            "options": [
                {"id": 3, "is_correct": True},
                {"id": 4, "is_correct": False},
            ],
        },
    ]
    model.get_candidate_answers.return_value = [
        {"question_id": 31, "selected_option_id": 2},
        {"question_id": 32, "selected_option_id": 4},
    ]
    model.complete_session_once.return_value = (
        True,
        {"id": 23, "status": "completed", "score": 5, "max_score": 8},
    )

    submitted = controller.submit_exam(23)

    assert submitted.success
    assert submitted.score is None
    assert submitted.max_score is None
    assert submitted.result == {"status": "submitted"}
    model.complete_session_once.assert_called_once_with(
        23,
        15,
        score=5.0,
        max_score=8.0,
        question_scores=[
            {"question_id": 31, "score": 5.0, "max_score": 5.0},
            {"question_id": 32, "score": 0.0, "max_score": 3.0},
        ],
    )

    model.get_candidate_session.return_value = {"status": "completed"}
    duplicate = controller.submit_exam(23)

    assert duplicate.status == ExamResult.ALREADY_SUBMITTED
    model.complete_session_once.assert_called_once()


def test_concurrent_duplicate_submission_is_not_graded_twice():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = _active_session()
    model.get_grading_questions.return_value = [
        {
            "id": 31,
            "points": 5,
            "options": [
                {"id": 1, "is_correct": False},
                {"id": 2, "is_correct": True},
            ],
        }
    ]
    model.get_candidate_answers.return_value = [
        {"question_id": 31, "selected_option_id": 2}
    ]
    model.complete_session_once.return_value = (False, None)

    result = controller.submit_exam(23)

    assert result.status == ExamResult.ALREADY_SUBMITTED
    model.complete_session_once.assert_called_once()


def test_invalid_grading_data_does_not_complete_session():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = _active_session()
    model.get_grading_questions.return_value = [
        {
            "id": 31,
            "points": 5,
            "options": [
                {"id": 1, "is_correct": True},
                {"id": 2, "is_correct": True},
            ],
        }
    ]
    model.get_candidate_answers.return_value = []

    result = controller.submit_exam(23)

    assert result.status == ExamResult.INVALID_EXAM_CONFIGURATION
    model.complete_session_once.assert_not_called()


def test_candidate_result_is_hidden_until_company_releases_it():
    _session("candidate", 15)
    model, _, controller = _exam_controller()
    model.get_candidate_session.return_value = {"status": "completed"}
    model.get_candidate_submission.return_value = {"status": "graded"}

    hidden = controller.get_result(23)
    assert hidden.status == ExamResult.RESULT_NOT_RELEASED
    model.get_candidate_result.assert_not_called()

    model.get_candidate_submission.return_value = {"status": "released"}
    model.get_candidate_result.return_value = {
        "score": 8,
        "max_score": 10,
    }
    released = controller.get_result(23)
    assert released.success and released.result["score"] == 8


@pytest.mark.parametrize("role", ["student", "expert", "admin", "company"])
def test_wrong_role_cannot_use_candidate_exam_operations(role):
    _session(role)
    model, _, controller = _exam_controller()

    assert controller.list_invitations().status == ExamResult.WRONG_ROLE
    assert controller.start_exam(1).status == ExamResult.WRONG_ROLE
    assert controller.list_questions(1).status == ExamResult.WRONG_ROLE
    assert controller.save_answer(1, 1, 1).status == ExamResult.WRONG_ROLE
    assert controller.submit_exam(1).status == ExamResult.WRONG_ROLE
    assert controller.get_result(1).status == ExamResult.WRONG_ROLE
    model.assert_not_called()


def test_wrong_role_cannot_use_company_exam_operations():
    _session("candidate")
    model, _, controller = _exam_controller()

    assert controller.create_exam("Test").status == ExamResult.WRONG_ROLE
    assert controller.list_exams().status == ExamResult.WRONG_ROLE
    assert controller.publish_exam(1).status == ExamResult.WRONG_ROLE
    assert controller.invite_candidate(1, 2, 3).status == ExamResult.WRONG_ROLE
    assert controller.list_submissions(1).status == ExamResult.WRONG_ROLE
    assert controller.release_results(1).status == ExamResult.WRONG_ROLE
    model.assert_not_called()


def test_exam_service_surfaces_sqlite_errors():
    _session("company")
    model, _, controller = _exam_controller()
    model.create_exam.side_effect = sqlite3.OperationalError("locked")

    assert controller.create_exam("Test").status == ExamResult.DB_ERROR

    _session("candidate")
    model.get_candidate_session.side_effect = sqlite3.OperationalError("locked")
    assert controller.submit_exam(1).status == ExamResult.DB_ERROR


def test_exam_controller_rejects_bad_request_shapes_without_service_call():
    service = Mock(spec=ExamService)
    controller = ExamController(service)

    assert controller.get_exam(True).status == ExamResult.INVALID_INPUT
    assert controller.invite_candidate(1, 2, True).status == ExamResult.INVALID_INPUT
    assert controller.save_answer(1, 2, True).status == ExamResult.INVALID_INPUT
    service.get_exam.assert_not_called()
    service.invite_candidate.assert_not_called()
    service.save_answer.assert_not_called()
