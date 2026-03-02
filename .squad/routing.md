# Routing Rules

## Domain Routing

| Signal | Route To | Rationale |
|--------|----------|-----------|
| Architecture, design decisions, code review | Mal | Lead owns structure and review |
| FastAPI, database, models, CRUD, migrations, API endpoints, NL/AI processing, embeddings | Kaylee | Backend owns server-side logic |
| Frontend, UI, HTML, CSS, JavaScript, ES modules, user experience | Wash | Frontend owns client-side |
| Auth, login, registration, permissions, sharing, invitations, access control, OAuth, JWT | Jayne | Security owns auth and access |
| CI/CD, GitHub Actions, Docker, deployment, Azure, infra, pipelines | Simon | DevOps owns build and deploy |
| Tests, pytest, E2E, quality, edge cases, coverage | Zoe | Tester owns quality |
| Multi-domain or "team" request | Fan out to relevant agents | Parallel execution |

## Escalation

- If unsure, route to Mal (Lead) for triage.
- Security-sensitive changes require Jayne's review.
- All PRs get Zoe's test verification.

## Quality Gate (Non-Negotiable)

**No feature merges without test coverage.** This is enforced as follows:

1. **Any agent implementing a feature** MUST include tests in their deliverable, OR explicitly hand off to Zoe with a test request before marking work as done.
2. **Zoe MUST be invoked** on every feature branch before merge. If Zoe identifies missing test coverage, the feature is BLOCKED until tests are added.
3. **Multi-step user flows** (e.g., upload → analyze → confirm → add) MUST have lifecycle tests that verify data survives between steps — not just individual endpoint tests.
4. **Lesson learned (2026-02-28):** The image analysis feature shipped with a critical bug (`_identifiedItems` wiped by `clearImagePreview()` in a `finally` block) that was only caught in manual testing. The test suite tested endpoints in isolation but never tested the full user flow. This class of bug is now explicitly in Zoe's charter to catch.
