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
