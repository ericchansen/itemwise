# Zoe — History

## Project Context
- **Project:** Itemwise — conversational inventory assistant
- **Stack:** Python, FastAPI, PostgreSQL, vanilla JS, Azure Container Apps, OpenAI
- **User:** Eric Hansen

## Learnings

### 2026-02-27: Resilience Tests
- `tests/test_health.py` already existed with full coverage: 200/healthy, 503/unhealthy, response structure with `dependencies.database`
- Added `pool_pre_ping` and `pool_recycle` assertions to `tests/test_engine.py::TestDatabaseEngine`
- Engine pool internals accessed via `engine.pool._pre_ping` and `engine.pool._recycle`
- Pre-existing test failures (6 FAILED, 113 ERROR) are all DB session/table-creation race conditions — not related to resilience work
- Test patterns: async tests use `pytest.mark.asyncio`, httpx `AsyncClient` with `ASGITransport`, mock DB via `patch("itemwise.api.AsyncSessionLocal", ...)`
- `conftest.py` has autouse `mock_embeddings` fixture — all tests get mocked embeddings by default
- Health endpoint is at `/health` (not under `/api/v1`), catches `SQLAlchemyError | OSError`

### 2026-03-02: Production Manual Browser Test (Post Image-Analysis Rollback)
- Tested production URL after master rollback removed image analysis feature
- **All 7 test steps PASSED:**
  1. Login page loads cleanly — no flash of content, Login/Register tabs, email/password fields
  2. Registration works — created `prodtest@test.com` account, auto-logged in
  3. Chat interface works — sent "What's in my inventory?", got correct "Your inventory is empty." response
  4. Items tab loads — search bar, location dropdown, Add button, "No items yet" placeholder
  5. Settings tab loads — Profile (email), Change Password, Inventory Members, Notifications sections
  6. **No image analysis UI exists** — DOM inspection confirmed: 0 file inputs, 0 camera buttons, 0 image-analysis elements. Rollback is clean.
  7. Logout works — returns to login screen
- Minor UX observation: after logout, form retains pre-filled credentials from prior session (not a bug, standard browser autofill behavior)
- Console had 1 error (expected: /api/v1/auth/me 401 on unauthenticated page load) and tailwind CDN warning
- Screenshot saved as prod-test-final-state.png