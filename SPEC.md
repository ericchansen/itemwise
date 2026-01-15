# Inventory Assistant - Functional Specification

## 1. Overview

The Inventory Assistant is an AI-powered system for managing chest freezer inventory through natural language interactions. It provides a Model Context Protocol (MCP) server that enables AI agents to perform inventory operations while maintaining a complete audit trail.

### Purpose
Enable users to track items in their chest freezer and interact with the inventory using natural language queries through AI assistants like Claude.

### Key Features
- Natural language inventory search using semantic similarity
- AI agent-driven CRUD operations via MCP server
- Complete transaction logging for audit and future approval workflows
- Local PostgreSQL database with vector search capabilities

## 2. Architecture

### Technology Stack
- **Backend Framework**: Python 3.11+ with FastMCP
- **Database**: PostgreSQL 16+ with pgvector extension
- **ORM**: SQLAlchemy 2.0 (async)
- **Package Manager**: uv
- **Database Migrations**: Alembic
- **Container Orchestration**: Docker Compose
- **MCP Protocol**: FastMCP framework

### System Components

```
┌─────────────────┐
│   AI Agent      │
│  (Claude, etc)  │
└────────┬────────┘
         │ MCP Protocol
         │
┌────────▼────────────────────┐
│   FastMCP Server            │
│   - add_item                │
│   - update_item             │
│   - remove_item             │
│   - list_items              │
│   - search_inventory        │
└────────┬────────────────────┘
         │
┌────────▼────────────────────┐
│   Business Logic Layer      │
│   - CRUD Operations         │
│   - Transaction Logging     │
│   - Embedding Generation    │
└────────┬────────────────────┘
         │
┌────────▼────────────────────┐
│   PostgreSQL Database       │
│   - inventory_items         │
│   - transaction_log         │
│   - pgvector extension      │
└─────────────────────────────┘
```

## 3. Database Schema

### 3.1 inventory_items Table

Stores all items in the freezer inventory.

| Column      | Type                | Constraints          | Description                        |
|-------------|---------------------|----------------------|------------------------------------|
| id          | INTEGER             | PRIMARY KEY          | Unique item identifier             |
| name        | VARCHAR             | NOT NULL, INDEX      | Item name                          |
| quantity    | INTEGER             | NOT NULL             | Number of items                    |
| category    | VARCHAR             | INDEX                | Category (meat, vegetables, etc.)  |
| description | TEXT                |                      | Optional detailed description      |
| embedding   | VECTOR(1536)        |                      | Semantic embedding for search      |
| created_at  | TIMESTAMP WITH TZ   | DEFAULT NOW()        | Record creation timestamp          |
| updated_at  | TIMESTAMP WITH TZ   | ON UPDATE            | Last modification timestamp        |

**Indexes:**
- Primary key on `id`
- Index on `name` for text searches
- Index on `category` for filtering
- Vector index on `embedding` for similarity search

### 3.2 transaction_log Table

Records all AI operations for audit trail and future approval workflows.

| Column     | Type                | Constraints    | Description                           |
|------------|---------------------|----------------|---------------------------------------|
| id         | INTEGER             | PRIMARY KEY    | Unique log identifier                 |
| operation  | VARCHAR             | NOT NULL       | Operation type (CREATE/UPDATE/DELETE) |
| item_id    | INTEGER             | NULLABLE       | Reference to inventory item           |
| data       | TEXT                |                | JSON data about the operation         |
| status     | VARCHAR             | NOT NULL       | PENDING/CONFIRMED/REJECTED            |
| timestamp  | TIMESTAMP WITH TZ   | DEFAULT NOW()  | When operation was logged             |

## 4. MCP Server Tools

The FastMCP server exposes the following tools to AI agents:

### 4.1 add_item
**Purpose**: Add a new item to the freezer inventory

**Parameters:**
- `name` (string, required): Name of the item
- `quantity` (integer, required): Number of items
- `category` (string, required): Category (e.g., "meat", "vegetables", "prepared")
- `description` (string, optional): Additional details

**Returns:**
```json
{
  "status": "success",
  "message": "Added [item] to inventory",
  "item_id": 123,
  "quantity": 5
}
```

### 4.2 update_item
**Purpose**: Update an existing inventory item

**Parameters:**
- `item_id` (integer, required): ID of the item to update
- `quantity` (integer, optional): New quantity
- `name` (string, optional): New name
- `category` (string, optional): New category
- `description` (string, optional): New description

**Returns:**
```json
{
  "status": "success",
  "message": "Updated [item]",
  "item": {
    "id": 123,
    "name": "Chicken Breast",
    "quantity": 8
  }
}
```

### 4.3 remove_item
**Purpose**: Remove an item from the inventory

**Parameters:**
- `item_id` (integer, required): ID of the item to remove

**Returns:**
```json
{
  "status": "success",
  "message": "Removed [item] from inventory"
}
```

### 4.4 list_items
**Purpose**: List all items or filter by category

**Parameters:**
- `category` (string, optional): Filter by category

**Returns:**
```json
{
  "status": "success",
  "count": 15,
  "items": [
    {
      "id": 123,
      "name": "Chicken Breast",
      "quantity": 8,
      "category": "meat",
      "description": "Organic chicken breast"
    }
  ]
}
```

### 4.5 search_inventory
**Purpose**: Search inventory using natural language

**Parameters:**
- `query` (string, required): Natural language search query

**Returns:**
```json
{
  "status": "success",
  "query": "do I have chicken?",
  "results": [
    {
      "id": 123,
      "name": "Chicken Breast",
      "quantity": 8,
      "category": "meat",
      "similarity_score": 0.92
    }
  ]
}
```

## 5. Data Flow

### 5.1 Adding an Item
1. AI agent calls `add_item` tool via MCP
2. FastMCP server receives request
3. Transaction logged to `transaction_log` with status PENDING
4. Generate embedding for item description
5. Create record in `inventory_items` table
6. Return success response to agent

### 5.2 Natural Language Search
1. AI agent calls `search_inventory` with natural language query
2. Generate embedding for search query
3. Use pgvector to find similar items by cosine similarity
4. Return ranked results to agent

### 5.3 Transaction Logging
All AI operations are logged to the `transaction_log` table. This provides:
- Complete audit trail of AI actions
- Foundation for future approval workflows
- Data for analyzing AI agent behavior
- Rollback capability (future feature)

## 6. Implementation Requirements

### 6.1 Python Package Dependencies
- `fastmcp>=0.2.0` - MCP server framework
- `sqlalchemy>=2.0.0` - Async ORM
- `asyncpg>=0.29.0` - PostgreSQL async driver
- `pgvector>=0.2.0` - Vector extension support
- `alembic>=1.13.0` - Database migrations
- `pydantic>=2.0.0` - Data validation
- `pydantic-settings>=2.0.0` - Settings management
- `python-dotenv>=1.0.0` - Environment variables
- `openai>=1.0.0` - Embeddings generation (optional)

### 6.2 Environment Configuration
- `POSTGRES_USER` - Database username
- `POSTGRES_PASSWORD` - Database password
- `POSTGRES_DB` - Database name
- `POSTGRES_HOST` - Database host
- `POSTGRES_PORT` - Database port
- `OPENAI_API_KEY` - For embedding generation (optional)

### 6.3 Docker Services
- PostgreSQL 16 with pgvector extension
- Volume mount for data persistence
- Port mapping for local access

## 7. Future Enhancements

### Phase 2 - Approval Workflow
- User confirmation before executing AI operations
- Pending transaction review interface
- Bulk approval/rejection capabilities

### Phase 3 - Advanced Features
- Expiration date tracking
- Low inventory alerts
- Recipe ingredient matching
- Shopping list generation from inventory gaps

### Phase 4 - Multi-User Support
- User authentication
- Per-user inventory separation
- Shared freezer management

## 8. Development Workflow

### 8.1 Database Migrations
Use Alembic for schema versioning:
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

### 8.2 Running the Server
```bash
# Start database
docker compose up -d

# Run MCP server
inventory-server

# Or with uv
uv run inventory-server
```

### 8.3 Testing with MCP Client
Configure in Claude Desktop or compatible MCP client:
```json
{
  "mcpServers": {
    "itemwise": {
      "command": "uv",
      "args": ["run", "inventory-server"],
      "cwd": "/path/to/itemwise"
    }
  }
}
```

## 9. Security Considerations

- Database credentials stored in `.env` (not committed to git)
- Input validation on all MCP tool parameters
- SQL injection prevention via SQLAlchemy parameterized queries
- Transaction logging for accountability
- Future: User authentication and authorization

## 10. Success Metrics

- AI agent successfully performs CRUD operations
- Natural language search returns relevant results
- All operations logged to transaction table
- Database queries complete in <100ms
- Zero data loss from AI operations
