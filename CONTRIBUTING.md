# Contributing to Itemwise

Welcome to Itemwise — an AI-powered inventory management application. This document is the
single source of truth for anyone (human or AI agent) working on this codebase. Read it
before making any changes.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Repository Structure](#repository-structure)
4. [Database Models](#database-models)
5. [API Endpoints](#api-endpoints)
6. [Frontend](#frontend)
7. [AI System](#ai-system)
8. [Development Setup](#development-setup)
9. [Testing](#testing)
10. [Deployment](#deployment)
11. [Conventions & Gotchas](#conventions--gotchas)
12. [Completed Roadmap](#completed-roadmap)

---

## Project Overview

Itemwise lets users manage household or business inventory through natural language chat.
Say "Add 2 frozen pizzas to chest freezer" and the AI parses it into structured database
operations. It also provides a traditional CRUD interface for browsing, searching, and
editing items.

**Core value proposition:** Talk to your inventory instead of managing spreadsheets.

**Key capabilities:**
- Natural language chat powered by Azure OpenAI (GPT-4o-mini) with tool calling
- Semantic search via pgvector embeddings (text-embedding-3-small, 1536 dimensions)
- Multi-inventory support with email-based sharing
- Lot tracking with FIFO ordering and oldest-item queries
- Location management (freezer, pantry, garage, etc.)
- JWT authentication with registration and login
- Email invitations via Azure Communication Services

---

## Architecture

```
┌──────────────────────────────────────┐
│          Frontend (index.html)       │  Single-file HTML/JS/CSS
│          Tailwind CSS, dark theme    │  Served by FastAPI
└──────────────┬───────────────────────┘
               │ REST API (JSON)
┌──────────────▼───────────────────────┐
│          FastAPI Application         │  src/itemwise/api.py
│  Auth │ Items │ Chat │ Inventories   │
└──┬───────────┬───────────────────────┘
   │           │
   │    ┌──────▼──────────────────┐
   │    │   AI Client             │  src/itemwise/ai_client.py
   │    │   Azure OpenAI GPT-4o   │  Multi-pass tool calling
   │    │   + Tool definitions    │
   │    └──────┬──────────────────┘
   │           │ Tool calls
┌──▼───────────▼──────────────────────┐
│       Database Layer (CRUD)          │  src/itemwise/database/crud.py
│  SQLAlchemy async │ pgvector search  │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│     PostgreSQL 16 + pgvector         │  Docker (local) or Azure Flexible Server
│  Users│Inventories│Items│Lots│Logs   │
└──────────────────────────────────────┘
```

**Tech stack at a glance:**

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ (Docker image uses 3.12) |
| Web framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 + pgvector |
| AI | Azure OpenAI (GPT-4o-mini chat, GPT-4o vision, text-embedding-3-small embeddings) |
| Auth | JWT (PyJWT) + bcrypt |
| Email | Azure Communication Services |
| Frontend | Modular JS (7 modules), Tailwind CSS (CDN), PWA (service worker + manifest) |
| Package manager | uv |
| Linter | ruff |
| Tests | pytest + pytest-asyncio + Playwright (E2E) |
| Deployment | Azure Container Apps via azd (Bicep) |
| Containers | Docker + Docker Compose |

---

## Repository Structure

```
itemwise/
├── src/itemwise/              # Application source code
│   ├── __init__.py
│   ├── api.py                 # FastAPI app — all REST endpoints + frontend serving
│   ├── ai_client.py           # Azure OpenAI client, tool calling, chat logic
│   ├── auth.py                # JWT tokens, password hashing, OAuth2
│   ├── config.py              # Pydantic Settings (env vars)
│   ├── email_service.py       # Azure Communication Services email
│   ├── embeddings.py          # Text embedding generation (1536-dim vectors)
│   ├── server.py              # MCP server (for Claude Desktop integration)
│   ├── utils.py               # Shared utilities
│   ├── prompts/
│   │   └── system.txt         # AI system prompt (overrides constant in ai_client.py)
│   └── database/
│       ├── models.py          # SQLAlchemy ORM models (7 tables)
│       ├── engine.py          # Async engine, session factory, init
│       └── crud.py            # All database operations
├── frontend/                  # Modular web UI
│   ├── index.html             # HTML shell + Tailwind CSS (CDN)
│   ├── js/                    # JavaScript modules
│   │   ├── app.js             # App initialization + routing
│   │   ├── auth.js            # Authentication (login, register, JWT)
│   │   ├── chat.js            # Chat tab functionality
│   │   ├── items.js           # Items tab (browse, search, CRUD)
│   │   ├── settings.js        # Settings tab (sharing, account)
│   │   ├── state.js           # State management
│   │   └── utils.js           # Shared utilities
│   ├── manifest.json          # PWA web app manifest
│   ├── sw.js                  # Service worker (offline support)
│   └── icons/                 # PWA icons (SVG)
├── tests/                     # 26 test modules, ~322 tests
│   ├── conftest.py            # Fixtures: test DB, users, inventories, mock embeddings
│   ├── test_api.py            # API endpoint tests
│   ├── test_auth.py           # Auth utilities
│   ├── test_crud.py           # Database operations
│   ├── test_e2e.py            # Playwright browser tests
│   ├── test_server.py         # MCP server tools
│   ├── test_sharing.py        # Multi-inventory membership
│   ├── test_lots.py           # Lot tracking / FIFO
│   ├── test_soft_delete.py    # Trash / restore / purge
│   ├── test_image_analysis.py # Image chat endpoints
│   ├── test_password_reset.py # Forgot / reset password flow
│   ├── test_expiration.py     # Expiration date tracking
│   ├── test_rate_limiting.py  # Slowapi rate limit tests
│   └── ...                    # (see tests/ for full list)
├── alembic/                   # Database migrations
├── infra/                     # Azure Bicep templates
│   ├── main.bicep             # Subscription-level deployment
│   └── resources.bicep        # All Azure resources
├── scripts/                   # Maintenance and setup scripts
│   ├── cleanup_e2e_users.py   # Clean up test users from E2E runs
│   └── setup-cd-oidc.sh       # One-time Azure OIDC setup for CD
├── AGENTS.md                  # Mandatory pre-handoff checklist
├── CONTRIBUTING.md            # This file
├── pyproject.toml             # Dependencies, ruff config, scripts
├── pytest.ini                 # Test configuration
├── docker-compose.yml         # Local dev: app (8080) + PostgreSQL (5433)
├── Dockerfile                 # Multi-stage build (uv, Python 3.12-slim)
├── azure.yaml                 # Azure Developer CLI config
├── start.sh                   # Container entrypoint (migrations + uvicorn)
└── fix_migration.py           # Repairs inconsistent Alembic state on startup
```

---

## Database Models

Seven tables defined in `src/itemwise/database/models.py`:

### User
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| email | String | Unique, indexed |
| hashed_password | String | bcrypt hash |
| created_at | DateTime | UTC |

### Inventory
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String | e.g. "Home", "Office" |
| created_at | DateTime | |

A user can own multiple inventories. The default inventory is created lazily — on first
chat interaction, not on registration. This means a new user has 0 inventories until they
send their first chat message.

### InventoryMember
Junction table for sharing. Unique constraint on `(inventory_id, user_id)`.

### Location
Belongs to an inventory. Has a `normalized_name` for fuzzy matching and a 1536-dim
`embedding` vector for semantic location matching.

### InventoryItem
The core entity. Belongs to an inventory, optionally linked to a location. Has a
`quantity` field that is the sum of its lots. Has a 1536-dim `embedding` for semantic
search.

### ItemLot
Tracks batches within an item (e.g., "5 added on Monday, 3 added on Wednesday"). Enables
FIFO tracking and "what's oldest?" queries. Each lot has `quantity`, `added_at`,
`added_by_user_id`, and `notes`.

**Important:** When adding items, create with `quantity=0` then call `create_lot()` which
increments `item.quantity`. Do NOT pass quantity to both `create_item()` and `create_lot()`
or it will double-count.

### TransactionLog
Audit trail of all AI operations. Records operation type, item reference, JSON data, and
status (PENDING, etc.).

---

## API Endpoints

All endpoints are in `src/itemwise/api.py`. Auth endpoints use JWT bearer tokens.
The API is served at both `/api/` and `/api/v1/` (versioned). Auto-generated docs
are available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Authentication
| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/auth/register` | JSON body: `{email, password}` |
| POST | `/api/auth/login` | **Form-encoded** (OAuth2PasswordRequestForm), NOT JSON |
| POST | `/api/auth/refresh` | Refresh JWT token |
| GET | `/api/auth/me` | Current user profile |
| POST | `/api/auth/logout` | Logout (invalidate token) |
| PUT | `/api/auth/password` | Change password |
| POST | `/api/auth/forgot-password` | Request password reset email |
| POST | `/api/auth/reset-password` | Reset password with emailed token |
| DELETE | `/api/auth/account` | Delete user account |

### Items
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/items` | List items (filterable by category, location, limit) |
| POST | `/api/items` | Create item |
| GET | `/api/items/{id}` | Get single item with lots |
| PUT | `/api/items/{id}` | Update item |
| DELETE | `/api/items/{id}` | Soft-delete item (moves to trash) |
| GET | `/api/items/trash` | List soft-deleted items |
| POST | `/api/items/{id}/restore` | Restore item from trash |
| DELETE | `/api/items/{id}/purge` | Permanently delete item |
| GET | `/api/items/expiring` | Items with expiration dates approaching |
| GET | `/api/search` | Semantic + text hybrid search |

### Inventories & Sharing
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/inventories` | List user's inventories |
| GET | `/api/inventories/{id}/members` | List members |
| POST | `/api/inventories/{id}/members` | Add member (sends invite email if user not found) |
| DELETE | `/api/inventories/{id}/members/{uid}` | Remove member |

### Chat
| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/chat` | Natural language chat (AI tool calling) |
| POST | `/api/chat/confirm` | Confirm a pending destructive action |
| POST | `/api/chat/image` | Analyze an uploaded image of items |
| POST | `/api/chat/image/add` | Add items identified in an image |

### Locations, Notifications & Other
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/locations` | List locations |
| POST | `/api/locations` | Create location |
| POST | `/api/notifications/expiration-digest` | Trigger expiration email digest |
| GET | `/health` | Health check (unauthenticated) |
| GET | `/` | Serves frontend |

---

## Frontend

The frontend is a modular web application served from `frontend/` at the root URL (`/`).
It uses vanilla JavaScript split across 7 modules under `frontend/js/`, with Tailwind CSS
loaded from CDN. There is no build system, no bundler, no component framework — changes
take effect immediately on reload.

The app is also a **Progressive Web App (PWA)** — `manifest.json` and `sw.js` enable
"Add to Home Screen" on mobile devices with offline caching support.

### Tabs
- **Chat** — Natural language interface with streaming responses and quick action buttons
- **Items** — Browse and search inventory items, with soft-delete/restore support
- **Settings** — Inventory management, member invitations, account settings

### Key UI patterns
- Dark theme throughout (Tailwind classes)
- JWT stored in `localStorage`; auto-refresh on 401
- Inventory selector dropdown in header (hidden when user has ≤1 inventory or is on settings tab)
- Chat messages rendered with markdown support
- Image upload for item identification via chat
- Error/success toasts for user feedback

### Working with the frontend
Since there's no build step, changes take effect immediately on reload. The HTML shell is
served by FastAPI via `FileResponse`. JS modules are loaded via `<script>` tags. All API
calls use `fetch()` with the JWT bearer token from `localStorage`.

---

## AI System

### How chat works (`ai_client.py`)

1. User sends a message via `/api/chat`
2. System prompt loaded from `src/itemwise/prompts/system.txt`
3. Message sent to Azure OpenAI GPT-4o-mini with tool definitions
4. If the model returns tool calls, they are executed against `crud.py` functions
5. Results are fed back to the model for another round (multi-pass tool calling)
6. Final text response returned to the user

### Tools available to the AI
- `add_item` — Add items to inventory (with location, category, notes)
- `update_item` — Modify existing items
- `remove_item` — Delete items (reduces lot quantity or removes entirely)
- `list_inventory` — List all or filtered items
- `search_inventory` — Semantic search using embeddings
- `add_location` — Create new storage locations
- `get_locations` — List available locations
- `get_oldest_items` — FIFO query for oldest lots

### System prompt
The system prompt file at `src/itemwise/prompts/system.txt` overrides the `SYSTEM_PROMPT`
constant in `ai_client.py`. Always update the file, not the constant.

### Embeddings
Generated by Azure OpenAI `text-embedding-3-small` (1536 dimensions). Used for both item
search and location matching. When Azure OpenAI is unavailable, falls back to zero vectors.

---

## Development Setup

### Prerequisites
- Python 3.11+ via [uv](https://docs.astral.sh/uv/) (Docker image uses 3.12)
- Docker Desktop (for PostgreSQL)
- Azure CLI (for Azure OpenAI features)

### Quick start
```bash
uv sync                          # Install dependencies
cp .env.example .env             # Configure environment
docker compose up -d             # Start PostgreSQL (port 5433) + app (port 8080)
```

### Running outside Docker
```bash
docker compose up -d itemwise-db    # Just the database
uv run alembic upgrade head         # Apply migrations
uv run itemwise-web                 # Start dev server on port 8080
# Or: uv run uvicorn itemwise.api:app --reload --port 8080
```

### Environment variables
See `.env.example` for all options. Key ones:
- `DATABASE_URL` — PostgreSQL connection string
- `AZURE_OPENAI_ENDPOINT` — Azure OpenAI endpoint
- `AZURE_OPENAI_DEPLOYMENT` — GPT model deployment name (gpt-4o-mini)
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` — Embedding model deployment
- `AZURE_COMMUNICATION_CONNECTION_STRING` — For invite emails
- `AZURE_COMMUNICATION_SENDER` — Email sender address

---

## Testing

### Test infrastructure
```bash
docker compose up -d             # Start DB + app
```
Tests connect to PostgreSQL on port 5433 (database: `inventory`). The test database is
created/destroyed per test session via fixtures in `conftest.py`.

### Commands
```bash
# Linting
uv run ruff check .

# Unit tests (excludes E2E by default)
uv run python -m pytest tests/ -v --tb=short

# E2E tests (requires running app on localhost:8080)
uv run python -m pytest tests/test_e2e.py -v -m e2e --no-cov

# E2E against Azure
$env:E2E_BASE_URL = "https://ca-api-ki7zeahtw2lr6.proudwater-caeb734c.centralus.azurecontainerapps.io"
uv run python -m pytest tests/test_e2e.py -v -m e2e --no-cov
```

### Important test details
- `conftest.py` has an **autouse** `mock_embeddings` fixture that patches all embedding
  functions globally. Test files that need real embeddings must override this fixture.
- Coverage threshold is 40% (enforced by pytest-cov).
- E2E tests use Playwright and require the app to be running.
- E2E chat tests may auto-skip if Azure OpenAI credentials are unavailable.
- Tests needing an `inventory_id` must use the `test_inventory` fixture.

### Test markers
- `@pytest.mark.asyncio` — Async tests (mode: auto)
- `@pytest.mark.e2e` — End-to-end browser tests
- `@pytest.mark.slow` — Long-running tests
- `@pytest.mark.integration` — Integration tests

---

## Deployment

### Azure infrastructure
Deployed to **Azure Container Apps** in **centralus** via `azd` (Azure Developer CLI).

| Resource | Purpose |
|----------|---------|
| Container App | Runs the FastAPI application |
| PostgreSQL Flexible Server | Database (Burstable B1ms) |
| Azure OpenAI | GPT-4o-mini + text-embedding-3-small |
| Azure Communication Services | Invite emails |
| Container Registry | Docker image storage |
| Key Vault | Secrets management |
| Log Analytics | Logging and monitoring |

### Deploy commands
```bash
azd deploy                       # Deploy code changes (no infra changes)
azd provision                    # Provision/update Azure infrastructure
azd up                           # Provision + deploy (full)
```

### Azure details
- **URL:** `https://ca-api-ki7zeahtw2lr6.proudwater-caeb734c.centralus.azurecontainerapps.io`
- **Resource group:** `rg-itemwise-prod`
- **azd environment:** `itemwise-prod`
- **Subscription:** `ME-MngEnvMCAP529863-erichansen-1`

### SSL note
asyncpg uses `?ssl=require` while psycopg2 (used by Alembic) uses `?sslmode=require`.
The `alembic/env.py` file automatically translates between these formats.

### PostgreSQL auto-stop
The Azure PostgreSQL Flexible Server (Burstable B1ms) may auto-stop when idle. Before
deploying, check its state:
```bash
az postgres flexible-server show --resource-group rg-itemwise-prod \
  --name psql-ki7zeahtw2lr6 --query state -o tsv
```
Start it if stopped:
```bash
az postgres flexible-server start --resource-group rg-itemwise-prod \
  --name psql-ki7zeahtw2lr6
```

---

## Conventions & Gotchas

### Git
- **Default branch:** `master` (not main)
- **Commit prefixes:** `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `ci`, `perf`
- Use feature branches and pull requests — never push directly to master
- Scan staged diffs for secrets before every commit

### Code style
- Line length: 140 characters (ruff config in `pyproject.toml`)
- Python target: 3.11+
- Async everywhere: all database operations, all API endpoints
- Use type hints

### Login is form-encoded, not JSON
The `/api/auth/login` endpoint uses `OAuth2PasswordRequestForm`, which expects
`application/x-www-form-urlencoded` — not JSON. This is a common source of confusion.

### Shell scripts need LF line endings
`.gitattributes` enforces `*.sh text eol=lf`. Windows CRLF will break the Docker
container's `start.sh`. Never override this.

### `prek` is intentional
`prek` (prek.j178.dev) is a Rust-based pre-commit tool. It is NOT a typo or leftover. Do
not remove it.

### Quantity tracking
When adding items programmatically, create with `quantity=0` then call `create_lot()`
which increments `item.quantity`. Passing quantity to both `create_item()` and
`create_lot()` will double-count.

### Default inventory is lazy
New users have 0 inventories. The default inventory is created on the first chat message,
not on registration. Code that assumes a user always has an inventory will break for
brand-new users.

### System prompt location
Edit `src/itemwise/prompts/system.txt`, not the `SYSTEM_PROMPT` constant in `ai_client.py`.
The file overrides the constant at runtime.

### Email service graceful degradation
If `AZURE_COMMUNICATION_CONNECTION_STRING` is not set, email functions silently return
`False` without raising errors. The invite endpoint still works — it just doesn't send
emails.

---

## Completed Roadmap

All items from the original prioritized roadmap have been implemented:

- ✅ **Rate limiting** — slowapi on `/api/chat` and `/api/auth/*` endpoints
- ✅ **Password reset** — Forgot/reset flow with email token via Azure Communication Services
- ✅ **Expiration date tracking** — `expiration_date` on ItemLot, AI tools support it, `/api/items/expiring`
- ✅ **PWA / offline support** — Service worker, web app manifest, installable on mobile
- ✅ **Expiration notifications** — Email digest via `/api/notifications/expiration-digest`
- ✅ **Image analysis** — GPT-4o vision for item identification from photos
- ✅ **Soft delete / restore / purge** — Trash flow with restore and permanent delete
- ✅ **Confirmation flow** — AI asks before destructive actions
- ✅ **Account deletion** — Full account removal endpoint
- ✅ **CSRF protection** — On sensitive endpoints

---

*See AGENTS.md for the mandatory pre-handoff checklist that must be completed before any
work is handed off.*
