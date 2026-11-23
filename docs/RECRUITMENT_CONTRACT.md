# Recruitment and exam data contract

This contract describes the database records shared by the Company, Candidate,
and exam workflows. It reuses the existing exam/question tables and does not
change Authentication, UI, Controllers, or Services.

## Tables and ownership

| Table | Use | Important relationship/data |
|---|---|---|
| `job_postings` *(MIG-006)* | Company vacancy | `company_id -> users.id`; title, description, requirements, location, status |
| `exam_papers` *(existing)* | Reusable exam/test | Published paper selected for an invitation |
| `question_bank` *(existing)* | Question source | `expert_id` is the author; `reference_answer` and `test_cases` are confidential grading data |
| `question_options` *(existing)* | Multiple-choice options | Existing `is_correct` is confidential grading data |
| `exam_paper_questions` *(existing)* | Questions in a paper | Reuses the existing question and score/order relationship |
| `recruitment_invitations` *(MIG-006)* | Candidate invitation | Company, job, candidate, paper, response, and linked exam-session context |
| `exam_sessions` *(existing)* | Candidate's attempt | Candidate, company, paper, timing, lifecycle, and score |
| `exam_answers` *(existing)* | Answers in an attempt | One answer per session/question; option selection is checked against its question |
| `recruitment_submissions` *(MIG-006)* | Submission and result-release lifecycle | One submission per invitation/session; status and timestamps |

`job_postings.company_id` is the authoritative owner. Composite foreign keys
require an invitation's company to own its job and require its exam session to
match the invitation's candidate, company, and paper. A new invitation starts
with no session; accepting it links a scheduled session. Each invitation can
have at most one session and one submission. A new invitation is a new attempt;
Services should prevent duplicate active invitations when that is not intended.

Foreign keys provide data consistency, not request authorization. Services must
derive `company_id` and `candidate_id` from the authenticated user, not trust
client-supplied owner IDs:

- Company operations must scope job and invitation reads/writes by the current
  Company's `users.id`.
- Candidate operations must scope invitation, session, and submission reads
  and writes by the current Candidate's `users.id` and an invitation addressed
  to that Candidate.
- Only published jobs and exam papers should be used to create an invitation.

MIG-006 also checks that a job owner has the `company` role, an invited user has
the `candidate` role, and the job and paper are published when an invitation is
created. Job ownership and invitation/submission identity fields are immutable
after creation (the invitation's exam session can be linked once on acceptance).

`question_bank.expert_id` remains the author and must not be filled with the
Company's id. The persistence layer accepts a question only with an explicit
Expert id who has an `active` contract with that Company. The current
`ExamService.add_question()` call does not provide that id; do not infer an
author by choosing an arbitrary contracted Expert.

## Lifecycle and status values

| Record | Statuses | Allowed progression |
|---|---|---|
| Job posting | `draft`, `published`, `closed` | Company workflow controls publication/closure |
| Invitation | `pending`, `accepted`, `declined`, `cancelled`, `expired` | `pending -> accepted / declined / cancelled / expired`; `accepted -> cancelled / expired` |
| Exam session *(existing)* | `scheduled`, `in_progress`, `completed`, `cancelled` | Existing exam lifecycle; an accepted invitation must link a `scheduled` session |
| Submission | `submitted`, `grading`, `graded`, `released` | `submitted -> grading -> graded -> released` |

The database rejects invalid invitation/submission transitions, requires
`responded_at` when an invitation leaves `pending`, and requires a completed
session before a submission can be inserted. The submission's unique
invitation/session constraints prevent duplicate submission. Save or update
answers only while the linked recruitment session is `in_progress`.

Grading should set each answer's score/grading fields and the session's
`total_score`, then move the submission through `grading` to `graded`. The
database rejects `graded` or `released` when the total score is missing, the
maximum score is not positive, or any answer remains ungraded. Set
`released_at` only when moving to `released`.

## Candidate-safe data

Never return raw `question_bank` or `question_options` rows to a Candidate.
Candidate question queries must explicitly select only the paper/question
identity, prompt, type, difficulty, points, and order. Omit
`question_bank.reference_answer`, `question_bank.test_cases`, and
`question_options.is_correct`. `ExamQuestionModel` and `QuestionOptionModel`
are the candidate-safe DTOs; answer-key and grading DTOs remain out of this
model module's Candidate-facing shapes.

Candidate answers should include only the selected option and/or submitted
text/code. `ExamAnswerModel` excludes score and grader feedback. A Candidate
result query must join `recruitment_submissions` and expose a score only when
`status = 'released'`; `CandidateExamResultModel.from_row` rejects any other
status and requires grading/release timestamps and a score.

Suggested result query shape:

```sql
SELECT es.id AS exam_session_id,
       es.total_score,
       es.max_score,
       rs.status AS submission_status,
       rs.graded_at,
       rs.released_at
FROM exam_sessions AS es
JOIN recruitment_submissions AS rs ON rs.exam_session_id = es.id
WHERE rs.candidate_id = :authenticated_candidate_id
  AND rs.status = 'released';
```

## Model imports

Import the shared DTOs from `server.models`:

- `JobPostingModel`, `ExamPaperModel`
- `ExamQuestionModel`, `QuestionOptionModel`
- `RecruitmentInvitationModel`, `ExamSessionModel`, `ExamAnswerModel`
- `RecruitmentSubmissionModel`, `CandidateExamResultModel`
- `RecruitmentRepository` implements both Service persistence protocols.

Models are immutable row DTOs; they do not execute SQL or replace authorization
in Services. Use the existing SQLite connection and schema migration path.

To reconcile question authorship, the proposed `ExamModel.add_question`
signature is:

```python
def add_question(
    self,
    company_id: int,
    exam_id: int,
    *,
    expert_id: int,
    title: str,
    content: str,
    difficulty: str,
    points: float,
    options: Sequence[ExamOption],
) -> Mapping[str, object] | None: ...
```

The Service/UI must choose an actual active contracted Expert (or support
selecting an existing Expert-authored question) before calling this method.

## Migration compatibility

MIG-006 adds `job_postings`, `recruitment_invitations`, and
`recruitment_submissions`, plus indexes and triggers. It does not rebuild or
rewrite existing user, question, paper, session, or answer data. The migration
is idempotent and runs after MIG-005 for both new databases and existing
databases using the established migration chain.
