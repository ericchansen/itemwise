# Simon — History

## Project Context
- **Project:** Itemwise — conversational inventory assistant
- **Stack:** Python, FastAPI, PostgreSQL, vanilla JS, Azure Container Apps, OpenAI
- **User:** Eric Hansen

## Learnings
- Azure PostgreSQL Flexible Server (Burstable B1ms) auto-stops after ~7 days of inactivity. Container must handle DB being unreachable at startup.
- `start.sh` MUST have LF line endings — enforced by `.gitattributes` (`*.sh text eol=lf`). Always verify with binary read after editing.
- Health endpoint: `GET /health` returns `{"status":"healthy","dependencies":{"database":"healthy"}}` (200) or 503 when DB is down.
- Container Apps health probes go in `template.containers[].probes[]` with types `Liveness` and `Startup` (PascalCase).
- Startup probe uses `failureThreshold: 30` × `periodSeconds: 10` = 300s window for migrations to complete.
- Docker image is `python:3.12-slim` — curl not included by default, added explicitly in Dockerfile.
- Healthchecks switched from `python -c "import httpx; ..."` to `curl -f` for lower overhead and no Python import chain.
- `docker-compose.yml` app service depends on `postgres: condition: service_healthy` — DB healthcheck uses `pg_isready`.
- Pre-existing test failures: parallel test runs cause `duplicate key` errors in table creation — unrelated to infra changes.
- **CI/CD Comparison (teamskills vs itemwise, 2026-02):**
  - GitHub Deployments sidebar is driven by `environment:` key on workflow jobs. teamskills uses `environment: production` (deploy) and `environment: staging` (PR). itemwise cd.yml has NO `environment:` key — that's why deployments don't show in sidebar.
  - teamskills uses client secret auth (`azure/login` with `creds` JSON). itemwise uses OIDC federated credentials (`id-token: write` + `client-id`/`tenant-id`/`subscription-id`). Itemwise's approach is more secure — no rotating secrets.
  - teamskills uses `azure/container-apps-deploy-action@v1` for direct ACR build+deploy. itemwise uses `azd deploy` which is higher-level but adds latency.
  - teamskills has a single `ci-cd.yml` (lint → test → deploy chain). itemwise splits CI (`ci.yml`) and CD (`cd.yml` triggered by `workflow_run`). Itemwise's split is cleaner separation of concerns.
  - itemwise has features teamskills lacks: concurrency groups, security scan (bandit), dependency audit (pip-audit), infra-change detection (only provisions when `infra/` changed), post-deploy E2E against production.
  - teamskills PR staging uses dedicated Bicep (`infra/staging/main.bicep`) with a separate resource group. itemwise PR staging reuses production infra (same RG, same PG server, per-PR DB + container app). Itemwise's approach is cheaper but less isolated.
  - teamskills PR cleanup scales to zero + stops Postgres. itemwise PR cleanup fully deletes container app, database, and ACR image — cleaner but slower to re-deploy.
  - Both repos use smoke tests on PR staging. teamskills checks health + frontend + config.js + cross-connectivity. itemwise runs full E2E test suite against staging — more thorough.
- **GitHub Environments added (2026-02-28):** Added `environment: production` to `cd.yml` deploy job and `environment: staging` to `pr-staging.yml` deploy-and-test job. Created both environments via `gh api`. This enables deployment tracking in the GitHub repo sidebar. Also added a deployment summary step to `cd.yml` that writes URL, commit SHA, and timestamp to `$GITHUB_STEP_SUMMARY`.
- **Cherry-pick PR workflow for clean fixes (2026-03-01):** When a feature branch (`fix/auth-flash-on-load`) was created before a master rollback and contains unwanted commits, use cherry-pick to create a clean branch: `git checkout master && git checkout -b fix/auth-flash-clean && git cherry-pick <commit-sha>`. This isolates the desired fix from unrelated commits. PR #25 created this way for Wash's auth flash fix (`7a910f3`). Original branch preserved — never delete source branches that may have other useful commits.
