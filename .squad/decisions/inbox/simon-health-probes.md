# Decision: DB Readiness Check and Health Probes

**Author:** Simon (DevOps)  
**Date:** 2026-02-27  
**Status:** Implemented (branch `fix/db-health-probes`)

## Context

Azure PostgreSQL Flexible Server (Burstable B1ms) auto-stops after ~7 days of inactivity. When this happens, the container starts, migrations fail silently, and the app serves requests that all fail because the DB is unreachable.

## Decision

1. **`start.sh`** — Added a DB readiness loop (30s max, 2s intervals) using Python `socket.connect()` before running migrations. Falls through gracefully if DB never becomes reachable.

2. **`infra/resources.bicep`** — Added Azure Container Apps health probes:
   - **Liveness probe**: `GET /health` every 30s, 3 failures to restart
   - **Startup probe**: `GET /health` every 10s, up to 30 failures (300s window for migrations)

3. **Dockerfile + docker-compose.yml** — Switched healthchecks from `python -c "import httpx; ..."` to `curl -f` for lower overhead. Added `curl` to Dockerfile apt-get.

## Rationale

- Socket check is zero-dependency (Python stdlib only), fast, and doesn't require `pg_isready` or `psycopg2`.
- Startup probe's 300s window accommodates slow migrations without triggering premature restarts.
- Liveness probe ensures Azure restarts the container if the app becomes permanently unhealthy (e.g., DB connection pool exhausted).
- `curl` healthcheck avoids importing the entire Python runtime + httpx for a simple HTTP check.

## Impact

- No application code changes
- No new dependencies beyond `curl` (standard in most container environments)
- Graceful degradation: app still starts even if DB is unreachable (allows health endpoint to report 503)
