# Decisions

<!-- Canonical decision ledger. Scribe merges from decisions/inbox/. Append-only. -->

## 2026-02-27: User Directive — Domain Agent Model Preference

**By:** Eric Hansen (via Copilot)  
**Date:** 2026-02-27T21:35:00Z  
**Status:** Active

All domain agents (Mal, Kaylee, Wash, Jayne, Simon, Zoe) should use `claude-opus-4.6` by default. Scribe remains on `claude-haiku-4.5`.

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
