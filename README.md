# Itemwise

AI-powered inventory management with natural language search. Track items across multiple locations (freezer, garage, pantry, battery bin - anywhere!) using conversational interfaces.

Built with FastMCP to enable AI agents like Claude to manage your inventory, plus a web UI for easy demos. **Now with Azure OpenAI integration for intelligent natural language understanding!**

## Features

- 🏠 **Multi-Location Support** - Track items in any location: freezer, garage, closet, tool shed, etc.
- 🤖 **MCP Server Integration** - Expose inventory operations to AI agents via Model Context Protocol
- 🧠 **Azure OpenAI Powered** - Natural language chat that understands "I put 3 bags of chicken in the freezer"
- 🔍 **Semantic Search** - Natural language search powered by Azure OpenAI embeddings and pgvector
- 🌐 **Web Interface** - Responsive chat UI that works on desktop and mobile
- 📝 **Complete Audit Trail** - All operations logged for tracking
- 🗄️ **PostgreSQL Backend** - Robust database with vector extension for semantic capabilities
- ⚡ **Async Operations** - Built with SQLAlchemy async for high performance

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd itemwise

# Copy environment template
cp .env.example .env

# Install dependencies
uv sync
```

### 2. Start Database

```bash
# Start PostgreSQL with pgvector extension
docker compose up -d

# Wait for database to be ready
docker compose ps
```

### 3. Initialize Database

```bash
# Run migrations to create tables
uv run alembic upgrade head
```

### 4. Configure Azure OpenAI (Optional but Recommended)

For full natural language understanding (adding/removing items via chat), configure Azure OpenAI:

```env
# Add to your .env file
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini  # or your deployed model name
```

The app uses Azure AD authentication via `DefaultAzureCredential`, so make sure you're logged in:
```bash
az login
```

Without Azure OpenAI, the chat will work in fallback mode with basic pattern matching.

### 5. Run the Application

**Option A: Web Interface (Recommended for demos)**
```bash
# Start the web server
uv run itemwise-web

# Open http://localhost:8080 in your browser
```

**Option B: MCP Server (For AI agents like Claude)**
```bash
# Start the MCP server
uv run itemwise-server
```

## Web Interface

The web UI provides:
- **Chat tab**: Natural language interaction with your inventory
- **Inventory tab**: Browse, search, and manage items with filters

With Azure OpenAI enabled, try:
- "I just bought 5 bags of frozen vegetables and put them in the freezer"
- "I used 2 of the AA batteries from the garage"
- "What meat do I have in the freezer?"
- "Do I have any batteries?"
- "Show me everything in the garage"

The AI understands context and will automatically:
- Add items with appropriate categories when you mention buying/storing things
- Remove or reduce quantities when you mention using items
- Search and list items when you ask about what you have

## MCP Client Configuration

### Claude Desktop

Add to your Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

## Available MCP Tools

### `add_item`
Add a new item to any location.

```
"Add 3 chicken breasts to the freezer"
"Put 8 AAA batteries in the battery bin"
"Store a hammer in the garage"
```

### `list_inventory`
List items filtered by category or location.

```
"What's in the freezer?"
"Show me all the meat"
"What electronics do I have?"
```

### `search_inventory`
Natural language search across all items.

```
"Do I have any chicken?"
"Find batteries"
"Something to grill"
```

### `add_location`
Create a new storage location.

```
"Create a location called Tool Shed"
```

### `get_locations`
List all available storage locations.

### `update_item_tool`
Update an existing item's details.

### `remove_item`
Remove an item from inventory.

## REST API

The web server also exposes a REST API:

- `GET /api/items` - List items (with optional `category` and `location` filters)
- `POST /api/items` - Add a new item
- `GET /api/items/{id}` - Get single item
- `PUT /api/items/{id}` - Update item
- `DELETE /api/items/{id}` - Delete item
- `GET /api/search?q=query` - Search items
- `GET /api/locations` - List locations
- `POST /api/locations` - Create location
- `POST /api/chat` - AI-powered chat endpoint (requires Azure OpenAI for full functionality)

API docs available at `http://localhost:8080/docs`

## Configuration

Edit `.env` file:

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=inventory
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Application
DEBUG=false
ENV=production  # or 'development'

# Security - REQUIRED for production
# Generate a secure key:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=your-secure-random-key-here

# Azure OpenAI (optional - enables intelligent chat + semantic search)
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
```

### Security Note

The `SECRET_KEY` (or `JWT_SECRET_KEY`) environment variable is **required** when:
- `DEBUG=false` (default), or
- `ENV=production` or `ENV=prod`

The application will raise an error on startup if SECRET_KEY is not set in production environments. Generate a secure key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Development

### Project Structure

```
itemwise/
├── src/itemwise/
│   ├── server.py        # MCP server and tools
│   ├── api.py           # FastAPI REST API
│   ├── ai_client.py     # Azure OpenAI integration
│   ├── auth.py          # Authentication & security
│   ├── embeddings.py    # Semantic search embeddings
│   ├── config.py        # Settings
│   └── database/
│       ├── models.py    # SQLAlchemy models
│       ├── crud.py      # Database operations
│       └── engine.py    # Connection management
├── frontend/
│   └── index.html       # Web UI
├── alembic/             # Database migrations
├── tests/               # Test suite
└── docker-compose.yml   # PostgreSQL setup
```

### Database Migrations

```bash
# Create new migration
uv run alembic revision --autogenerate -m "Description"

# Apply migrations
uv run alembic upgrade head
```

### Testing

```bash
uv run pytest
```

## Troubleshooting

### Database connection errors
```bash
docker compose ps
docker compose logs postgres
```

### Module import errors
```bash
uv sync --reinstall
```

## License

MIT
