# Mal — History

## Project Context
- **Project:** Itemwise — conversational inventory assistant
- **Stack:** Python, FastAPI, PostgreSQL, vanilla JS, Azure Container Apps, OpenAI
- **User:** Eric Hansen

## Learnings

### 2025-07 SPEC.md Audit
- **SPEC.md is significantly behind the codebase.** ~20 features exist in code but are undocumented.
- **API paths**: Router mounted at both `/api/v1` (canonical) and `/api` (compat). Spec only says `/api`.
- **Frontend is multi-file now**: `frontend/js/` has 7 JS modules (app, auth, chat, items, settings, state, utils) + PWA assets. Spec still says "single-file HTML".
- **Key undocumented features**: soft-delete/trash, expiration tracking, password reset flow, CSRF protection, rate limiting, confirmation flow for destructive chat actions, logout, delete account, PWA support, Azure Monitor/OpenTelemetry integration.
- **Database model additions**: `deleted_at` on InventoryItem, `expiration_date` on ItemLot — neither in spec.
- **MCP server has 9 tools** (spec says 8); `get_expiring_items_tool` is missing from spec.
- **AI chat defines 7 tools** in INVENTORY_TOOLS (spec says 6); `get_expiring_items` is defined but has NO handler in the chat flow — it will return "Unknown tool" error if the model tries to call it.
- **Email service has 4 functions** (spec documents 2): `send_password_reset_email` and `send_expiration_digest_email` are undocumented.
- **Undocumented env vars**: `CORS_ORIGINS`, `ENV`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `DEBUG`.
- **Key file paths**: `src/itemwise/api.py` (main API), `src/itemwise/ai_client.py` (AI tools), `src/itemwise/server.py` (MCP), `src/itemwise/database/models.py`, `src/itemwise/database/crud.py`, `src/itemwise/auth.py`, `src/itemwise/email_service.py`, `src/itemwise/utils.py`, `src/itemwise/config.py`, `src/itemwise/embeddings.py`.

### 2026-02: Image Analysis Branch Review (`feat/image-analysis`)
- **Architecture:** Follows existing patterns well — new AI function in `ai_client.py`, new endpoints in `api.py`, proper use of rate limiting and authentication.
- **Separation of concerns:** Clean separation — `analyze_image()` in `ai_client.py` handles all OpenAI communication, API layer handles HTTP/validation/orchestration.
- **Bicep infrastructure:** Vision model deployment properly chained (`dependsOn: [embeddingDeployment]`) and parameterized correctly through `main.bicep` → `resources.bicep`.
- **DATABASE_URL encoding:** URL encoding in `config.py` is CORRECT — passwords with special chars (`@`, `#`, etc.) must be percent-encoded for connection strings. Using `quote(str, safe='')` is the proper approach (also applied to username for consistency).
- **Minor issues:**
  - Accidentally committed 41 `.squad-templates/` and `.github/workflows/squad-*` files — these are squad framework scaffolding and should not be in the feature branch.
  - Missing import in `api.py` line 1625: `"image_analysis"},` has trailing quote that should end the string (appears to be line wrap artifact in diff).
- **Verdict:** APPROVE with cleanup required — remove the 41 accidentally committed squad files before merge.
