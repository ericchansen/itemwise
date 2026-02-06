"""CRUD operations for inventory management."""

import json
import logging
import re
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import InventoryItem, Location, TransactionLog, User

logger = logging.getLogger(__name__)


def normalize_location_name(name: str) -> str:
    """Normalize a location name for matching.
    
    - Lowercase
    - Remove apostrophes and other punctuation
    - Collapse multiple spaces
    - Strip whitespace
    
    Examples:
        "Tim's Pocket" -> "tims pocket"
        "Tims pocket" -> "tims pocket"
        "  GARAGE  " -> "garage"
    """
    # Lowercase
    normalized = name.lower()
    # Remove apostrophes and common punctuation
    normalized = re.sub(r"['\"\-_.,!?]", "", normalized)
    # Collapse multiple spaces
    normalized = re.sub(r"\s+", " ", normalized)
    # Strip
    return normalized.strip()


# ===== Location Operations =====


async def create_location(
    session: AsyncSession,
    user_id: int,
    name: str,
    description: Optional[str] = None,
    embedding: Optional[list[float]] = None,
    normalized_name: Optional[str] = None,
) -> Location:
    """Create a new storage location.

    Args:
        session: Database session
        user_id: ID of the owning user
        name: Display name of the location (e.g., "Tim's Pocket")
        description: Optional description
        embedding: Optional vector embedding for semantic search
        normalized_name: Optional pre-computed normalized name (for matching)

    Returns:
        The created location
    """
    if normalized_name is None:
        normalized_name = normalize_location_name(name)
    
    location = Location(
        user_id=user_id,
        name=name,
        normalized_name=normalized_name,
        description=description,
        embedding=embedding,
    )
    session.add(location)
    await session.commit()
    await session.refresh(location)
    logger.info(f"Created location: {location.name} (normalized: {location.normalized_name}, id={location.id})")
    return location


async def get_location(
    session: AsyncSession, user_id: int, location_id: int
) -> Optional[Location]:
    """Get a location by ID, filtered by user_id for security.

    Args:
        session: Database session
        user_id: ID of the owning user (prevents IDOR attacks)
        location_id: ID of the location to retrieve

    Returns:
        The location if found and owned by user, None otherwise
    """
    result = await session.execute(
        select(Location).where(
            Location.id == location_id,
            Location.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_location_by_name(session: AsyncSession, user_id: int, name: str) -> Optional[Location]:
    """Get a location by normalized name.

    Args:
        session: Database session
        user_id: ID of the owning user
        name: Name of the location (will be normalized for lookup)

    Returns:
        The location if found, None otherwise
    """
    normalized = normalize_location_name(name)
    result = await session.execute(
        select(Location).where(
            Location.normalized_name == normalized,
            Location.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def list_locations(session: AsyncSession, user_id: int) -> list[Location]:
    """List all locations for a user.

    Args:
        session: Database session
        user_id: ID of the owning user

    Returns:
        List of all locations for the user
    """
    result = await session.execute(
        select(Location).where(Location.user_id == user_id).order_by(Location.name)
    )
    return list(result.scalars().all())


async def get_or_create_location(
    session: AsyncSession,
    user_id: int,
    name: str,
    description: Optional[str] = None,
    embedding: Optional[list[float]] = None,
    display_name: Optional[str] = None,
) -> Location:
    """Get existing location by normalized name or create a new one.

    Args:
        session: Database session
        user_id: ID of the owning user
        name: Name of the location (any format - will be normalized for lookup)
        description: Optional description (used only if creating)
        embedding: Optional embedding (used only if creating)
        display_name: Optional display name for new location (if not provided, uses title case)

    Returns:
        The existing or newly created location
    """
    # Try to find existing location by normalized name
    location = await get_location_by_name(session, user_id, name)
    if location:
        return location
    
    # Create new location
    normalized = normalize_location_name(name)
    
    # Use provided display name or fall back to title case
    if not display_name:
        display_name = name.title()
    
    return await create_location(session, user_id, display_name, description, embedding, normalized)


# ===== Inventory Item Operations =====


async def create_item(
    session: AsyncSession,
    user_id: int,
    name: str,
    quantity: int,
    category: str,
    description: Optional[str] = None,
    location_id: Optional[int] = None,
    embedding: Optional[list[float]] = None,
) -> InventoryItem:
    """Create a new inventory item.

    Args:
        session: Database session
        user_id: ID of the owning user
        name: Name of the item
        quantity: Quantity of the item
        category: Category (e.g., "meat", "vegetables", "electronics")
        description: Optional description
        location_id: Optional ID of the storage location
        embedding: Optional vector embedding for semantic search

    Returns:
        The created inventory item
    """
    item = InventoryItem(
        user_id=user_id,
        name=name,
        quantity=quantity,
        category=category,
        description=description,
        location_id=location_id,
        embedding=embedding,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    logger.info(f"Created item: {item.name} (id={item.id}, user_id={user_id})")
    return item


async def get_item(session: AsyncSession, user_id: int, item_id: int) -> Optional[InventoryItem]:
    """Get an inventory item by ID.

    Args:
        session: Database session
        user_id: ID of the owning user
        item_id: ID of the item to retrieve

    Returns:
        The inventory item if found and owned by user, None otherwise
    """
    result = await session.execute(
        select(InventoryItem)
        .options(selectinload(InventoryItem.location))
        .where(
            InventoryItem.id == item_id,
            InventoryItem.user_id == user_id,
        )
    )
    item: InventoryItem | None = result.scalar_one_or_none()
    return item


async def list_items(
    session: AsyncSession,
    user_id: int,
    category: Optional[str] = None,
    location_id: Optional[int] = None,
    location_name: Optional[str] = None,
    limit: int = 100,
) -> list[InventoryItem]:
    """List inventory items with optional filtering.

    Args:
        session: Database session
        user_id: ID of the owning user
        category: Optional category filter
        location_id: Optional location ID filter
        location_name: Optional location name filter (case-insensitive)
        limit: Maximum number of items to return

    Returns:
        List of inventory items owned by the user
    """
    query = select(InventoryItem).options(selectinload(InventoryItem.location)).where(InventoryItem.user_id == user_id)

    if category:
        query = query.where(InventoryItem.category == category)

    if location_id:
        query = query.where(InventoryItem.location_id == location_id)

    if location_name:
        normalized = normalize_location_name(location_name)
        query = query.join(Location).where(Location.normalized_name == normalized)

    query = query.order_by(InventoryItem.created_at.desc()).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def update_item(
    session: AsyncSession,
    user_id: int,
    item_id: int,
    name: Optional[str] = None,
    quantity: Optional[int] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
    location_id: Optional[int] = None,
    embedding: Optional[list[float]] = None,
) -> Optional[InventoryItem]:
    """Update an inventory item.

    Args:
        session: Database session
        user_id: ID of the owning user
        item_id: ID of the item to update
        name: New name (if provided)
        quantity: New quantity (if provided)
        category: New category (if provided)
        description: New description (if provided)
        location_id: New location ID (if provided)
        embedding: New embedding (if provided)

    Returns:
        The updated item if found, None otherwise
    """
    item = await get_item(session, user_id, item_id)
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
    if location_id is not None:
        item.location_id = location_id
    if embedding is not None:
        item.embedding = embedding

    await session.commit()
    await session.refresh(item)
    logger.info(f"Updated item: {item.name} (id={item.id})")
    return item


async def delete_item(session: AsyncSession, user_id: int, item_id: int) -> bool:
    """Delete an inventory item.

    Args:
        session: Database session
        user_id: ID of the owning user
        item_id: ID of the item to delete

    Returns:
        True if item was deleted, False if not found
    """
    result = await session.execute(
        delete(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.user_id == user_id,
        )
    )
    await session.commit()

    deleted: bool = result.rowcount > 0  # type: ignore[attr-defined]
    if deleted:
        logger.info(f"Deleted item id={item_id}")
    return deleted


async def search_items_by_text(
    session: AsyncSession,
    user_id: int,
    query: str,
    location_id: Optional[int] = None,
    location_name: Optional[str] = None,
    limit: int = 10,
) -> list[InventoryItem]:
    """Search items by text (case-insensitive name/description search).

    Args:
        session: Database session
        user_id: ID of the owning user
        query: Search query
        location_id: Optional location ID filter
        location_name: Optional location name filter
        limit: Maximum number of results

    Returns:
        List of matching items
    """
    stmt = (
        select(InventoryItem)
        .options(selectinload(InventoryItem.location))
        .where(
            (InventoryItem.user_id == user_id) &
            ((InventoryItem.name.ilike(f"%{query}%"))
            | (InventoryItem.description.ilike(f"%{query}%")))
        )
    )

    if location_id:
        stmt = stmt.where(InventoryItem.location_id == location_id)

    if location_name:
        normalized = normalize_location_name(location_name)
        stmt = stmt.join(Location).where(Location.normalized_name == normalized)

    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_items_by_embedding(
    session: AsyncSession,
    user_id: int,
    query_embedding: list[float],
    location_id: Optional[int] = None,
    location_name: Optional[str] = None,
    limit: int = 10,
) -> list[tuple[InventoryItem, float]]:
    """Search items using vector similarity (semantic search).

    Args:
        session: Database session
        user_id: ID of the owning user
        query_embedding: Vector embedding of the search query
        location_id: Optional location ID filter
        location_name: Optional location name filter
        limit: Maximum number of results

    Returns:
        List of (item, distance) tuples, ordered by similarity
    """
    # Calculate L2 distance between query embedding and item embeddings
    distance = InventoryItem.embedding.l2_distance(query_embedding)

    stmt = (
        select(InventoryItem, distance)
        .options(selectinload(InventoryItem.location))
        .where(
            (InventoryItem.user_id == user_id) &
            (InventoryItem.embedding.isnot(None))
        )
    )

    if location_id:
        stmt = stmt.where(InventoryItem.location_id == location_id)

    if location_name:
        normalized = normalize_location_name(location_name)
        stmt = stmt.join(Location).where(Location.normalized_name == normalized)

    stmt = stmt.order_by(distance).limit(limit)
    result = await session.execute(stmt)

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


# ===== User Operations =====


async def create_user(
    session: AsyncSession,
    email: str,
    hashed_password: str,
) -> User:
    """Create a new user.

    Args:
        session: Database session
        email: User's email address
        hashed_password: Pre-hashed password

    Returns:
        The created user
    """
    user = User(email=email, hashed_password=hashed_password)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Created user: {user.email} (id={user.id})")
    return user


async def get_user_by_email(
    session: AsyncSession,
    email: str,
) -> Optional[User]:
    """Get a user by email address.

    Args:
        session: Database session
        email: Email address to look up

    Returns:
        The user if found, None otherwise
    """
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
