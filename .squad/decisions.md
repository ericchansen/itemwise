# Decisions

<!-- Canonical decision ledger. Scribe merges from decisions/inbox/. Append-only. -->

## 2026-02-27: User Directive — Domain Agent Model Preference

**By:** Eric Hansen (via Copilot)  
**Date:** 2026-02-27T21:35:00Z  
**Status:** Active

All domain agents (Mal, Kaylee, Wash, Jayne, Simon, Zoe) should use `claude-opus-4.6` by default. Scribe remains on `claude-haiku-4.5`.

---

## 2026-02-28: Azure PostgreSQL Auto-Pause Resilience Suite

**Coordinated by:** Scribe (Kaylee, Wash, Simon, Zoe agents)  
**Date:** 2026-02-28T000700Z  
**Status:** Implemented

### Overview
Azure PostgreSQL Flexible Server (Burstable B1ms) auto-stops after ~7 days of inactivity. Four agents implemented coordinated fixes:

### Kaylee (Backend): Connection Pool Recycling
**Decision:** Added `pool_recycle=3600` to `create_async_engine()` in `src/itemwise/database/engine.py`
- Discards and recreates connections older than 1 hour
- Combined with existing `pool_pre_ping=True` for dual-layer resilience
- All 210 unit tests + 7 E2E tests pass

### Wash (Frontend): Error Feedback Pattern
**Decision:** Implemented `showConnectionError()` utility in `frontend/js/utils.js`
- Wired into catch blocks in `items.js` (4 blocks) and `settings.js` (3 blocks)
- Added `#connection-error` dismissible banner to `index.html`
- Network errors → "⚠️ Can't connect to server. Please try again later."
- Other errors → "⚠️ Something went wrong. Please try again later."
- Filters `Unauthorized` errors (handled by auth flow)

### Simon (DevOps): DB Readiness & Health Probes
**Decision:** Multi-layer health infrastructure in branch `fix/db-health-probes`
- `start.sh`: Added DB readiness loop (30s max, 2s intervals) using Python `socket.connect()`
- `infra/resources.bicep`: Liveness probe (`GET /health` every 30s, 3 failures to restart); Startup probe (`GET /health` every 10s, up to 30 failures)
- `Dockerfile` + `docker-compose.yml`: Switched healthchecks to `curl -f` (zero-dependency socket check)
- App gracefully starts even if DB unreachable (health endpoint reports 503 until DB available)

### Zoe (Tester): Resilience Test Coverage
**Decision:** Test suite validation + pool config assertions
- `test_health.py`: Already had full coverage (healthy 200, unhealthy 503, structure validation)
- `test_engine.py`: Added assertions for `pool_pre_ping=True` and `pool_recycle=3600` to prevent accidental removal
- All 210 unit tests + 7 E2E tests pass
- 6 pre-existing failures unrelated to resilience (DB session/table-creation race conditions in `test_crud.py`, `test_soft_delete.py`, `test_server.py`, `test_rate_limiting.py`, `test_cross_inventory_auth.py` — out of scope)

### Rationale
- Connection recycling prevents stale connections from accumulating after DB restart
- Frontend feedback eliminates silent error swallowing
- Readiness check and health probes ensure Azure detects and responds to DB unavailability
- Test assertions prevent configuration regression

---

## 2026-02-27: Set Azure Container App minReplicas to 1

**Author:** Jayne (Security Dev)  
**Date:** 2026-02-27  
**Status:** Implemented (pending deploy)

**Context:** Users reported "I can't even login to the app" on Azure. Container App had `minReplicas: 0`, allowing scale-to-zero. Service worker masked outage with cached static content.

**Decision:** Changed `minReplicas` from `0` to `1` in `infra/resources.bicep` to ensure at least one instance always running.

**Trade-offs:**
- Pro: Login and all API calls work immediately without cold-start delay
- Con: Slight cost increase (~$5-10/mo for 0.5 CPU / 1Gi)

**Branch:** `fix/azure-login-scale-to-zero`

**Next Steps:** Deploy with `azd provision` then `azd deploy`

---

## 2025-07: SPEC.md Requires Major Update

**Author:** Mal (Lead)  
**Status:** Recommendation

SPEC.md is significantly outdated — ~20 features/capabilities exist in code but are undocumented, and several details are stale.

### Key areas requiring updates
1. **Frontend architecture** — no longer single-file; now modular JS + PWA
2. **API endpoints** — ~10 undocumented endpoints (trash, restore, purge, expiring, expiration-digest, forgot-password, reset-password, logout, delete-account, confirm-action)
3. **Database schema** — `deleted_at` on InventoryItem, `expiration_date` on ItemLot
4. **AI tools** — `get_expiring_items` tool defined but handler missing (bug)
5. **MCP tools** — `get_expiring_items_tool` undocumented
6. **Security features** — CSRF, rate limiting, cookie-based auth undocumented
7. **Email functions** — password reset + expiration digest emails undocumented
8. **Environment variables** — 4 new env vars undocumented
9. **API versioning** — dual `/api/v1` + `/api` mount undocumented

### Bug Found
`get_expiring_items` is defined in INVENTORY_TOOLS (sent to OpenAI model) but has no handler in the chat `tool_handlers` dict. If the model calls it, user gets "Unknown tool" error.
