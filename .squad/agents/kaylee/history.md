# Kaylee — History

## Project Context
- **Project:** Itemwise — conversational inventory assistant
- **Stack:** Python, FastAPI, PostgreSQL, vanilla JS, Azure Container Apps, OpenAI
- **User:** Eric Hansen

## Learnings

- **DB engine config** lives in `src/itemwise/database/engine.py` — `create_async_engine()` with `pool_pre_ping=True`, `pool_recycle=3600`, `pool_size=5`, `max_overflow=10`
- **Health endpoint** at `/health` in `src/itemwise/api.py` (line ~369) — runs `SELECT 1`, returns 503 with `{"status": "unhealthy", "dependencies": {"database": "unhealthy"}}` when DB is down. Mounted on root app, not behind `/api` prefix.
- **Azure PostgreSQL Flexible Server (B1ms)** auto-pauses after ~7 days of inactivity — `pool_recycle=3600` + `pool_pre_ping=True` handles stale connections on resume
- **Pre-existing test failures**: `test_sharing.py` and `test_soft_delete.py` have 78 errors (schema/migration issues), unrelated to engine config
