# SkillProof Demo Guide

This guide describes what is currently implemented and what can be demonstrated
without presenting placeholders as completed features.

## Preparation

- Use Python 3.13 and install dependencies with `pip install -r requirements.txt`.
- Run `python main.py` from a disposable checkout or demo environment. Do not
  replace or delete a user database to prepare a demo.
- On a new database, complete the First-Run Setup form to create the initial
  administrator. There is no default admin password.
- Public registration creates Candidate accounts only. Company and Expert demo
  accounts must already exist in the disposable QA/demo database; the UI has no
  role-provisioning flow.

## Verified UI flows

### Candidate

1. From Welcome, open Login and choose Register.
2. Register a Candidate, return to Login, and sign in.
3. Open **Hồ sơ cá nhân**, create the profile, then edit and save it.
4. Choose **Đăng xuất**; the session ends and Login is shown. Sign in again to
   verify the session can be established again.

### Company and Expert profiles

1. Sign in using an existing Company or Expert account.
2. From the role dashboard, open **Hồ sơ doanh nghiệp** or
   **Hồ sơ chuyên gia**.
3. Create and then edit the profile; use **Quay lại Dashboard** to return.

The profile screens and role checks are implemented. The dashboard's other
Company/Expert menu entries are not connected to their screens.

## Implemented domain flows not yet reachable from the dashboard

- Company expert search and invitations are implemented in the search screen
  and service.
- Company/Expert contract transitions and Company-created / Expert-completed
  tasks are implemented and covered by controller/service integration tests.
- MainWindow contains some search/contract/task routes, but the dashboard does
  not currently expose entry points to all of them. Do not claim these are
  end-to-end GUI demo flows until the navigation is connected.

## Not implemented

- Job-posting and candidate recruitment workflow.
- End-user skill exams, grading, interview evaluation, certificate issuance,
  or certificate verification. Related database tables and task references do
  not by themselves implement these workflows.
- Admin user/role management, skill management, or system settings. Admin
  currently has first-run account setup and a placeholder dashboard.
- Instructor and Student dashboards beyond role-specific placeholder content.

## Verification commands

```powershell
python -m pytest -q
python -m compileall -q app client server tests main.py
```

Tests use temporary SQLite databases. The desktop startup smoke test should
also use a temporary database and `QT_QPA_PLATFORM=offscreen` in CI; it does
not replace an interactive Windows acceptance run.
