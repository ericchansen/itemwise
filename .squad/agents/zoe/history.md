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
