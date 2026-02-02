# Quick Start Guide

## ✅ System Status

All components are now set up and working:

- ✅ PostgreSQL database with pgvector running
- ✅ Database tables created (inventory_items, transaction_log)
- ✅ Test data added successfully
- ✅ FastMCP server ready

## Next Steps: Connect to Claude Desktop

### 1. Find Your Claude Desktop Config

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

### 2. Add This Configuration

Open the config file and add:

```json
{
  "mcpServers": {
    "itemwise": {
      "command": "uv",
      "args": ["--directory", "C:\\Users\\erichansen\\repos\\itemwise", "run", "itemwise-server"],
      "env": {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
        "POSTGRES_DB": "inventory"
      }
    }
  }
}
```

**Important:** Update the path `C:\\Users\\erichansen\\repos\\itemwise` if your project is in a different location.

### 3. Restart Claude Desktop

Close and reopen Claude Desktop completely.

### 4. Test It Out!

Try these prompts in Claude:

```
"What's in my freezer inventory?"
```

```
"Add 3 packages of ground beef to my freezer"
```

```
"Do I have any chicken?"
```

```
"Show me all my vegetables"
```

## Available MCP Tools

Claude will have access to these tools:

- **add_item** - Add new items to inventory
- **update_item_tool** - Update existing items
- **remove_item** - Remove items
- **list_inventory** - List all items or filter by category
- **search_inventory** - Natural language search

## Troubleshooting

### MCP server not appearing
1. Check the config file path is correct
2. Verify the project directory path uses double backslashes `\\`
3. Ensure database is running: `docker compose ps`
4. Check Claude Desktop Developer Tools (Ctrl+Shift+I on Windows)

### Database errors
```bash
# Restart database
docker compose restart

# Check database logs
docker compose logs postgres
```

### Test the server manually
```bash
# This should start the server in stdio mode
uv run itemwise-server
```

## Managing the Database

### Stop database
```bash
docker compose down
```

### Start database
```bash
docker compose up -d
```

### View database directly
```bash
docker exec -it itemwise-db psql -U postgres -d inventory
```

Then run SQL:
```sql
SELECT * FROM inventory_items;
SELECT * FROM transaction_log;
```

## Current Inventory

You already have 2 test items:
- Chicken Breast: 5 (meat)
- Frozen Peas: 3 (vegetables)

Enjoy your AI-powered freezer inventory system! 🎉
