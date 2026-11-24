# SkillProof Demo Guide

This guide covers verified application flows and calls out features that are
not implemented. Use an isolated SQLite database for every demo.

## Prepare an isolated demo database

In PowerShell, select a database under the Windows temporary directory before
starting the app. The normal database path is unchanged when this variable is
not set.

```powershell
$demoDir = Join-Path $env:TEMP "SkillProofDemo"
New-Item -ItemType Directory -Force $demoDir | Out-Null
$env:SKILLPROOF_DB_PATH = Join-Path $demoDir "skillproof.db"
```

Public registration creates Candidate accounts only. To demonstrate Company
and Expert roles, seed those accounts in this disposable database before
launching the application. This one-off setup is not an application feature and
must never be run against the normal user database:

```powershell
$env:SKILLPROOF_DEMO_PASSWORD = Read-Host "Enter a strong temporary demo password"
@'
import os

from app.utils.helpers import hash_password
from server.database.connection import db
from server.database.schema import create_all_tables

create_all_tables()
password_hash = hash_password(os.environ["SKILLPROOF_DEMO_PASSWORD"])
for username, email, full_name, role in (
    ("demo-company", "company-demo@example.test", "Demo Company", "company"),
    ("demo-expert", "expert-demo@example.test", "Demo Expert", "expert"),
):
    db.execute(
        """
        INSERT OR IGNORE INTO users
            (username, email, password, full_name, role, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (username, email, password_hash, full_name, role),
    )
db.close()
'@ | python -
Remove-Item Env:\SKILLPROOF_DEMO_PASSWORD
```

Start the app from the repository root while `SKILLPROOF_DB_PATH` remains set:

```powershell
python main.py
```

The first launch displays First-Run Setup. Create an Admin account there; no
default Admin password exists. Keep the temporary database until the demo is
finished, then remove only the named `SkillProofDemo` directory under `$env:TEMP`.

## Verified flows

### Admin

1. Sign in with the Admin account created by First-Run Setup.
2. The dashboard loads real user, profile, and skill counts from SQLite.
3. Open **Người dùng** to search by username/name/email, filter by role and
   status, and lock or unlock an account. A deleted account is not listed, and
   the last active Admin cannot be locked.
4. Open **Danh mục kỹ năng** to add or edit a skill, or deactivate/reactivate
   it. The current service does not provide physical deletion.
5. Sign out; Admin operations require a logged-in, active Admin session.

### Candidate

1. From Welcome, open Login and choose Register.
2. Register a Candidate, return to Login, and sign in.
3. Open **Hồ sơ cá nhân**, create the profile, then edit and save it.
4. Open **Lời mời làm bài**, accept a Company invitation, save answers, and
   submit once.
5. The submitted score is hidden until the Company releases the result. Return
   to **Kết quả** after release to view the score.
6. Choose **Đăng xuất**, then sign in again to verify a new session.

### Company and Expert

1. Sign in using the temporary accounts prepared above.
2. From the role dashboard, open **Hồ sơ doanh nghiệp** or
   **Hồ sơ chuyên gia**; create or edit the profile and return to Dashboard.
3. As Company, open **Tìm chuyên gia**, search and send an invitation.
4. Open **Hợp đồng của tôi** to review invitations and contract status. Sign in
   as the Expert to accept or reject a pending invitation.
5. After a contract is active, Company can create a task. Expert can start and
   complete the assigned task. Return to Dashboard and sign out from either
   role when finished.
6. Open **Tuyển dụng & đánh giá**. Create a position and set it to **Đang
   tuyển**. When creating a multiple-choice exam, select an Expert who has an
   active contract with the Company; then invite a registered Candidate.
7. After the Candidate submits, open **Kết quả** and select a graded result's
   exam to publish its results. The Candidate can then view the released score.

Role checks and writes are enforced by the corresponding Controllers and
Services. The UI displays operation errors rather than substituting demo data.
Company/Expert registration and Admin account creation after first-run setup
are not currently available in the UI.

## Supplementary workflows

- Candidate can save and submit persisted essay/Coding answers. Company and
  contracted Expert can manually grade; Company publishes results, after which
  Candidate can view the score. Coding is never executed by the application.
- Focus monitoring starts only for the signed-in Candidate's active exam and
  after an explicit confirmation. Focus-loss events are stored in SQLite as
  non-violation metadata; no camera, screen, or audio is captured.
- Company can schedule interviews for a Candidate and optionally assign a
  contracted Expert. Company/Expert can update status; the assigned Expert can
  save scored feedback. Candidate views do not expose evaluation notes.
- Releasing a result for an exam linked to an active skill creates its approved
  assessment source. Admin can issue and revoke certificates; authenticated
  roles can verify a certificate by code. Results from unlinked exams cannot
  qualify for certificates.

## Not implemented or still limited

- UI for authoring essay/Coding questions; those question types must already
  be present in the persisted exam to use the Candidate and grading screens.
- Instructor and Student workspaces beyond placeholder dashboard content.
- Physical skill deletion; use the supported deactivate/reactivate action.
- Company/Expert role provisioning through public registration; use only the
  isolated demo database setup above for demo accounts.
- Job `employment_type` is not stored; the recruitment form exposes only fields
  supported by the current SQLite schema. Company exam authoring remains
  multiple-choice; essay/Coding grading is manual and no candidate code runs.
- A Company without an active Expert contract cannot create exam questions;
  the UI does not assign question authors automatically.

## Verification commands

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
python -m compileall -q app client server tests main.py
```

Tests and smoke tests use temporary SQLite databases. An offscreen startup
smoke test and SQLite-backed recruitment regression test do not replace an
interactive Windows acceptance run.
