# Itemwise — Functional Specification

## 1. Overview

Itemwise is an AI-powered inventory management application. Users interact with their inventory through **natural language chat** (powered by Azure OpenAI) or a **traditional CRUD UI**. Items are organized into shared inventories with named storage locations and tracked with lot-level granularity.

### Key Capabilities

- **AI Chat** — "Add 2 frozen pizzas to the chest freezer" is parsed, executed, and confirmed automatically
- **Semantic Search** — pgvector embeddings let users find items by meaning, not just keywords
- **Multi-Inventory Sharing** — invite other users by email; members see the same items
- **Lot Tracking** — FIFO batch tracking records when each quantity was added and by whom
- **MCP Server** — a secondary Model Context Protocol interface for AI agents (Claude Desktop, etc.)
- **Web Frontend** — single-page dark-themed UI with Chat, Items, and Settings tabs

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Single-file HTML + Tailwind CSS)                      │
│  Tabs: Chat │ Items │ Settings                                   │
└────────────────────────┬─────────────────────────────────────────┘
                         │ REST / JSON
┌────────────────────────▼─────────────────────────────────────────┐
│  FastAPI Application (src/itemwise/api.py)                        │
│  ┌──────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────────┐  │
│  │ Auth     │ │ Items     │ │ Locations │ │ Inventories      │  │
│  │ (JWT)    │ │ CRUD+Lots │ │ CRUD      │ │ Members/Sharing  │  │
│  └──────────┘ └───────────┘ └───────────┘ └──────────────────┘  │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐  │
│  │ /api/chat endpoint   │──│ AI Client (ai_client.py)         │  │
│  │                      │  │  → Azure OpenAI GPT-4o-mini      │  │
│  │                      │  │  → Tool calling (multi-pass)     │  │
│  └──────────────────────┘  └──────────────────────────────────┘  │
└────────────────────────┬─────────────────────────────────────────┘
                         │ SQLAlchemy 2.0 (async) + asyncpg
┌────────────────────────▼─────────────────────────────────────────┐
│  PostgreSQL 16 + pgvector                                        │
│  Tables: users, inventories, inventory_members, locations,       │
│          inventory_items, item_lots, transaction_log             │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  FastMCP Server (src/itemwise/server.py) — stdio transport       │
│  Secondary interface for Claude Desktop / MCP clients            │
└──────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 + pgvector |
| AI | Azure OpenAI (GPT-4o-mini chat, text-embedding-3-small embeddings) |
| Auth | JWT (HS256) + bcrypt |
| Email | Azure Communication Services |
| MCP | FastMCP (stdio transport) |
| Migrations | Alembic |
| Package Manager | uv |
| Frontend | Single-file HTML, Tailwind CSS, vanilla JS |
| Deployment | Azure Container Apps + Azure Database for PostgreSQL Flexible Server |
| IaC | Bicep (infra/) |

## 3. Database Schema

Seven tables managed by SQLAlchemy models in `src/itemwise/database/models.py`.

### 3.1 users

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, indexed | User ID |
| email | VARCHAR | UNIQUE, NOT NULL, indexed | Login email |
| hashed_password | VARCHAR | NOT NULL | bcrypt hash |
| created_at | TIMESTAMPTZ | DEFAULT now() | Registration time |

### 3.2 inventories

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, indexed | Inventory ID |
| name | VARCHAR | NOT NULL | Display name (e.g. "Home") |
| created_at | TIMESTAMPTZ | DEFAULT now() | Creation time |

### 3.3 inventory_members

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, indexed | Row ID |
| inventory_id | INTEGER | FK → inventories, NOT NULL, indexed | Inventory |
| user_id | INTEGER | FK → users, NOT NULL, indexed | Member |
| joined_at | TIMESTAMPTZ | DEFAULT now() | Join time |

**Unique constraint:** `(inventory_id, user_id)` — a user can belong to an inventory only once.

### 3.4 locations

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, indexed | Location ID |
| inventory_id | INTEGER | FK → inventories, NOT NULL, indexed | Owning inventory |
| name | VARCHAR | NOT NULL, indexed | Display name ("Tim's Pocket") |
| normalized_name | VARCHAR | NOT NULL, indexed | Lowercase for matching ("tims pocket") |
| description | TEXT | nullable | Optional notes |
| embedding | VECTOR(1536) | nullable | Semantic embedding |
| created_at | TIMESTAMPTZ | DEFAULT now() | Creation time |

**Unique constraint:** `(inventory_id, normalized_name)` — no duplicate location names within an inventory.

### 3.5 inventory_items

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, indexed | Item ID |
| name | VARCHAR | NOT NULL, indexed | Item name |
| quantity | INTEGER | NOT NULL | Total quantity (sum of lots) |
| category | VARCHAR | indexed | Category (meat, electronics, etc.) |
| description | TEXT | nullable | Optional details |
| location_id | INTEGER | FK → locations, nullable, indexed | Storage location |
| inventory_id | INTEGER | FK → inventories, NOT NULL, indexed | Owning inventory |
| embedding | VECTOR(1536) | nullable | Semantic embedding |
| created_at | TIMESTAMPTZ | DEFAULT now() | Creation time |
| updated_at | TIMESTAMPTZ | ON UPDATE | Last modification |

### 3.6 item_lots

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, indexed | Lot ID |
| item_id | INTEGER | FK → inventory_items (CASCADE), NOT NULL, indexed | Parent item |
| quantity | INTEGER | NOT NULL | Lot quantity |
| added_at | TIMESTAMPTZ | DEFAULT now(), indexed | When this lot was added |
| added_by_user_id | INTEGER | FK → users (SET NULL), nullable | Who added it |
| notes | TEXT | nullable | Lot-specific notes |

### 3.7 transaction_log

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK | Log ID |
| operation | VARCHAR | NOT NULL | CREATE / UPDATE / DELETE / SEARCH |
| item_id | INTEGER | nullable | Related item |
| data | TEXT | nullable | JSON payload |
| status | VARCHAR | NOT NULL, default "PENDING" | Operation status |
| timestamp | TIMESTAMPTZ | DEFAULT now() | When logged |

## 4. API Endpoints

All endpoints are defined in `src/itemwise/api.py`. Auth-protected routes require a Bearer JWT.

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Create account (JSON body with email + password) |
| POST | `/api/auth/login` | — | Login (**form-encoded**, OAuth2PasswordRequestForm) |
| POST | `/api/auth/refresh` | — | Exchange refresh token for new access token |
| GET | `/api/auth/me` | ✓ | Get current user info |
| PUT | `/api/auth/password` | ✓ | Change password |

### Items

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/items` | ✓ | List items (optional `category`, `location` query params) |
| POST | `/api/items` | ✓ | Create item (creates lot automatically) |
| GET | `/api/items/{item_id}` | ✓ | Get single item with lots |
| PUT | `/api/items/{item_id}` | ✓ | Update item fields |
| DELETE | `/api/items/{item_id}` | ✓ | Delete item and all lots |

### Search

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/search` | ✓ | Semantic + text search (`q` query param) |

### Locations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/locations` | ✓ | List all locations in active inventory |
| POST | `/api/locations` | ✓ | Create a new location |

### Inventories & Sharing

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/inventories` | ✓ | List inventories the user belongs to |
| GET | `/api/inventories/{id}/members` | ✓ | List members of an inventory |
| POST | `/api/inventories/{id}/members` | ✓ | Add member by email (sends email invitation) |
| DELETE | `/api/inventories/{id}/members/{uid}` | ✓ | Remove a member |

### Chat

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/chat` | ✓ | Send natural language message, get AI response |

### Other

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Health check (returns `{"status": "healthy"}`) |
| GET | `/` | — | Serve frontend (`frontend/index.html`) |

## 5. AI System

### Chat Flow

1. User sends a message to `POST /api/chat`
2. The API builds a message array: **system prompt** + **user message**
3. Azure OpenAI (`GPT-4o-mini` deployment) is called with tool definitions
4. If the model returns tool calls, each tool is executed against the database
5. Tool results are appended and the model is called again (up to 5 iterations)
6. The final text response is returned to the user

### AI Tools (defined in `ai_client.py`)

| Tool | Description |
|------|-------------|
| `add_item` | Add item with name, quantity, category, location, description |
| `remove_item` | Remove item or reduce quantity (supports lot_id targeting) |
| `search_items` | Semantic search with optional location filter |
| `list_items` | List items filtered by location and/or category |
| `list_locations` | List all storage locations |
| `get_oldest_items` | Find oldest items by lot date (FIFO) |

### System Prompt

The system prompt instructs the model to act as an inventory assistant — extracting item details from natural language, using FIFO for removals, suggesting recipes based on inventory, and confirming actions conversationally. It is loaded from `src/itemwise/prompts/system.txt` if present, otherwise falls back to the default in `ai_client.py`.

### Fallback Mode

When Azure OpenAI is not configured, the chat endpoint uses keyword-based pattern matching to handle basic add/remove/search/list operations without AI.

## 6. Semantic Search

- **Model:** Azure OpenAI `text-embedding-3-small` (1536 dimensions)
- **Storage:** pgvector `VECTOR(1536)` columns on `inventory_items` and `locations`
- **Indexing:** Embeddings are generated on item create/update
- **Search:** Query text is embedded, then compared via L2 distance; results are ranked by similarity score (1 − distance/2)
- **Hybrid:** Semantic results are merged with text-based (`ILIKE`) results to maximize recall

## 7. Multi-Inventory & Sharing

- On registration, each user gets a default inventory (named `"{email}'s Inventory"`)
- Users can belong to multiple inventories via the `inventory_members` join table
- The active inventory is selected via `X-Inventory-Id` header (defaults to the first inventory)
- **Adding a member:** `POST /api/inventories/{id}/members` with `{"email": "..."}`:
  - If the email belongs to an existing user → adds them immediately, sends notification email
  - If not registered → sends a signup invitation email via Azure Communication Services
- All item and location operations are scoped to the active inventory

## 8. Lot Tracking

Each item's quantity is backed by one or more **lots** (batches):

- When an item is created via chat or API, an `ItemLot` records the quantity, timestamp, and who added it
- **Removal is FIFO** — the AI removes from the oldest lot first
- `get_oldest_items` returns items sorted by their earliest lot date
- The item's `quantity` field is the authoritative total; lot quantities sum to match it

## 9. Authentication

- **Password hashing:** bcrypt with automatic salt generation
- **Password policy:** ≥ 8 chars, uppercase, lowercase, digit, special character
- **Tokens:** JWT (HS256) with separate access (1 hour) and refresh (7 day) tokens
- **Login format:** `application/x-www-form-urlencoded` (OAuth2PasswordRequestForm) — not JSON
- **Secret key:** `JWT_SECRET_KEY` or `SECRET_KEY` env var; raises error if default is used in production
- **Timing attack prevention:** constant-time comparison with dummy hash for non-existent users

## 10. Email

Invitation and notification emails are sent via **Azure Communication Services**.

| Function | Trigger |
|----------|---------|
| `send_invite_email` | Adding a non-registered email as inventory member |
| `send_added_email` | Adding a registered user to an inventory |

**Configuration:** `AZURE_COMMUNICATION_CONNECTION_STRING` and `AZURE_COMMUNICATION_SENDER` environment variables. Email is best-effort; failures are logged but do not block the API response.

## 11. Deployment

### Azure Infrastructure (Bicep in `infra/`)

| Resource | Purpose |
|----------|---------|
| Azure Container Apps | Hosts the FastAPI application |
| Azure Database for PostgreSQL Flexible Server | Primary database with pgvector |
| Azure OpenAI | Chat completions and embedding generation |
| Azure Communication Services | Transactional email |
| Azure Container Registry | Docker image storage |

### Deployment Workflow

```bash
# Deploy application (uses Azure Developer CLI)
azd deploy

# Full provision + deploy
azd up
```

The `Dockerfile` builds the Python application with `uv` and serves via Uvicorn. Database migrations run on startup via Alembic (`alembic upgrade head`). SSL is enforced for Azure PostgreSQL connections (`?ssl=require` for asyncpg).

## 12. Frontend

A single-file HTML application served from `frontend/index.html` at the root URL (`/`).

### Design

- **Tailwind CSS** via CDN with a dark theme (`bg-neutral-950`)
- **Tabs:** Chat, Items, Settings
- **Responsive:** works on mobile and desktop

### Features

- **Chat tab** — conversational interface; sends messages to `/api/chat`
- **Items tab** — table of all items with inline CRUD; location and category filters
- **Settings tab** — inventory sharing (add/remove members), password change, active inventory selector
- **Auth** — login/register forms with JWT stored in `localStorage`; auto-refresh on 401

## 13. MCP Server

The FastMCP server (`src/itemwise/server.py`) provides a **stdio-transport** MCP interface for AI agents like Claude Desktop.

### Tools

| Tool | Description |
|------|-------------|
| `add_item` | Add item to inventory with location |
| `update_item_tool` | Update item fields |
| `remove_item` | Delete an item |
| `list_inventory` | List items with optional category/location filter |
| `search_inventory` | Semantic + text search |
| `add_location` | Create a new storage location |
| `get_locations` | List all locations |
| `get_oldest_items_tool` | Find oldest items by lot date |

### Configuration

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

The MCP server uses a default `mcp-user@local` user context and operates on that user's default inventory.

## 14. Development

### Running Locally

```bash
# Start database + app
docker compose up -d

# Or run outside Docker
uv run uvicorn src.itemwise.api:app --host 0.0.0.0 --port 8080

# Run MCP server
uv run itemwise-server
```

### Database Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Testing

```bash
# Unit tests
uv run python -m pytest tests/ -v --tb=short

# E2E tests (requires running app on port 8080)
uv run python -m pytest tests/test_e2e.py -v -m e2e --no-cov
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_USER` | Yes | Database username |
| `POSTGRES_PASSWORD` | Yes | Database password |
| `POSTGRES_DB` | Yes | Database name |
| `POSTGRES_HOST` | Yes | Database host |
| `POSTGRES_PORT` | Yes | Database port |
| `JWT_SECRET_KEY` | Prod | JWT signing key |
| `AZURE_OPENAI_ENDPOINT` | For chat | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | For chat | Chat model deployment name |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | For search | Embedding model deployment name |
| `AZURE_COMMUNICATION_CONNECTION_STRING` | For email | ACS connection string |
| `AZURE_COMMUNICATION_SENDER` | For email | Sender email address |
