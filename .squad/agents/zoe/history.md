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
### 2026-02-28: Image Analysis Test Review
- Reviewed `tests/test_image_analysis.py` (15 tests) for `feat/image-analysis` branch
- All tests pass (15/15), good coverage of happy paths and validation
- Test fixture patterns: autouse `_reset_limiter()`, `patch_db`, async `client`, `known_user`, `auth_header()` helper
- Image endpoints: `POST /api/v1/chat/image` (5/min limit), `POST /api/v1/chat/image/add` (10/min limit)
- Coverage gaps identified: no tests for file size limit (10 MB), concurrent uploads, network errors from vision API, actual rate limit breach (5/min)
- Mock patterns: `patch("itemwise.api.AZURE_OPENAI_ENABLED")` and `patch("itemwise.ai_client.analyze_image")` correctly patched at call sites
- `analyze_image()` parsing tested: JSON, markdown fences, invalid JSON, non-list, user hint passing
- Endpoints tested: unsupported file type, empty file, OpenAI disabled, successful analysis, items found/not found, auth required, validation errors
- Missing: E2E test for browser-based image upload (Playwright with file upload fixture)
- `test_config.py` change: correctly updates URL-encoding assertion from raw `p@ss:word!` to encoded `p%40ss%3Aword%21`

### 2026-03-01: Image Lifecycle Tests (Bug Prevention)
- Added `TestImageLifecycle` class (6 tests) to `tests/test_image_analysis.py` — total now 26 tests
- Tests the full analyze→add contract: POST `/chat/image` returns items, then POST `/chat/image/add` with those exact items succeeds
- Key test: `test_analyze_then_add_items_lifecycle` — chains both endpoints, verifying items from analysis are valid input for the add endpoint
- `test_add_items_verifiable_via_items_endpoint` — confirms added items appear in GET `/items` (response wraps items in `{"items": [...]}`)
- `test_add_items_with_empty_list` — catches the silent no-op when `_identifiedItems` gets wiped (the frontend bug pattern)
- `test_lifecycle_items_format_compatibility` — detects format drift between analysis response and add request
- Coverage fail-under 40% is pre-existing (34.67% total) — not related to these tests
- Lesson: always test multi-step workflows as connected flows, not just individual endpoints in isolation
