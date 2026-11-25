# SkillProof marketplace foundation (Phase 1)

Existing recruitment invitations are company-originated exam invitations, not Candidate job applications.

## Delivered
- MIG-011: job_applications and saved_job_postings, idempotent and backwards-compatible.
- Candidate is_discoverable defaults to off (opt-in required for Company talent search).
- MarketplaceRepository: published job discovery, save/unsave, apply once, view one's applications, withdraw, Company-owned applicant listing and stage updates.
- Permission, migration and privacy integration tests.

## Limits
- This foundation does not yet connect PySide6 or session-aware Services/Controllers.
- Applications do not automatically create exam invitations.
- SQLite currently supports local demo; multi-device sharing needs a later centralized backend.
- Test only with temporary SQLite; never modify real user databases.

## Next phases
- Session-aware Services and Controllers.
- Candidate discovery/application UI and Company talent/applicant management UI.
- Explicit mapping of applications to exam and interview lifecycle.
