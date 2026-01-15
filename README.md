# Inventory Assistant

AI-powered freezer inventory management with natural language search capabilities. Built with FastMCP to enable AI agents like Claude to manage your inventory through conversational interfaces.

## Features

- 🤖 **MCP Server Integration** - Expose inventory operations to AI agents via Model Context Protocol
- 🔍 **Natural Language Search** - Query your inventory using semantic search powered by pgvector
- 📝 **Complete Audit Trail** - All AI operations logged to transaction table for tracking
- 🗄️ **PostgreSQL Backend** - Robust database with vector extension for semantic capabilities
- ⚡ **Async Operations** - Built with SQLAlchemy async for high performance
- 🔄 **Database Migrations** - Alembic integration for schema versioning

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) - Fast Python package manager

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

### 4. Run MCP Server

```bash
# Start the server
uv run inventory-server

# Or during development
uv run python -m itemwise.server
```

## Configuration

Edit `.env` file to customize database connection:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=inventory
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DEBUG=false
```

## MCP Client Configuration

### Claude Desktop

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "itemwise": {
      "command": "uv",
      "args": ["run", "inventory-server"],
      "cwd": "C:\\Users\\YourName\\repos\\itemwise"
    }
  }
}
```

After configuration, restart Claude Desktop.

## Available Tools

The MCP server exposes the following tools to AI agents:

### `add_item`
Add a new item to the freezer inventory.

```python
add_item(
    name="Chicken Breast",
    quantity=5,
    category="meat",
    description="Organic boneless chicken breast"
)
```

### `update_item_tool`
Update an existing inventory item.

```python
update_item_tool(
    item_id=1,
    quantity=3,  # Optional: update quantity
    name="New Name",  # Optional: update name
)
```

### `remove_item`
Remove an item from inventory.

```python
remove_item(item_id=1)
```

### `list_inventory`
List all items or filter by category.

```python
list_inventory()  # All items
list_inventory(category="meat")  # Filter by category
```

### `search_inventory`
Search inventory using natural language.

```python
search_inventory(query="chicken")
```

## Usage Examples

Once configured with Claude Desktop, you can interact naturally:

```
You: What's in my freezer?
Claude: [calls list_inventory()]

You: Add 3 packages of ground beef to the inventory
Claude: [calls add_item(name="Ground Beef", quantity=3, category="meat")]

You: Do I have any chicken?
Claude: [calls search_inventory(query="chicken")]

You: Remove the item with ID 5
Claude: [calls remove_item(item_id=5)]
```

## Development

### Project Structure

```
itemwise/
├── src/
│   └── itemwise/
│       ├── __init__.py
│       ├── config.py           # Settings and configuration
│       ├── server.py            # FastMCP server and tools
│       └── database/
│           ├── __init__.py
│           ├── models.py        # SQLAlchemy models
│           ├── engine.py        # Database connection
│           └── crud.py          # CRUD operations
├── alembic/                     # Database migrations
├── docker-compose.yml           # PostgreSQL setup
├── pyproject.toml              # Python dependencies
└── .env                        # Environment variables
```

### Database Migrations

Create a new migration after model changes:

```bash
uv run alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Rollback one version:

```bash
uv run alembic downgrade -1
```

### Testing

```bash
# Install dev dependencies
uv sync --dev

# Run tests (when available)
uv run pytest
```

## Database Schema

### inventory_items

| Column      | Type          | Description                        |
|-------------|---------------|------------------------------------|
| id          | INTEGER       | Primary key                        |
| name        | VARCHAR       | Item name                          |
| quantity    | INTEGER       | Number of items                    |
| category    | VARCHAR       | Category (meat, vegetables, etc.)  |
| description | TEXT          | Optional description               |
| embedding   | VECTOR(1536)  | Semantic search vector             |
| created_at  | TIMESTAMP     | Creation timestamp                 |
| updated_at  | TIMESTAMP     | Last update timestamp              |

### transaction_log

| Column     | Type       | Description                    |
|------------|------------|--------------------------------|
| id         | INTEGER    | Primary key                    |
| operation  | VARCHAR    | Operation type (CREATE/UPDATE) |
| item_id    | INTEGER    | Reference to inventory item    |
| data       | TEXT       | JSON operation data            |
| status     | VARCHAR    | PENDING/CONFIRMED/REJECTED     |
| timestamp  | TIMESTAMP  | Operation timestamp            |

## Troubleshooting

### Database connection errors

Ensure PostgreSQL is running:
```bash
docker compose ps
docker compose logs postgres
```

### Module import errors

Reinstall dependencies:
```bash
uv sync --reinstall
```

### MCP server not appearing in Claude

1. Check configuration file path
2. Verify `cwd` path is correct
3. Restart Claude Desktop completely
4. Check Claude Desktop logs for errors

## Future Enhancements

See [functional-spec.md](functional-spec.md) for planned features:

- User approval workflow for AI operations
- Expiration date tracking
- Low inventory alerts
- Recipe ingredient matching
- OpenAI embeddings for enhanced semantic search

## License

MIT

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.
