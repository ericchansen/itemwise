"""FastMCP server for inventory management."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .database.crud import (
    create_item,
    create_location,
    delete_item,
    get_item,
    get_or_create_location,
    list_items,
    list_locations,
    log_transaction,
    search_items_by_embedding,
    search_items_by_text,
    update_item,
)
from .database.engine import AsyncSessionLocal, close_db, init_db
from .embeddings import generate_embedding

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _get_item_text_for_embedding(name: str, description: Optional[str] = None, category: Optional[str] = None) -> str:
    """Build text representation of item for embedding generation."""
    parts = [name]
    if category:
        parts.append(f"category: {category}")
    if description:
        parts.append(description)
    return " | ".join(parts)


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
    location: str = "",
    description: str = "",
) -> dict[str, Any]:
    """Add a new item to inventory at a specific location.

    Use this tool when the user wants to add or store something. The location
    can be any storage place like "freezer", "garage", "pantry", "battery bin",
    "closet", "toolbox", etc.

    Args:
        name: Name of the item (e.g., "Chicken Breast", "AAA Batteries", "Hammer")
        quantity: Quantity or count of items
        category: Category such as "meat", "vegetables", "electronics", "tools"
        location: Storage location (e.g., "Freezer", "Garage", "Battery Bin"). If not specified, item is stored without location.
        description: Optional detailed description of the item

    Returns:
        Dictionary with status, message, item_id, and location info

    Examples:
        - "Add 3 chicken breasts to the freezer" -> add_item("Chicken Breast", 3, "meat", "Freezer")
        - "Put 8 AAA batteries in the battery bin" -> add_item("AAA Batteries", 8, "electronics", "Battery Bin")
        - "Store a hammer in the garage" -> add_item("Hammer", 1, "tools", "Garage")
    """
    try:
        async with AsyncSessionLocal() as session:
            # Get or create location if specified
            location_id = None
            location_name = None
            if location:
                loc = await get_or_create_location(session, location.strip())
                location_id = loc.id
                location_name = loc.name

            # Generate embedding for semantic search
            item_text = _get_item_text_for_embedding(name, description, category)
            embedding = generate_embedding(item_text)

            # Log the operation
            await log_transaction(
                session,
                operation="CREATE",
                item_id=None,
                data={
                    "name": name,
                    "quantity": quantity,
                    "category": category,
                    "location": location_name,
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
                location_id=location_id,
                embedding=embedding,
            )

            return {
                "status": "success",
                "message": f"Added {quantity} {name} to {location_name or 'inventory'}",
                "item_id": item.id,
                "quantity": item.quantity,
                "location": location_name,
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
    location: Optional[str] = None,
    description: Optional[str] = None,
) -> dict[str, Any]:
    """Update an existing inventory item.

    Args:
        item_id: ID of the item to update
        name: New name for the item (optional)
        quantity: New quantity (optional)
        category: New category (optional)
        location: New storage location (optional)
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

            # Handle location update
            location_id = None
            location_name = None
            if location is not None:
                if location:
                    loc = await get_or_create_location(session, location.strip())
                    location_id = loc.id
                    location_name = loc.name

            # Generate new embedding if name or description changed
            embedding = None
            if name is not None or description is not None or category is not None:
                new_name = name if name is not None else existing_item.name
                new_desc = description if description is not None else existing_item.description
                new_cat = category if category is not None else existing_item.category
                item_text = _get_item_text_for_embedding(new_name, new_desc, new_cat)
                embedding = generate_embedding(item_text)

            # Log the operation
            await log_transaction(
                session,
                operation="UPDATE",
                item_id=item_id,
                data={
                    "name": name,
                    "quantity": quantity,
                    "category": category,
                    "location": location_name,
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
                location_id=location_id,
                embedding=embedding,
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
                    "location": updated_item.location.name if updated_item.location else None,
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
            location_name = item.location.name if item.location else None

            # Log the operation
            await log_transaction(
                session,
                operation="DELETE",
                item_id=item_id,
                data={"name": item_name, "location": location_name},
            )

            # Delete the item
            deleted = await delete_item(session, item_id)

            if deleted:
                msg = f"Removed {item_name}"
                if location_name:
                    msg += f" from {location_name}"
                return {
                    "status": "success",
                    "message": msg,
                }
            else:
                raise ToolError(f"Failed to delete item {item_id}")
    except ToolError:
        raise
    except Exception as e:
        logger.exception("Error removing item")
        raise ToolError(f"Failed to remove item: {str(e)}")


@mcp.tool()  # type: ignore[misc]
async def list_inventory(
    category: Optional[str] = None,
    location: Optional[str] = None,
) -> dict[str, Any]:
    """List all items in the inventory, optionally filtered by category or location.

    Use this to show what's stored in a particular place or category.

    Args:
        category: Optional category filter (e.g., "meat", "vegetables", "electronics")
        location: Optional location filter (e.g., "Freezer", "Garage", "Battery Bin")

    Returns:
        Dictionary with status, count, and list of items

    Examples:
        - "What's in the freezer?" -> list_inventory(location="Freezer")
        - "Show me all the meat" -> list_inventory(category="meat")
        - "What electronics do I have in the garage?" -> list_inventory(category="electronics", location="Garage")
    """
    try:
        async with AsyncSessionLocal() as session:
            items = await list_items(
                session,
                category=category,
                location_name=location,
            )

            return {
                "status": "success",
                "count": len(items),
                "filters": {
                    "category": category or "all",
                    "location": location or "all",
                },
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "quantity": item.quantity,
                        "category": item.category,
                        "location": item.location.name if item.location else None,
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
async def search_inventory(
    query: str,
    location: Optional[str] = None,
) -> dict[str, Any]:
    """Search inventory using natural language.

    This performs semantic search to find items matching your query.
    You can search for items by name, description, or general concept.

    Args:
        query: Natural language search query (e.g., "chicken", "something to grill", "batteries")
        location: Optional location to search within (e.g., "Freezer", "Garage")

    Returns:
        Dictionary with status, query, and matching items ranked by relevance

    Examples:
        - "Do I have any chicken?" -> search_inventory("chicken")
        - "What meat can I grill?" -> search_inventory("grillable meat", location="Freezer")
        - "Find batteries" -> search_inventory("batteries")
    """
    try:
        async with AsyncSessionLocal() as session:
            # Log the search operation
            await log_transaction(
                session,
                operation="SEARCH",
                data={"query": query, "location": location},
            )

            # Generate embedding for semantic search
            query_embedding = generate_embedding(query)

            # Try semantic search first
            semantic_results = await search_items_by_embedding(
                session,
                query_embedding,
                location_name=location,
                limit=10,
            )

            # Also do text search as fallback
            text_results = await search_items_by_text(
                session,
                query,
                location_name=location,
                limit=10,
            )

            # Combine results, preferring semantic search but including text matches
            seen_ids = set()
            results = []

            # Add semantic results with similarity score
            for item, distance in semantic_results:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    # Convert L2 distance to similarity score (lower distance = higher similarity)
                    similarity = max(0, 1 - (distance / 2))
                    results.append({
                        "id": item.id,
                        "name": item.name,
                        "quantity": item.quantity,
                        "category": item.category,
                        "location": item.location.name if item.location else None,
                        "description": item.description,
                        "relevance_score": round(similarity, 3),
                    })

            # Add text results that weren't in semantic results
            for item in text_results:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    results.append({
                        "id": item.id,
                        "name": item.name,
                        "quantity": item.quantity,
                        "category": item.category,
                        "location": item.location.name if item.location else None,
                        "description": item.description,
                        "relevance_score": 0.5,  # Default score for text matches
                    })

            return {
                "status": "success",
                "query": query,
                "location": location,
                "count": len(results),
                "results": results,
            }
    except Exception as e:
        logger.exception("Error searching inventory")
        raise ToolError(f"Failed to search inventory: {str(e)}")


@mcp.tool()  # type: ignore[misc]
async def add_location(
    name: str,
    description: str = "",
) -> dict[str, Any]:
    """Create a new storage location.

    Use this to add a new place where items can be stored.

    Args:
        name: Name of the location (e.g., "Garage Shelf", "Kitchen Pantry", "Tool Shed")
        description: Optional description of what's typically stored there

    Returns:
        Dictionary with status and location details
    """
    try:
        async with AsyncSessionLocal() as session:
            # Generate embedding for the location
            loc_text = f"{name} | {description}" if description else name
            embedding = generate_embedding(loc_text)

            location = await create_location(
                session,
                name=name,
                description=description if description else None,
                embedding=embedding,
            )

            await log_transaction(
                session,
                operation="CREATE_LOCATION",
                data={"name": name, "description": description},
            )

            return {
                "status": "success",
                "message": f"Created location: {name}",
                "location": {
                    "id": location.id,
                    "name": location.name,
                    "description": location.description,
                },
            }
    except Exception as e:
        logger.exception("Error creating location")
        raise ToolError(f"Failed to create location: {str(e)}")


@mcp.tool()  # type: ignore[misc]
async def get_locations() -> dict[str, Any]:
    """List all storage locations.

    Returns all available locations where items can be stored.

    Returns:
        Dictionary with status and list of locations
    """
    try:
        async with AsyncSessionLocal() as session:
            locations = await list_locations(session)

            return {
                "status": "success",
                "count": len(locations),
                "locations": [
                    {
                        "id": loc.id,
                        "name": loc.name,
                        "description": loc.description,
                    }
                    for loc in locations
                ],
            }
    except Exception as e:
        logger.exception("Error listing locations")
        raise ToolError(f"Failed to list locations: {str(e)}")


def main() -> None:
    """Entry point for the MCP server."""
    logger.info("Initializing Inventory Assistant MCP Server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
