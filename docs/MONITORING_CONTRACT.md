# Monitoring, coding-test, and interview persistence contract

This contract describes the SQLite/Repository boundary for camera monitoring,
recording, coding-test results, and interviews. It reuses MIG-007–009 tables
and adds only MIG-010 columns and indexes to `exam_proctoring_sessions`.
Video bytes remain in external storage; SQLite stores only a path or URI.

## Schema and data states

MIG-010 is safe to rerun and preserves existing proctoring sessions and events.
It adds:

- `camera_status` and `camera_status_changed_at`.
- `recording_consent` and `recording_consent_at`. These are distinct from
  `consent_for_evidence`, which authorizes event evidence references only.
- `video_path`, `video_created_at`, `video_retention_until`,
  `video_deleted_at`, and `video_status`.

The existing unique exam-session relation prevents duplicate proctoring
sessions. A partial unique index prevents one external video reference from
being attached to multiple sessions. Triggers enforce valid camera/video
states, consent before attaching a recording, one-way video state transitions,
and immutable deletion records. Data URLs and non-text media payloads are
rejected.

| Field | Values / meaning |
|---|---|
| Camera | `not_started`, `active`, `disconnected`, `permission_denied`, `off` |
| Video | `not_recorded -> available -> expired -> deleted`; `available -> deleted` is also allowed |
| Event decision | Existing `pending`, `reviewed`, `dismissed`, `escalated`; review is recorded with reviewer, time, and notes |
| Proctoring session | Existing lifecycle; starts `active`, then completes or is flagged/reviewed |

`focus_lost`, `camera_disconnected`, and `timeout` are stored as event types in
`exam_session_events`. `is_violation` identifies violations; the existing
processing fields store the review decision. Camera-status changes made through
the Repository also append an event. Repeating the same status/consent update
is idempotent and does not append another event.

The policy uses the existing `app_settings` table under
`exam_proctoring.policy.v1`; no policy or video table is duplicated.

## DTOs

Import from `server.models`:

- `ExamProctoringSessionModel`: session status, evidence/recording consent,
  camera state, and video lifecycle metadata. It deliberately omits the video
  path.
- `ProctoringVideoModel`: external path and lifecycle data returned by the
  separately authorized video APIs.
- `ExamSessionEventModel`: immutable event details and processing decision.
- `ExamProctoringPolicyModel`: thresholds, camera timeout, and retention days.
- `ExamGradeRevisionModel`: an existing grading revision row.

## Monitoring Repository APIs

All methods are on `RecruitmentRepository`. `None` means the target is missing
or the caller is unauthorized unless a method below specifies an empty list.
Invalid values or forbidden state transitions raise `sqlite3.IntegrityError`.
Services must pass the authenticated user ID; never accept an owner ID directly
from an untrusted request.

| Method | Parameters and behavior | Permission / result |
|---|---|---|
| `start_exam_proctoring_session(session_id, candidate_id, *, consent_for_evidence=False, recording_consent=False)` | Starts/reuses the unique session for an in-progress exam. Consent timestamps are recorded when true. | The candidate owning the active exam; returns `ExamProctoringSessionModel` or `None`. Recording consent is separate from evidence consent. |
| `set_exam_recording_consent(session_id, candidate_id, *, consented)` | Grants or withdraws recording consent and appends a consent event. Repeating the current value is a no-op. Consent cannot change after video metadata is attached. | Owning candidate with an active proctoring session; model or `None`. |
| `update_exam_camera_status(session_id, candidate_id, *, camera_status)` | Records one of the camera states above, timestamp, and a camera event. | Owning candidate with an active proctoring session; model or `None`. |
| `record_exam_session_event(session_id, candidate_id, event_type, *, is_violation=False, details=None, occurred_at=None, evidence_uri=None)` | Stores event data; evidence URI must be external and requires `consent_for_evidence`. Use event types such as `focus_lost` and `timeout`. | Candidate with an active proctoring session; returns `ExamSessionEventModel`. |
| `review_exam_session_event(company_id, reviewer_id, event_id, *, processing_status, notes=None)` | Records a decision (`reviewed`, `dismissed`, or `escalated`), reviewer, time, and notes. | Company owner, admin, or contracted expert; event model or `None`. |
| `list_proctoring_violation_history(session_id, viewer_id, *, processing_status=None)` | Returns violations in event-time order, optionally filtered by decision status. | Candidate for that session, owning company, admin, or active contracted expert; unauthorized callers receive `[]`. |
| `attach_proctoring_video(session_id, actor_id, video_path, *, created_at=None, retention_days=None)` | Stores an external path/URI and retention metadata, not media bytes. Uses policy retention if omitted. Requires prior recording consent. | Owning company or admin; `ProctoringVideoModel` or `None`. Duplicate attachment, embedded media, or absent consent raises `sqlite3.IntegrityError`. |
| `get_proctoring_video_for_session(session_id, viewer_id)` | Returns a permitted video reference. Expired references transition to `expired`; expired/deleted records return no playable path. | Candidate, owning company, admin, or active contracted expert; model or `None`. |
| `list_expired_proctoring_videos(admin_id)` | Returns expired references and paths for an authorized external-storage cleanup worker. Marks elapsed available recordings expired. | Active admin only; non-admin receives `[]`. |
| `record_proctoring_video_deleted(session_id, actor_id)` | Clears the external path and records deletion time/status. Call only after the external object is actually removed. Repeating it is safe. | Owning company or admin; deleted model or `None`. |
| `get_exam_proctoring_policy()` | Reads the validated global policy, or documented defaults when not configured. | Read-only configuration; returns `ExamProctoringPolicyModel`. |
| `save_exam_proctoring_policy(admin_id, policy)` | Persists a policy model or mapping in `app_settings`. Requires positive thresholds/timeouts/retention and termination threshold not below warning threshold. | Active admin; policy model or `None`. |

Default policy: warning threshold `1`, termination threshold `3`, terminate on
threshold `true`, camera-disconnect timeout `60` seconds, and video retention
`30` days. The policy is configuration for the consuming Service; persistence
does not execute camera capture, delete external files, or terminate an exam.
No recording may be started or attached without recording consent. Consent
does not authorize storage of camera images or video blobs in SQLite.

## Coding-test persistence

Coding prompts, supported languages, public/hidden test cases, submitted code,
grading mode, and test results reuse `question_bank` and `exam_answers`.
Automatic grading persists caller-provided results; the Repository never runs
submitted code.

| Method | Parameters and behavior | Permission / result |
|---|---|---|
| `list_public_coding_test_cases(session_id, candidate_id, question_id)` | Returns only public `{input, expected_output}` cases. | Candidate owning an in-progress session; list or `None`. |
| `list_coding_test_cases(expert_id, question_id)` | Returns all cases, including hidden cases, for test-authoring. | Question author; list or `None`. |
| `grade_exam_answer(company_id, grader_id, session_id, question_id, *, score=None, feedback=None, grading_mode="manual", coding_test_results=None, revision_reason=None)` | Persists manual or automatic results. Automatic mode requires one result per case; source code is never executed here. Re-grades append to `exam_grade_revisions`. | Owning company, admin, or active contracted expert; grading model or `None`. |
| `list_exam_grade_revisions(company_id, requester_id, session_id, *, question_id=None)` | Reads saved grade revisions, optionally for one question. | Owning company, admin, or active contracted expert; list of `ExamGradeRevisionModel` (unauthorized callers receive `[]`). |

Revision history records changes after the initial grade; the current grade and
latest test results remain on `exam_answers`.

## Interview persistence already available

No interview schema change is needed. The existing `interviews`,
`interview_participants`, and `interview_evaluations` tables persist scheduling,
meeting URL, participants, lifecycle, scores, recommendations, and feedback:

- `schedule_interview(company_id, candidate_id, *, title, scheduled_at, duration_min=60, description=None, meeting_url=None, interviewer_ids=())`
- `list_company_interviews(company_id)`, `list_candidate_interviews(candidate_id)`,
  `list_expert_interviews(expert_id)`, and
  `list_interview_participants(company_id, interview_id)`
- `set_interview_status(company_id, interview_id, status)` supports
  `in_progress`, `completed`, `cancelled`, and `no_show` from valid existing
  states.
- `save_interview_evaluation(interview_id, expert_id, *, technical_score, communication_score, problem_solving_score, overall_rating, feedback=None, recommendation=None)` accepts 1–5 scores and the existing recommendation values.
- `list_interview_evaluations(company_id, interview_id)` and
  `list_expert_interview_evaluations(expert_id, interview_id)` retrieve saved
  assessments.

Company scheduling is owner-scoped; interviewer IDs must be contracted experts.
Experts can evaluate only interviews in which they are participants. Meeting
URLs are references only; this contract does not add video calling.
