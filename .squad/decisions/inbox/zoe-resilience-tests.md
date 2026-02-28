# Decision: Resilience Test Coverage

**Author:** Zoe (Tester)
**Date:** 2026-02-27
**Status:** Informational

## Context
Eric requested tests for health endpoint and DB pool resilience config as part of Azure PostgreSQL auto-stop handling.

## Findings
1. **`test_health.py` already had full coverage** — healthy (200), unhealthy (503), response structure validation. No new tests needed.
2. **Added pool config tests to `test_engine.py`** — `pool_pre_ping=True` and `pool_recycle=3600` assertions to verify resilience settings aren't accidentally removed.

## Note on Pre-existing Failures
The test suite has 6 failures and 113 errors unrelated to resilience work — all stem from DB session/table-creation race conditions in `test_crud.py`, `test_soft_delete.py`, `test_server.py`, `test_rate_limiting.py`, and `test_cross_inventory_auth.py`. These should be triaged separately.
