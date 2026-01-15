"""CRUD operations for inventory management."""

import json
import logging
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import InventoryItem, TransactionLog

logger = logging.getLogger(__name__)


# ===== Inventory Item Operations =====


async def create_item(
    session: AsyncSession,
    name: str,
    quantity: int,
    category: str,
    description: Optional[str] = None,
    embedding: Optional[list[float]] = None,
) -> InventoryItem:
    """Create a new inventory item.

    Args:
        session: Database session
        name: Name of the item
        quantity: Quantity of the item
        category: Category (e.g., "meat", "vegetables")
        description: Optional description
        embedding: Optional vector embedding for semantic search

    Returns:
        The created inventory item
    """
    item = InventoryItem(
        name=name,
        quantity=quantity,
        category=category,
        description=description,
        embedding=embedding,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    logger.info(f"Created item: {item.name} (id={item.id})")
    return item


async def get_item(session: AsyncSession, item_id: int) -> Optional[InventoryItem]:
    """Get an inventory item by ID.

    Args:
        session: Database session
        item_id: ID of the item to retrieve

    Returns:
        The inventory item if found, None otherwise
    """
    result = await session.execute(
        select(InventoryItem).where(InventoryItem.id == item_id)
    )
    item: InventoryItem | None = result.scalar_one_or_none()
    return item


async def list_items(
    session: AsyncSession,
    category: Optional[str] = None,
    limit: int = 100,
) -> list[InventoryItem]:
    """List inventory items with optional filtering.

    Args:
        session: Database session
        category: Optional category filter
        limit: Maximum number of items to return

    Returns:
        List of inventory items
    """
    query = select(InventoryItem)

    if category:
        query = query.where(InventoryItem.category == category)

    query = query.order_by(InventoryItem.created_at.desc()).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def update_item(
    session: AsyncSession,
    item_id: int,
    name: Optional[str] = None,
    quantity: Optional[int] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
    embedding: Optional[list[float]] = None,
) -> Optional[InventoryItem]:
    """Update an inventory item.

    Args:
        session: Database session
        item_id: ID of the item to update
        name: New name (if provided)
        quantity: New quantity (if provided)
        category: New category (if provided)
        description: New description (if provided)
        embedding: New embedding (if provided)

    Returns:
        The updated item if found, None otherwise
    """
    item = await get_item(session, item_id)
    if not item:
        return None

    if name is not None:
        item.name = name
    if quantity is not None:
        item.quantity = quantity
    if category is not None:
        item.category = category
    if description is not None:
        item.description = description
    if embedding is not None:
        item.embedding = embedding

    await session.commit()
    await session.refresh(item)
    logger.info(f"Updated item: {item.name} (id={item.id})")
    return item


async def delete_item(session: AsyncSession, item_id: int) -> bool:
    """Delete an inventory item.

    Args:
        session: Database session
        item_id: ID of the item to delete

    Returns:
        True if item was deleted, False if not found
    """
    result = await session.execute(
        delete(InventoryItem).where(InventoryItem.id == item_id)
    )
    await session.commit()

    deleted: bool = result.rowcount > 0  # type: ignore[attr-defined]
    if deleted:
        logger.info(f"Deleted item id={item_id}")
    return deleted


async def search_items_by_text(
    session: AsyncSession,
    query: str,
    limit: int = 10,
) -> list[InventoryItem]:
    """Search items by text (case-insensitive name search).

    Args:
        session: Database session
        query: Search query
        limit: Maximum number of results

    Returns:
        List of matching items
    """
    result = await session.execute(
        select(InventoryItem).where(InventoryItem.name.ilike(f"%{query}%")).limit(limit)
    )
    return list(result.scalars().all())


async def search_items_by_embedding(
    session: AsyncSession,
    query_embedding: list[float],
    limit: int = 10,
) -> list[tuple[InventoryItem, float]]:
    """Search items using vector similarity (semantic search).

    Args:
        session: Database session
        query_embedding: Vector embedding of the search query
        limit: Maximum number of results

    Returns:
        List of (item, distance) tuples, ordered by similarity
    """
    # Calculate L2 distance between query embedding and item embeddings
    distance = InventoryItem.embedding.l2_distance(query_embedding)

    result = await session.execute(
        select(InventoryItem, distance)
        .where(InventoryItem.embedding.isnot(None))
        .order_by(distance)
        .limit(limit)
    )

    return [(row[0], row[1]) for row in result.all()]


# ===== Transaction Log Operations =====


async def log_transaction(
    session: AsyncSession,
    operation: str,
    item_id: Optional[int] = None,
    data: Optional[dict[str, Any]] = None,
    status: str = "PENDING",
) -> TransactionLog:
    """Log an AI operation to the transaction log.

    Args:
        session: Database session
        operation: Operation type (CREATE, UPDATE, DELETE, SEARCH)
        item_id: Optional ID of the affected item
        data: Optional additional data as dictionary
        status: Status of the transaction (PENDING, CONFIRMED, REJECTED)

    Returns:
        The created transaction log entry
    """
    log_entry = TransactionLog(
        operation=operation,
        item_id=item_id,
        data=json.dumps(data) if data else None,
        status=status,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    logger.info(f"Logged transaction: {operation} (id={log_entry.id})")
    return log_entry


async def get_transaction_logs(
    session: AsyncSession,
    limit: int = 100,
    status: Optional[str] = None,
) -> list[TransactionLog]:
    """Get transaction logs with optional status filter.

    Args:
        session: Database session
        limit: Maximum number of logs to return
        status: Optional status filter (PENDING, CONFIRMED, REJECTED)

    Returns:
        List of transaction log entries
    """
    query = select(TransactionLog)

    if status:
        query = query.where(TransactionLog.status == status)

    query = query.order_by(TransactionLog.timestamp.desc()).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())
