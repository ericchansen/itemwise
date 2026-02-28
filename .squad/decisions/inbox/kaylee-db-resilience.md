# Decision: Connection Pool Recycling for Azure DB Auto-Pause Resilience

**Author:** Kaylee (Backend Dev)  
**Date:** 2026-02-27  
**Status:** Implemented

## Context

Azure PostgreSQL Flexible Server (Burstable B1ms) auto-stops after ~7 days of inactivity. When this happens, the app serves static HTML fine but all API calls fail silently because the connection pool holds stale connections to an unreachable DB.

## Decision

Added `pool_recycle=3600` to `create_async_engine()` in `src/itemwise/database/engine.py`. This forces SQLAlchemy to discard and recreate connections older than 1 hour, preventing stale connections from accumulating after a DB auto-pause/restart cycle.

Combined with the existing `pool_pre_ping=True`, the engine now:
1. Recycles connections every hour (prevents long-lived stale connections)
2. Pings before each use (catches connections that went stale between recycles)

## Verification

- `/health` endpoint already correctly returns 503 with `{"status": "unhealthy", "dependencies": {"database": "unhealthy"}}` when DB is unreachable
- Health endpoint is at `/health` (root level, not behind `/api` prefix) — suitable for container health probes
- All 210 unit tests and 7 E2E tests pass
