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
