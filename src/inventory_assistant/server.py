"""FastMCP server for inventory management."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .database.crud import (
    create_item,
    delete_item,
    get_item,
    list_items,
    log_transaction,
    search_items_by_text,
    update_item,
)
from .database.engine import AsyncSessionLocal, close_db, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Lifespan management for database connection
@asynccontextmanager
async def lifespan(app: Any) -> AsyncGenerator[None, None]:
    """Manage database lifecycle during server startup and shutdown."""
    logger.info("Starting Inventory Assistant MCP Server...")
    try:
        await init_db()
        logger.info("Database initialized successfully")
        yield
    finally:
        logger.info("Shutting down server...")
        await close_db()
        logger.info("Server shutdown complete")


# Initialize FastMCP server
mcp = FastMCP(
    name="itemwise",
)


@mcp.tool()  # type: ignore[misc]
async def add_item(
    name: str,
    quantity: int,
    category: str,
    description: str = "",
) -> dict[str, Any]:
    """Add a new item to the freezer inventory.

    Args:
        name: Name of the item (e.g., "Chicken Breast")
        quantity: Quantity or count of items
        category: Category such as "meat", "vegetables", "prepared", "dessert"
        description: Optional detailed description of the item

    Returns:
        Dictionary with status, message, item_id, and quantity
    """
    try:
        async with AsyncSessionLocal() as session:
            # Log the operation
            await log_transaction(
                session,
                operation="CREATE",
                item_id=None,
                data={
                    "name": name,
                    "quantity": quantity,
                    "category": category,
                    "description": description,
                },
            )

            # Create the item
            item = await create_item(
                session,
                name=name,
                quantity=quantity,
                category=category,
                description=description if description else None,
            )

            return {
                "status": "success",
                "message": f"Added {name} to inventory",
                "item_id": item.id,
                "quantity": item.quantity,
            }
    except Exception as e:
        logger.exception("Error adding item")
        raise ToolError(f"Failed to add item: {str(e)}")


@mcp.tool()  # type: ignore[misc]
async def update_item_tool(
    item_id: int,
    name: Optional[str] = None,
    quantity: Optional[int] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> dict[str, Any]:
    """Update an existing inventory item.

    Args:
        item_id: ID of the item to update
        name: New name for the item (optional)
        quantity: New quantity (optional)
        category: New category (optional)
        description: New description (optional)

    Returns:
        Dictionary with status, message, and updated item details
    """
    try:
        async with AsyncSessionLocal() as session:
            # Check if item exists
            existing_item = await get_item(session, item_id)
            if not existing_item:
                raise ToolError(f"Item with ID {item_id} not found")

            # Log the operation
            await log_transaction(
                session,
                operation="UPDATE",
                item_id=item_id,
                data={
                    "name": name,
                    "quantity": quantity,
                    "category": category,
                    "description": description,
                },
            )

            # Update the item
            updated_item = await update_item(
                session,
                item_id=item_id,
                name=name,
                quantity=quantity,
                category=category,
                description=description,
            )

            if not updated_item:
                raise ToolError(f"Item with ID {item_id} not found")

            return {
                "status": "success",
                "message": f"Updated {updated_item.name}",
                "item": {
                    "id": updated_item.id,
                    "name": updated_item.name,
                    "quantity": updated_item.quantity,
                    "category": updated_item.category,
                    "description": updated_item.description,
                },
            }
    except ToolError:
        raise
    except Exception as e:
        logger.exception("Error updating item")
        raise ToolError(f"Failed to update item: {str(e)}")


@mcp.tool()  # type: ignore[misc]
async def remove_item(item_id: int) -> dict[str, Any]:
    """Remove an item from the inventory.

    Args:
        item_id: ID of the item to remove

    Returns:
        Dictionary with status and confirmation message
    """
    try:
        async with AsyncSessionLocal() as session:
            # Check if item exists
            item = await get_item(session, item_id)
            if not item:
                raise ToolError(f"Item with ID {item_id} not found")

            item_name = item.name

            # Log the operation
            await log_transaction(
                session,
                operation="DELETE",
                item_id=item_id,
                data={"name": item_name},
            )

            # Delete the item
            deleted = await delete_item(session, item_id)

            if deleted:
                return {
                    "status": "success",
                    "message": f"Removed {item_name} from inventory",
                }
            else:
                raise ToolError(f"Failed to delete item {item_id}")
    except ToolError:
        raise
    except Exception as e:
        logger.exception("Error removing item")
        raise ToolError(f"Failed to remove item: {str(e)}")


@mcp.tool()  # type: ignore[misc]
async def list_inventory(category: Optional[str] = None) -> dict[str, Any]:
    """List all items in the inventory or filter by category.

    Args:
        category: Optional category filter (e.g., "meat", "vegetables")

    Returns:
        Dictionary with status, count, and list of items
    """
    try:
        async with AsyncSessionLocal() as session:
            items = await list_items(session, category=category)

            return {
                "status": "success",
                "count": len(items),
                "category": category if category else "all",
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "quantity": item.quantity,
                        "category": item.category,
                        "description": item.description,
                        "created_at": (
                            item.created_at.isoformat() if item.created_at else None
                        ),
                    }
                    for item in items
                ],
            }
    except Exception as e:
        logger.exception("Error listing items")
        raise ToolError(f"Failed to list items: {str(e)}")


@mcp.tool()  # type: ignore[misc]
async def search_inventory(query: str) -> dict[str, Any]:
    """Search inventory using natural language or keywords.

    This performs a text-based search on item names. For semantic search
    with embeddings, items need to have embedding vectors generated.

    Args:
        query: Search query (e.g., "chicken", "frozen vegetables")

    Returns:
        Dictionary with status, query, and matching items
    """
    try:
        async with AsyncSessionLocal() as session:
            # Log the search operation
            await log_transaction(
                session,
                operation="SEARCH",
                data={"query": query},
            )

            # Perform text search
            items = await search_items_by_text(session, query)

            return {
                "status": "success",
                "query": query,
                "count": len(items),
                "results": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "quantity": item.quantity,
                        "category": item.category,
                        "description": item.description,
                    }
                    for item in items
                ],
            }
    except Exception as e:
        logger.exception("Error searching inventory")
        raise ToolError(f"Failed to search inventory: {str(e)}")


def main() -> None:
    """Entry point for the MCP server."""
    logger.info("Initializing Inventory Assistant MCP Server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
