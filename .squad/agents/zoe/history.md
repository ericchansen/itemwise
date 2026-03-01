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
