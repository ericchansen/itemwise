# Itemwise

AI-powered inventory management with natural language chat, semantic search, and image analysis. Track items across multiple locations — freezer, garage, pantry, anywhere — using conversational interfaces, a progressive web app, or AI agents via MCP.

## Features

- 🧠 **AI Chat** — Natural language understanding powered by Azure OpenAI GPT-4o-mini with tool calling
- 📷 **Image Analysis** — Photograph items and the AI identifies them (GPT-4o vision)
- 🔍 **Semantic Search** — Hybrid text + vector search via pgvector and text-embedding-3-small (1536-dim)
- 📅 **Expiration Tracking** — Track expiry dates and receive email digest notifications
- 🗑️ **Soft Delete / Restore** — Trash, restore, and purge items
- 🏠 **Multi-Inventory Sharing** — Share inventories with other users via email invitations
- 📦 **Lot Tracking** — FIFO ordering with per-lot quantities and expiration dates
- 🔐 **JWT Authentication** — Registration, login, logout, password change, and password reset via email
- ✅ **Confirmation Flow** — AI asks for confirmation before destructive actions
- 📱 **PWA** — Installable web app with service worker and offline support
- 🤖 **MCP Server** — Expose inventory tools to Claude Desktop and other AI agents
- 🛡️ **Rate Limiting & CSRF Protection** — Secured sensitive endpoints
- ☁️ **Azure Container Apps** — One-command deployment with `azd` and Bicep IaC

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/ericchansen/itemwise.git
cd itemwise
cp .env.example .env   # Edit with your values
uv sync
```

### 2. Start services

```bash
docker compose up -d          # PostgreSQL (5432) + app (8080)
docker compose ps             # Verify both are healthy
```

The app container handles migrations automatically via `start.sh`, so once healthy
you can open [http://localhost:8080](http://localhost:8080).

> **Developing outside Docker?** Start only the database with `docker compose up -d postgres`,
> then run `uv run alembic upgrade head` and `uv run itemwise-web`. See CONTRIBUTING.md for details.

### 3. Configure Azure OpenAI

Add your Azure OpenAI credentials to `.env`:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_VISION_DEPLOYMENT=gpt-4o
```

The app authenticates via `DefaultAzureCredential` — run `az login` first.

## Web Interface

The frontend is a modular PWA built with Tailwind CSS and vanilla JavaScript:

```
frontend/
├── index.html          # HTML shell + Tailwind CSS
├── js/
│   ├── app.js          # App initialization
│   ├── auth.js         # Authentication flows
│   ├── chat.js         # Chat tab
│   ├── items.js        # Items tab
│   ├── settings.js     # Settings tab
│   ├── state.js        # State management
│   └── utils.js        # Shared utilities
├── manifest.json       # PWA manifest
├── sw.js               # Service worker
└── icons/              # PWA icons
```

**Chat examples:**
- *"I just bought 5 bags of frozen vegetables and put them in the chest freezer"*
- *"I used 2 AA batteries from the garage"*
- *"What meat do I have that expires this month?"*

**Image analysis:** Photograph a shelf or group of items — the AI identifies them and offers to add them to your inventory.

## MCP Client Configuration

Add to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "itemwise": {
      "command": "uv",
      "args": ["run", "itemwise-server"],
      "cwd": "/path/to/itemwise"
    }
  }
}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `add_item` | Add an item to a location with quantity, category, and expiration |
| `update_item_tool` | Update an existing item's details |
| `remove_item` | Remove an item from inventory |
| `list_inventory` | List items, optionally filtered by category or location |
| `search_inventory` | Semantic search across all items |
| `add_location` | Create a new storage location |
| `get_locations` | List all storage locations |
| `get_oldest_items_tool` | Get items with the oldest lots (FIFO) |

## REST API

The API serves 30+ endpoints across authentication, items, chat, search, locations, inventories, and notifications. Both `/api/` and `/api/v1/` route prefixes are supported.

| Group | Endpoints | Highlights |
|-------|-----------|------------|
| **Auth** | 9 | Register, login (form-encoded), JWT refresh, password reset via email, account deletion |
| **Items** | 9 | CRUD, soft-delete/restore/purge, expiration tracking |
| **Chat** | 4 | Natural language, confirmation flow, image analysis, image-to-item |
| **Search** | 1 | Hybrid semantic + text search |
| **Locations** | 2 | List and create |
| **Inventories** | 4 | List, members, invite, remove member |
| **Notifications** | 1 | Expiration digest email |
| **Health** | 1 | `GET /health` |

Interactive API docs: [http://localhost:8080/docs](http://localhost:8080/docs)

## Configuration

Copy `.env.example` and edit:

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=inventory
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Application
DEBUG=false
ENV=production
SECRET_KEY=<generate-with-python-secrets>

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_VISION_DEPLOYMENT=gpt-4o

# Email (password reset + notifications)
AZURE_COMMUNICATION_CONNECTION_STRING=endpoint=https://...
AZURE_COMMUNICATION_SENDER=DoNotReply@...
```

> **Security:** `SECRET_KEY` (or `JWT_SECRET_KEY`) is required when `DEBUG=false` or `ENV=production`. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Project Structure

```
itemwise/
├── src/itemwise/
│   ├── api.py              # FastAPI REST API + frontend serving
│   ├── ai_client.py        # Azure OpenAI integration + tool calling
│   ├── auth.py             # JWT authentication + password hashing
│   ├── config.py           # Pydantic Settings configuration
│   ├── email_service.py    # Azure Communication Services email
│   ├── embeddings.py       # Semantic search embeddings (pgvector)
│   ├── server.py           # MCP server for AI agents
│   ├── utils.py            # Shared utilities
│   ├── prompts/
│   │   └── system.txt      # AI system prompt
│   └── database/
│       ├── models.py       # SQLAlchemy models (7 tables)
│       ├── crud.py         # Database operations
│       └── engine.py       # Async engine + session management
├── frontend/               # Modular web UI (HTML + JS modules + PWA)
├── tests/                  # 26 test modules, ~322 tests
├── alembic/                # Database migrations
├── infra/                  # Azure Bicep templates
├── scripts/                # Maintenance scripts
├── docker-compose.yml      # Local dev: app (8080) + PostgreSQL (5432)
├── Dockerfile              # Multi-stage build
├── azure.yaml              # Azure Developer CLI config
└── start.sh                # Container entrypoint
```

## Development

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ (Docker uses 3.12) |
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| Database | PostgreSQL 16 + pgvector |
| AI | Azure OpenAI (GPT-4o-mini, GPT-4o vision, text-embedding-3-small) |
| Auth | PyJWT + bcrypt |
| Email | Azure Communication Services |
| MCP | FastMCP (stdio transport) |
| Frontend | Tailwind CSS (CDN), vanilla JS (modular), PWA |
| Deployment | Azure Container Apps via `azd` (Bicep IaC) |
| Package Manager | uv |

### Database Migrations

```bash
uv run alembic revision --autogenerate -m "Description"
uv run alembic upgrade head
```

### Testing

```bash
# Full test suite
docker compose up -d
uv run python -m pytest tests/ -v --tb=short

# E2E tests
uv run python -m pytest tests/test_e2e.py -v -m e2e --no-cov
```

### Deploy to Azure

```bash
azd deploy
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Database connection errors | `docker compose ps` / `docker compose logs postgres` |
| Module import errors | `uv sync --reinstall` |
| Azure OpenAI 401 | Run `az login` to refresh `DefaultAzureCredential` |
| Migrations fail on Azure | Check `alembic/env.py` SSL translation (`ssl=require` ↔ `sslmode=require`) |

## License

MIT
