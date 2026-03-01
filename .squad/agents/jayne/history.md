# Jayne — History

## Project Context
- **Project:** Itemwise — conversational inventory assistant
- **Stack:** Python, FastAPI, PostgreSQL, vanilla JS, Azure Container Apps, OpenAI
- **User:** Eric Hansen

## Learnings

### 2026-02-27: Login "Connection error" on Azure — Root Cause
- **Symptom:** User sees login form on Azure but gets "Connection error" on submit.
- **Root cause:** `minReplicas: 0` in `infra/resources.bicep` lets the Container App scale to zero. The service worker caches static pages (index.html, JS, icons) so the login form appears instantly, but all API calls (POST /api/auth/login) time out during cold start.
- **Fix:** Changed `minReplicas` from 0 to 1 in `infra/resources.bicep`.
- **Key files:** `infra/resources.bicep` (line ~321), `frontend/sw.js` (caching strategy), `frontend/js/auth.js` (handleAuth catch block shows "Connection error").
- **Auth code path verified:** Registration (JSON to /api/v1/auth/register) → Login (form-urlencoded to /api/v1/auth/login) → JWT cookie + CSRF cookie → authFetch for subsequent requests. All working correctly.
- **CORS note:** CORS_ORIGINS defaults to localhost only. Same-origin requests on Azure don't need CORS, but external API consumers would. The env var CORS_ORIGINS should be set on Azure if cross-origin access is needed.
- **Service worker insight:** SW caches `/`, `/manifest.json`, and icons. API calls (/api/*) use network-first. Non-GET requests skip the SW entirely. This means a down server shows a functional-looking login page but all actions fail silently.

### 2026-02-28: Image Upload Security Review — Critical Issues Found
- **Branch:** `feat/image-analysis`
- **Verdict:** REQUEST CHANGES (critical vulnerabilities must be fixed)
- **Critical finding #1:** Content-Type validation relies on browser-supplied MIME type, which can be spoofed. Attacker can upload `malicious.exe` with `Content-Type: image/jpeg`. Fix: Add magic byte validation using Python's `imghdr` module to verify actual file content.
- **Critical finding #2:** `user_hint` parameter passed to LLM without sanitization or length limits. Vulnerable to prompt injection attacks ("Ignore previous instructions...") and DoS via excessive token usage. Fix: Add 500-char max length validation and anti-injection instructions to system prompt.
- **Medium finding #3:** Quantity field from LLM response cast to `int()` without bounds checking. Could cause data integrity issues with unrealistic values. Fix: Add bounds validation (1-10000 range).
- **Passed checks:** Authentication (both endpoints protected with `get_current_user` + `get_active_inventory_id`), rate limiting (5/min for upload, 10/min for add), file size limit (10 MB max enforced), error handling (no info leakage), base64 encoding (safe), no SSRF/path traversal risks.
- **Key insight:** File upload validation MUST check actual file content (magic bytes), not just HTTP headers. Browser-supplied `Content-Type` headers are untrusted user input.
- **Security pattern:** Image upload endpoints should: (1) validate magic bytes, (2) enforce size limits, (3) sanitize all text inputs to LLM, (4) add anti-injection instructions to system prompts, (5) bounds-check all numeric fields from LLM responses.
