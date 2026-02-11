# Agent Instructions for Itemwise

## MANDATORY Pre-Handoff Checklist

**You MUST complete ALL of these steps before calling `task_complete` or telling the user you are done. NO EXCEPTIONS.**

### 1. Lint
```bash
uv run ruff check .
```
All checks must pass.

### 2. Start Test Infrastructure
```bash
docker compose up -d
```
Wait for both `itemwise-app` (port 8080) and `itemwise-db` (port 5433) to be healthy.

### 3. Run Full Unit Test Suite
```bash
uv run python -m pytest tests/ -v --tb=short
```
All tests must pass. Do NOT skip any.

### 4. Run E2E Tests Locally
```bash
uv run python -m pytest tests/test_e2e.py -v -m e2e --no-cov
```
All E2E tests must pass against localhost:8080.

### 5. Deploy to Azure
```bash
azd deploy
```
Wait for deployment to complete successfully.

### 6. Run E2E Tests Against Azure
```powershell
$env:E2E_BASE_URL = "https://ca-api-ki7zeahtw2lr6.proudwater-caeb734c.centralus.azurecontainerapps.io"
uv run python -m pytest tests/test_e2e.py -v -m e2e --no-cov
```
All E2E tests must pass against Azure.

### 7. Verify with Browser (Playwright MCP)
Open the app in the browser (both local and Azure URLs) and interact with it:
- Log in or register
- Send a chat message like "Add 2 frozen pizzas to chest freezer"
- Verify the response makes sense
- Check the Items tab shows the added items

**If ANY step fails, FIX IT before handing off. NEVER hand off broken code.**

---

## Git Workflow

- **Default branch**: `master` (not main)
- **Feature branches**: Always use `<type>/<short-description>` branches for new work
- **Prefixes**: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `ci`, `perf`
- **Never commit directly to master** for new features — use PRs

### Before Any Commit
1. Run linter
2. Run full test suite
3. Run E2E tests
4. Scan `git diff --staged` for secrets (API keys, tokens, passwords, connection strings)

---

## Development Environment

| Component | Details |
|-----------|---------|
| **Package manager** | `uv` |
| **Linter** | `ruff` |
| **Test DB** | Docker PostgreSQL on port 5433, DB name: `inventory` |
| **App** | Docker on port 8080 |
| **Azure URL** | `https://ca-api-ki7zeahtw2lr6.proudwater-caeb734c.centralus.azurecontainerapps.io` |
| **Azure region** | centralus |
| **Deploy command** | `azd deploy` |

## Key Technical Notes

- `prek` (prek.j178.dev) is a Rust-based pre-commit tool. It is NOT beads. Do NOT remove it.
- Login endpoint uses `application/x-www-form-urlencoded` (OAuth2PasswordRequestForm), not JSON.
- `conftest.py` has autouse `mock_embeddings` fixture — test files testing real embeddings must override it.
- Shell scripts MUST have LF line endings (enforced by `.gitattributes`).
- Azure SSL: asyncpg uses `?ssl=require`, psycopg2 uses `?sslmode=require`. `alembic/env.py` translates.
