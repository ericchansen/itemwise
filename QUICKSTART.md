# Quick Start Guide

Get Itemwise running locally in under 5 minutes.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Docker](https://www.docker.com/) (for PostgreSQL + pgvector)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (optional, for Azure OpenAI features)

## 1. Install Dependencies

```bash
git clone https://github.com/ericchansen/itemwise.git
cd itemwise
uv sync
```

## 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` if you want to enable Azure OpenAI (chat + semantic search):

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
```

Then authenticate:
```bash
az login
```

> **Without Azure OpenAI**, the app still works — chat uses basic pattern matching and search uses exact matching instead of semantic vectors.

## 3. Start the Database

```bash
docker compose up -d
```

Wait for it to be healthy:
```bash
docker compose ps   # Should show "healthy"
```

## 4. Run Migrations

```bash
uv run alembic upgrade head
```

## 5. Start the App

**Web UI** (recommended):
```bash
uv run itemwise-web
# Open http://localhost:8000
```

**MCP Server** (for Claude Desktop / AI agents):
```bash
uv run itemwise-server
```

## Connect to Claude Desktop

Add to your Claude Desktop config:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "itemwise": {
      "command": "uv",
      "args": ["--directory", "/path/to/itemwise", "run", "itemwise-server"]
    }
  }
}
```

Update the path to your clone location, then restart Claude Desktop.

## Try It Out

In the web UI chat or Claude Desktop:

- "I just bought 5 bags of frozen vegetables and put them in the freezer"
- "I used 2 of the AA batteries from the garage"
- "What meat do I have in the freezer?"
- "Show me everything in the garage"

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Database won't start | `docker compose logs postgres` |
| Import errors | `uv sync --reinstall` |
| MCP not appearing in Claude | Check config path, restart Claude Desktop |
| Chat returns generic responses | Set `AZURE_OPENAI_ENDPOINT` and run `az login` |

### View database directly

```bash
docker exec -it itemwise-db psql -U postgres -d inventory
```

```sql
SELECT name, quantity, category, location_name FROM inventory_items LIMIT 10;
SELECT name FROM locations;
```
