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
