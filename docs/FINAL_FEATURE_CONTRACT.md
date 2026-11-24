# Final database and persistence contract

This contract describes the SQLite models and `RecruitmentRepository` entry
points for exam answers, coding tests, proctoring, interviews, and certificates.
The repository does not run submitted code, capture media, authenticate users, or
replace authorization checks in the calling Service.

## Schema and migration notes

- **MIG-007** reuses `certificates` and adds `revoked_at`, `revoked_by`, and
  `revocation_reason`. It adds immutable `exam_session_events` rows.
- **MIG-008** adds `question_bank.supported_languages`, and
  `exam_answers.programming_language`, `test_results_json`, and `grading_mode`.
  Existing coding questions default to the supported language `python`;
  existing answers default to manual grading.
- MIG-008 adds `exam_proctoring_sessions` and consent, evidence-reference, and
  processing fields to `exam_session_events`. It adds no duplicate test-case
  or answer tables.
- Existing `question_bank.test_cases`, `exam_answers.answer_text`,
  `exam_answers.answer_code`, `score`, `max_score`, `feedback`, `graded_by`,
  `graded_at`, and `is_graded` remain the source of truth.
- Both migrations are idempotent. `create_all_tables()` applies them to new and
  legacy databases. Tests use temporary SQLite databases only.

## Exam questions, answers, and grading

### Models

- `ExamQuestionModel` and `QuestionOptionModel` are candidate-safe and do not
  expose reference answers, test cases, or correct-option flags.
- `CodingTestCaseModel` represents `{input, expected_output, is_hidden}`.
- `ExamAnswerModel` contains only candidate response fields, including the
  selected programming language; it excludes scores and grader feedback.
- `ExamAnswerGradingModel` is the reviewer DTO. It includes candidate, company,
  paper, grader, score, feedback, grading state, mode, language, and stored
  coding results.
- `CandidateExamResultModel` remains available to candidates only after result
  release.

### Persistence methods

```python
add_question(
    company_id, exam_id, *, title, content, difficulty, points,
    options=(), expert_id=None, question_type="multiple_choice",
    test_cases=(), supported_languages=None, reference_answer=None
) -> Record | None
```

Creates a multiple-choice, essay, or coding question on an unpublished paper.
The author must be an expert with an active company contract.
`question_type="coding"` requires test cases and accepts a non-empty language
list (defaults to `("python",)`). Cases and languages are stored as JSON in the
existing question row. The method records metadata only and never executes code.

```python
list_coding_test_cases(expert_id, question_id) -> list[Record] | None
```

Returns all test cases only to the question's author; `None` means the question
is missing or the requester is not its author.

```python
save_candidate_written_answer(
    session_id, candidate_id, question_id, answer, *,
    programming_language=None
) -> Record | None
```

Saves an essay to `answer_text`, or source code to `answer_code`, only for the
candidate's in-progress exam and a question on that paper. Coding language must
be declared by the question; if omitted, the first declared language is used.
The method returns `None` for a mismatched session/question or unsupported
language. Candidate answer updates are blocked after exam completion.

```python
submit_exam_for_grading(session_id, candidate_id) -> Record | None
```

Completes a recruitment exam once. Multiple-choice answers are scored
automatically; essay and coding answers enter `grading` with `is_graded=False`.
Missing responses are persisted as blank answers so every paper question has a
grade row. Returns the submission with `status`, `score`, and `max_score`;
`score` is `None` while manual grades are pending. Returns `None` if the
candidate/session is not active and accepted.

```python
list_exam_answers_for_grading(
    company_id, session_id, *, requester_id=None
) -> list[ExamAnswerGradingModel]
```

Returns the answers for the owning company. The requester may be that company,
an admin, or an expert with an active contract with it. Unauthorized or
out-of-scope requests return an empty list.

```python
grade_exam_answer(
    company_id, grader_id, session_id, question_id, *,
    score=None, feedback=None, grading_mode="manual",
    coding_test_results=None, revision_reason=None
) -> ExamAnswerGradingModel | None
```

Grades essay/coding answers in a completed, unreleased submission. The grader
must be the owning company, an admin, or its contracted expert. Manual scores
must be between zero and the answer's `max_score`. Automatic mode is coding
only: the caller supplies one `{passed: bool, actual_output?: str, error?: str}`
result per stored test case. The repository calculates a proportional score
and persists the results; execution belongs in an external, isolated runner.
Returns `None` for unauthorized, missing, out-of-scope, or already released
answers. Regrades are recorded in `exam_grade_revisions`. When all answers are
graded, the submission advances from `grading` to `graded` and the session total
is saved.

## Exam proctoring

### Model and states

- `ExamProctoringSessionModel` records the candidate's exam session, explicit
  evidence consent, start/end timestamps, status, and reviewer.
- `ExamSessionEventModel` records type, violation flag, timestamp, details,
  optional evidence reference, consent snapshot, and processing state.
- Session states: `active`, `completed`, `flagged`, `reviewed`.
- Event processing states: `pending` → `reviewed`, `dismissed`, or `escalated`.
  Processed event sources/evidence are immutable and cannot be reopened.

### Persistence methods

- `start_exam_proctoring_session(session_id, candidate_id, *,
  consent_for_evidence=False) -> ExamProctoringSessionModel | None`: starts (or
  returns the existing) monitor for that candidate's in-progress exam.
- `get_exam_proctoring_session(session_id, candidate_id)`: candidate-scoped
  lookup.
- `get_company_exam_proctoring_session(company_id, session_id, *,
  requester_id=None)`: company-scoped lookup for the owning company, admin, or
  contracted expert.
- `record_exam_session_event(session_id, candidate_id, event_type, *,
  is_violation=False, details=None, occurred_at=None, evidence_uri=None)`:
  appends an event only while the matching monitor is active. `evidence_uri`
  must be a reference, not media bytes or a `data:` URL, and is rejected unless
  the candidate explicitly consented when the monitor started. Event `details`
  are metadata only; do not put image/video payloads there.
- `finish_exam_proctoring_session(session_id, candidate_id)`: closes an active
  monitor; pending violations leave the session `flagged`.
- `list_exam_session_events(session_id, candidate_id, *,
  violations_only=False)`: candidate-scoped event history.
- `list_company_exam_session_events(company_id, session_id, *,
  requester_id=None, violations_only=False, processing_status=None)`: review
  queue scoped to the owning company, admin, or contracted expert.
- `review_exam_session_event(company_id, reviewer_id, event_id, *,
  processing_status, notes=None)`: records an authorized reviewer decision.
  Once every event is processed, a finished monitor advances to `reviewed`.

No camera/video/audio capture or storage is provided.

## Interviews

### Models and states

- `InterviewModel` contains candidate/company IDs, schedule, status, duration,
  meeting URL, and description.
- `InterviewParticipantModel` records contracted expert participants and
  their roles; `InterviewEvaluationModel` contains the scores, recommendation,
  and feedback.
- Status starts as `scheduled`; allowed repository transitions are
  `scheduled` → `in_progress`, `completed`, `cancelled`, or `no_show`, then
  `in_progress` → `completed`, `cancelled`, or `no_show`.

### Persistence methods

- `schedule_interview(company_id, candidate_id, *, title, scheduled_at,
  duration_min=60, description=None, meeting_url=None, interviewer_ids=())`:
  creates the interview and its contracted expert participants. Invalid role or
  participant eligibility returns `None`; invalid time/title/duration raises
  `sqlite3.IntegrityError`.
- `list_company_interviews(company_id)` and
  `list_candidate_interviews(candidate_id)` return scoped interview models.
- `list_interview_participants(company_id, interview_id)` returns participants
  only for the owning company.
- `set_interview_status(company_id, interview_id, status)` enforces the
  transitions above; returns `None` for an invalid transition or wrong owner.
- `save_interview_evaluation(interview_id, expert_id, *, technical_score,
  communication_score, problem_solving_score, overall_rating, feedback=None,
  recommendation=None)` upserts an evaluation for an assigned interviewer on
  an `in_progress` or `completed` interview. Scores are 1–5.
- `list_interview_evaluations(company_id, interview_id)` returns evaluation
  results only to the owning company.

No video-call service is created.

## Certificates

- `CertificateModel` maps the existing `certificates` table and revocation
  metadata. Status values remain `active`, `expired`, and `revoked`.
- `issue_certificate(user_id, skill_id, *, score=None, cert_code=None,
  expires_at=None)` creates a certificate for a candidate. The code is generated
  if omitted. The existing unique `(user_id, skill_id)` rule prevents duplicate
  issuance, including re-issuing a revoked certificate.
- `verify_certificate(cert_code)` returns an active, unexpired certificate or
  `None` when missing, expired, or revoked.
- `list_user_certificates(user_id)` returns the candidate's history.
- `revoke_certificate(certificate_id, revoked_by, reason)` allows an admin to
  revoke an active certificate and records actor, time, and non-empty reason.
  Returns `None` if unauthorized, missing, or already
  revoked. Revoked certificates cannot be reactivated.

Certificate issuance authorization based on the authenticated workflow remains
the calling Service's responsibility; this task intentionally does not change
Authentication or Services.
