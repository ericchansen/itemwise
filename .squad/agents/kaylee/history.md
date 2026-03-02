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
- **Image analysis bug (2026-03-02)**: `/chat/image` endpoint returns catch-all error because the `gpt-4o` vision model deployment was never provisioned in Azure OpenAI. The Bicep on `feat/image-analysis` adds it, but `azd provision` was never run — only `azd deploy`. The code in `ai_client.py:analyze_image()` defaults to deployment name `"gpt-4o"` which doesn't exist. Secondary issue: `analyze_image()` is synchronous and blocks the async event loop (needs `asyncio.to_thread()` wrapper). Full diagnosis in `.squad/decisions/inbox/kaylee-image-analysis-diagnosis.md`.
