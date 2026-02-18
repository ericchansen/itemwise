"""CRUD operations for inventory management."""

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Inventory, InventoryItem, InventoryMember, ItemLot, Location, TransactionLog, User  # noqa: F401

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


# ===== Inventory & Sharing Operations =====


async def create_inventory(session: AsyncSession, name: str, owner_user_id: int) -> Inventory:
    """Create a new inventory and add the owner as a member.

    Args:
        session: Database session
        name: Name of the inventory
        owner_user_id: ID of the user who owns this inventory

    Returns:
        The created inventory
    """
    inventory = Inventory(name=name)
    session.add(inventory)
    await session.flush()

    member = InventoryMember(inventory_id=inventory.id, user_id=owner_user_id)
    session.add(member)
    await session.commit()
    await session.refresh(inventory)
    logger.info(f"Created inventory: {inventory.name} (id={inventory.id}, owner={owner_user_id})")
    return inventory


async def list_inventories(session: AsyncSession, user_id: int) -> list[Inventory]:
    """List all inventories the user is a member of.

    Args:
        session: Database session
        user_id: ID of the user

    Returns:
        List of inventories the user belongs to, ordered by name
    """
    result = await session.execute(
        select(Inventory)
        .join(InventoryMember, Inventory.id == InventoryMember.inventory_id)
        .where(InventoryMember.user_id == user_id)
        .options(selectinload(Inventory.members))
        .order_by(Inventory.name)
    )
    return list(result.scalars().all())


async def get_inventory(session: AsyncSession, inventory_id: int) -> Optional[Inventory]:
    """Get an inventory by ID with members eager-loaded.

    Args:
        session: Database session
        inventory_id: ID of the inventory

    Returns:
        The inventory if found, None otherwise
    """
    result = await session.execute(
        select(Inventory)
        .where(Inventory.id == inventory_id)
        .options(selectinload(Inventory.members))
    )
    return result.scalar_one_or_none()


async def is_inventory_member(session: AsyncSession, inventory_id: int, user_id: int) -> bool:
    """Check if a user is a member of an inventory.

    Args:
        session: Database session
        inventory_id: ID of the inventory
        user_id: ID of the user

    Returns:
        True if the user is a member, False otherwise
    """
    result = await session.execute(
        select(InventoryMember).where(
            InventoryMember.inventory_id == inventory_id,
            InventoryMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def add_inventory_member(session: AsyncSession, inventory_id: int, user_id: int) -> InventoryMember:
    """Add a user to an inventory.

    Args:
        session: Database session
        inventory_id: ID of the inventory
        user_id: ID of the user to add

    Returns:
        The created InventoryMember
    """
    member = InventoryMember(inventory_id=inventory_id, user_id=user_id)
    session.add(member)
    await session.commit()
    await session.refresh(member)
    logger.info(f"Added member user_id={user_id} to inventory_id={inventory_id}")
    return member


async def remove_inventory_member(session: AsyncSession, inventory_id: int, user_id: int) -> bool:
    """Remove a member from an inventory.

    Args:
        session: Database session
        inventory_id: ID of the inventory
        user_id: ID of the user to remove

    Returns:
        True if member was removed, False if not found
    """
    result = await session.execute(
        delete(InventoryMember).where(
            InventoryMember.inventory_id == inventory_id,
            InventoryMember.user_id == user_id,
        )
    )
    await session.commit()
    removed: bool = result.rowcount > 0  # type: ignore[attr-defined]
    if removed:
        logger.info(f"Removed member user_id={user_id} from inventory_id={inventory_id}")
    return removed


async def list_inventory_members(session: AsyncSession, inventory_id: int) -> list[InventoryMember]:
    """List all members of an inventory.

    Args:
        session: Database session
        inventory_id: ID of the inventory

    Returns:
        List of InventoryMember entries with user info eager-loaded
    """
    result = await session.execute(
        select(InventoryMember)
        .where(InventoryMember.inventory_id == inventory_id)
        .options(selectinload(InventoryMember.user))
    )
    return list(result.scalars().all())


async def get_user_default_inventory(session: AsyncSession, user_id: int) -> Optional[Inventory]:
    """Get the user's default inventory (first by ID, ascending).

    If the user has no inventories, creates one named "{email}'s Inventory".

    Args:
        session: Database session
        user_id: ID of the user

    Returns:
        The user's default inventory
    """
    result = await session.execute(
        select(Inventory)
        .join(InventoryMember, Inventory.id == InventoryMember.inventory_id)
        .where(InventoryMember.user_id == user_id)
        .order_by(Inventory.id.asc())
        .limit(1)
    )
    inventory = result.scalar_one_or_none()
    if inventory:
        return inventory

    # No inventory exists — create one using the user's email
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return None

    return await create_inventory(session, f"{user.email}'s Inventory", user_id)


async def add_member_by_email(session: AsyncSession, inventory_id: int, email: str) -> Optional[InventoryMember]:
    """Add a user to an inventory by email address.

    Args:
        session: Database session
        inventory_id: ID of the inventory
        email: Email address of the user to add

    Returns:
        The InventoryMember if user was found, None if user not found
    """
    user = await get_user_by_email(session, email)
    if not user:
        return None

    # Check if already a member
    result = await session.execute(
        select(InventoryMember).where(
            InventoryMember.inventory_id == inventory_id,
            InventoryMember.user_id == user.id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    return await add_inventory_member(session, inventory_id, user.id)


# ===== Location Operations =====


async def create_location(
    session: AsyncSession,
    inventory_id: int,
    name: str,
    description: Optional[str] = None,
    embedding: Optional[list[float]] = None,
    normalized_name: Optional[str] = None,
) -> Location:
    """Create a new storage location.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
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
        inventory_id=inventory_id,
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
    session: AsyncSession, inventory_id: int, location_id: int
) -> Optional[Location]:
    """Get a location by ID, filtered by inventory_id for security.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory (prevents IDOR attacks)
        location_id: ID of the location to retrieve

    Returns:
        The location if found and owned by inventory, None otherwise
    """
    result = await session.execute(
        select(Location).where(
            Location.id == location_id,
            Location.inventory_id == inventory_id,
        )
    )
    return result.scalar_one_or_none()


async def get_location_by_name(session: AsyncSession, inventory_id: int, name: str) -> Optional[Location]:
    """Get a location by normalized name.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
        name: Name of the location (will be normalized for lookup)

    Returns:
        The location if found, None otherwise
    """
    normalized = normalize_location_name(name)
    result = await session.execute(
        select(Location).where(
            Location.normalized_name == normalized,
            Location.inventory_id == inventory_id
        )
    )
    return result.scalar_one_or_none()


async def list_locations(session: AsyncSession, inventory_id: int) -> list[Location]:
    """List all locations for an inventory.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory

    Returns:
        List of all locations for the inventory
    """
    result = await session.execute(
        select(Location).where(Location.inventory_id == inventory_id).order_by(Location.name)
    )
    return list(result.scalars().all())


async def get_or_create_location(
    session: AsyncSession,
    inventory_id: int,
    name: str,
    description: Optional[str] = None,
    embedding: Optional[list[float]] = None,
    display_name: Optional[str] = None,
) -> Location:
    """Get existing location by normalized name or create a new one.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
        name: Name of the location (any format - will be normalized for lookup)
        description: Optional description (used only if creating)
        embedding: Optional embedding (used only if creating)
        display_name: Optional display name for new location (if not provided, uses title case)

    Returns:
        The existing or newly created location
    """
    # Try to find existing location by normalized name
    location = await get_location_by_name(session, inventory_id, name)
    if location:
        return location
    
    # Create new location
    normalized = normalize_location_name(name)
    
    # Use provided display name or fall back to title case
    if not display_name:
        display_name = name.title()
    
    return await create_location(session, inventory_id, display_name, description, embedding, normalized)


# ===== Inventory Item Operations =====


async def create_item(
    session: AsyncSession,
    inventory_id: int,
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
        inventory_id: ID of the owning inventory
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
        inventory_id=inventory_id,
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
    logger.info(f"Created item: {item.name} (id={item.id}, inventory_id={inventory_id})")
    return item


async def get_item(session: AsyncSession, inventory_id: int, item_id: int) -> Optional[InventoryItem]:
    """Get an inventory item by ID.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
        item_id: ID of the item to retrieve

    Returns:
        The inventory item if found and owned by inventory, None otherwise
    """
    result = await session.execute(
        select(InventoryItem)
        .options(selectinload(InventoryItem.location))
        .where(
            InventoryItem.id == item_id,
            InventoryItem.inventory_id == inventory_id,
            InventoryItem.deleted_at.is_(None),
        )
    )
    item: InventoryItem | None = result.scalar_one_or_none()
    return item


async def list_items(
    session: AsyncSession,
    inventory_id: int,
    category: Optional[str] = None,
    location_id: Optional[int] = None,
    location_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[InventoryItem], int]:
    """List inventory items with optional filtering and pagination.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
        category: Optional category filter
        location_id: Optional location ID filter
        location_name: Optional location name filter (case-insensitive)
        limit: Maximum number of items to return
        offset: Number of items to skip

    Returns:
        Tuple of (list of inventory items, total count matching filters)
    """
    base_filter = select(InventoryItem).where(
        InventoryItem.inventory_id == inventory_id,
        InventoryItem.deleted_at.is_(None),
    )

    if category:
        base_filter = base_filter.where(InventoryItem.category == category)

    if location_id:
        base_filter = base_filter.where(InventoryItem.location_id == location_id)

    if location_name:
        normalized = normalize_location_name(location_name)
        base_filter = base_filter.join(Location).where(Location.normalized_name.contains(normalized))

    # Total count
    count_q = select(func.count()).select_from(base_filter.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    # Items query with pagination
    query = base_filter.options(selectinload(InventoryItem.location)).order_by(InventoryItem.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(query)
    return list(result.scalars().all()), total


async def update_item(
    session: AsyncSession,
    inventory_id: int,
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
        inventory_id: ID of the owning inventory
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
    item = await get_item(session, inventory_id, item_id)
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


async def delete_item(session: AsyncSession, inventory_id: int, item_id: int) -> bool:
    """Soft-delete an inventory item by setting deleted_at timestamp.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
        item_id: ID of the item to delete

    Returns:
        True if item was soft-deleted, False if not found
    """
    result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.inventory_id == inventory_id,
            InventoryItem.deleted_at.is_(None),
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        return False
    item.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    logger.info(f"Soft-deleted item id={item_id}")
    return True


async def list_deleted_items(
    session: AsyncSession, inventory_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[InventoryItem], int]:
    """List soft-deleted items (trash).

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
        limit: Maximum number of items to return
        offset: Number of items to skip

    Returns:
        Tuple of (list of soft-deleted items, total count)
    """
    base_filter = select(InventoryItem).where(
        InventoryItem.inventory_id == inventory_id,
        InventoryItem.deleted_at.isnot(None),
    )

    count_q = select(func.count()).select_from(base_filter.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    query = (
        base_filter.options(selectinload(InventoryItem.location))
        .order_by(InventoryItem.deleted_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    return list(result.scalars().all()), total


async def restore_item(session: AsyncSession, inventory_id: int, item_id: int) -> bool:
    """Restore a soft-deleted item.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
        item_id: ID of the item to restore

    Returns:
        True if item was restored, False if not found
    """
    result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.inventory_id == inventory_id,
            InventoryItem.deleted_at.isnot(None),
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        return False
    item.deleted_at = None
    await session.commit()
    logger.info(f"Restored item id={item_id}")
    return True


async def purge_item(session: AsyncSession, inventory_id: int, item_id: int) -> bool:
    """Permanently delete a soft-deleted item.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
        item_id: ID of the item to purge (must already be soft-deleted)

    Returns:
        True if item was purged, False if not found or not soft-deleted
    """
    result = await session.execute(
        delete(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.inventory_id == inventory_id,
            InventoryItem.deleted_at.isnot(None),
        )
    )
    await session.commit()
    purged: bool = result.rowcount > 0  # type: ignore[attr-defined]
    if purged:
        logger.info(f"Purged item id={item_id}")
    return purged


async def purge_old_deleted_items(
    session: AsyncSession, inventory_id: int, days: int = 30
) -> int:
    """Permanently delete items that have been in trash for more than N days.

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
        days: Number of days after which soft-deleted items are purged

    Returns:
        Number of items purged
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        delete(InventoryItem).where(
            InventoryItem.inventory_id == inventory_id,
            InventoryItem.deleted_at.isnot(None),
            InventoryItem.deleted_at < cutoff,
        )
    )
    await session.commit()
    count: int = result.rowcount  # type: ignore[attr-defined]
    if count:
        logger.info(f"Purged {count} old deleted items from inventory {inventory_id}")
    return count


async def search_items_by_text(
    session: AsyncSession,
    inventory_id: int,
    query: str,
    location_id: Optional[int] = None,
    location_name: Optional[str] = None,
    limit: int = 10,
) -> list[InventoryItem]:
    """Search items by text (case-insensitive name/description search).

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
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
            (InventoryItem.inventory_id == inventory_id) &
            (InventoryItem.deleted_at.is_(None)) &
            ((InventoryItem.name.ilike(f"%{query}%"))
            | (InventoryItem.description.ilike(f"%{query}%")))
        )
    )

    if location_id:
        stmt = stmt.where(InventoryItem.location_id == location_id)

    if location_name:
        normalized = normalize_location_name(location_name)
        stmt = stmt.join(Location).where(Location.normalized_name.contains(normalized))

    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_items_by_embedding(
    session: AsyncSession,
    inventory_id: int,
    query_embedding: list[float],
    location_id: Optional[int] = None,
    location_name: Optional[str] = None,
    limit: int = 10,
) -> list[tuple[InventoryItem, float]]:
    """Search items using vector similarity (semantic search).

    Args:
        session: Database session
        inventory_id: ID of the owning inventory
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
            (InventoryItem.inventory_id == inventory_id) &
            (InventoryItem.deleted_at.is_(None)) &
            (InventoryItem.embedding.isnot(None))
        )
    )

    if location_id:
        stmt = stmt.where(InventoryItem.location_id == location_id)

    if location_name:
        normalized = normalize_location_name(location_name)
        stmt = stmt.join(Location).where(Location.normalized_name.contains(normalized))

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


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    """Delete a user and clean up their data.

    For inventories where the user is the sole member, the entire inventory
    is deleted (FK cascades handle items, lots, locations, and memberships).
    For shared inventories, only the user's membership record is removed.

    Args:
        session: Database session
        user_id: ID of the user to delete

    Returns:
        True if the user was deleted, False if not found
    """
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        logger.warning("delete_user: user_id=%d not found", user_id)
        return False

    # Find all inventories this user belongs to
    memberships_result = await session.execute(
        select(InventoryMember).where(InventoryMember.user_id == user_id)
    )
    memberships = memberships_result.scalars().all()

    for membership in memberships:
        # Count how many members this inventory has
        count_result = await session.execute(
            select(func.count())
            .select_from(InventoryMember)
            .where(InventoryMember.inventory_id == membership.inventory_id)
        )
        member_count = count_result.scalar_one()

        if member_count == 1:
            # Sole member — delete entire inventory (FK cascades clean up)
            inv_result = await session.execute(
                select(Inventory).where(Inventory.id == membership.inventory_id)
            )
            inventory = inv_result.scalar_one_or_none()
            if inventory is not None:
                logger.info(
                    "delete_user: deleting sole-member inventory id=%d for user_id=%d",
                    membership.inventory_id,
                    user_id,
                )
                await session.delete(inventory)
        else:
            # Shared inventory — just remove the membership
            logger.info(
                "delete_user: removing membership inventory_id=%d for user_id=%d",
                membership.inventory_id,
                user_id,
            )
            await session.delete(membership)

    await session.delete(user)
    await session.commit()
    logger.info("delete_user: successfully deleted user_id=%d", user_id)
    return True


# ===== Item Lot Operations =====


async def create_lot(
    session: AsyncSession,
    item_id: int,
    quantity: int,
    added_by_user_id: Optional[int] = None,
    notes: Optional[str] = None,
    expiration_date: Optional[date] = None,
    inventory_id: Optional[int] = None,
) -> ItemLot:
    """Create a new lot for an inventory item.

    Also updates the parent item's quantity by adding the lot quantity.

    Args:
        session: Database session
        item_id: ID of the parent inventory item
        quantity: Quantity for this lot
        added_by_user_id: Optional ID of the user who added the lot
        notes: Optional notes about the lot
        expiration_date: Optional expiration date for this lot
        inventory_id: If provided, validates the item belongs to this inventory

    Returns:
        The created item lot
    """
    # Get the parent item and update its quantity (exclude soft-deleted)
    query = select(InventoryItem).where(
        InventoryItem.id == item_id,
        InventoryItem.deleted_at.is_(None),
    )
    if inventory_id is not None:
        query = query.where(InventoryItem.inventory_id == inventory_id)
    result = await session.execute(query)
    item = result.scalar_one_or_none()
    if item is None:
        if inventory_id is not None:
            raise ValueError(f"Item with id={item_id} not found in inventory {inventory_id}")
        raise ValueError(f"Item with id={item_id} not found")

    lot = ItemLot(
        item_id=item_id,
        quantity=quantity,
        added_by_user_id=added_by_user_id,
        notes=notes,
        expiration_date=expiration_date,
    )
    session.add(lot)
    item.quantity += quantity

    await session.commit()
    await session.refresh(lot)
    await session.refresh(item)
    logger.info(f"Created lot id={lot.id} for item id={item_id} (qty={quantity})")
    return lot


async def get_lots_for_item(
    session: AsyncSession,
    item_id: int,
) -> list[ItemLot]:
    """Get all lots for an item, ordered by added_at ascending (oldest first).

    Args:
        session: Database session
        item_id: ID of the parent inventory item

    Returns:
        List of item lots with eager-loaded user info
    """
    result = await session.execute(
        select(ItemLot)
        .options(selectinload(ItemLot.added_by))
        .where(ItemLot.item_id == item_id)
        .order_by(ItemLot.added_at.asc())
    )
    return list(result.scalars().all())


async def reduce_lot(
    session: AsyncSession,
    lot_id: int,
    quantity: int,
) -> Optional[ItemLot]:
    """Reduce a lot's quantity by the given amount.

    If quantity >= lot.quantity, the lot is deleted entirely.
    Also updates the parent item's quantity accordingly.
    If the item has no lots remaining, the item is deleted too.

    Args:
        session: Database session
        lot_id: ID of the lot to reduce
        quantity: Amount to subtract from the lot

    Returns:
        The lot if it still exists, None if deleted
    """
    result = await session.execute(
        select(ItemLot).where(ItemLot.id == lot_id)
    )
    lot = result.scalar_one_or_none()
    if lot is None:
        return None

    # Get the parent item (exclude soft-deleted)
    item_result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.id == lot.item_id,
            InventoryItem.deleted_at.is_(None),
        )
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        return None

    if quantity >= lot.quantity:
        # Delete the lot entirely
        removed = lot.quantity
        await session.delete(lot)
        item.quantity -= removed
        logger.info(f"Deleted lot id={lot_id} (removed qty={removed})")

        # Check if item has any remaining lots
        remaining = await session.execute(
            select(ItemLot).where(
                ItemLot.item_id == item.id,
                ItemLot.id != lot_id,
            )
        )
        if not remaining.scalars().first():
            await session.delete(item)
            logger.info(f"Deleted item id={item.id} (no lots remaining)")

        await session.commit()
        return None
    else:
        lot.quantity -= quantity
        item.quantity -= quantity
        await session.commit()
        await session.refresh(lot)
        logger.info(f"Reduced lot id={lot_id} by {quantity} (new qty={lot.quantity})")
        return lot


async def delete_lot(
    session: AsyncSession,
    lot_id: int,
) -> bool:
    """Delete a lot entirely.

    Subtracts the lot's quantity from the parent item.
    If the item has no lots remaining, the item is deleted too.

    Args:
        session: Database session
        lot_id: ID of the lot to delete

    Returns:
        True if the lot was deleted, False if not found
    """
    result = await session.execute(
        select(ItemLot).where(ItemLot.id == lot_id)
    )
    lot = result.scalar_one_or_none()
    if lot is None:
        return False

    # Get the parent item (exclude soft-deleted)
    item_result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.id == lot.item_id,
            InventoryItem.deleted_at.is_(None),
        )
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        return False

    item.quantity -= lot.quantity
    await session.delete(lot)
    logger.info(f"Deleted lot id={lot_id} (qty={lot.quantity})")

    # Check if item has any remaining lots
    remaining = await session.execute(
        select(ItemLot).where(
            ItemLot.item_id == item.id,
            ItemLot.id != lot_id,
        )
    )
    if not remaining.scalars().first():
        await session.delete(item)
        logger.info(f"Deleted item id={item.id} (no lots remaining)")

    await session.commit()
    return True


async def get_oldest_items(
    session: AsyncSession,
    inventory_id: int,
    location_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Find the oldest item lots in an inventory.

    Args:
        session: Database session
        inventory_id: ID of the inventory to search
        location_name: Optional location name filter (normalized for matching)
        limit: Maximum number of results

    Returns:
        List of dicts with item_name, item_id, lot_id, lot_quantity,
        added_at (ISO string), location_name, and expiration_date
    """
    stmt = (
        select(
            InventoryItem.name.label("item_name"),
            InventoryItem.id.label("item_id"),
            ItemLot.id.label("lot_id"),
            ItemLot.quantity.label("lot_quantity"),
            ItemLot.added_at,
            ItemLot.expiration_date,
            Location.name.label("location_name"),
        )
        .join(InventoryItem, ItemLot.item_id == InventoryItem.id)
        .join(Location, InventoryItem.location_id == Location.id)
        .where(InventoryItem.inventory_id == inventory_id)
        .where(InventoryItem.deleted_at.is_(None))
    )

    if location_name:
        normalized = normalize_location_name(location_name)
        stmt = stmt.where(Location.normalized_name.contains(normalized))

    stmt = stmt.order_by(ItemLot.added_at.asc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "item_name": row.item_name,
            "item_id": row.item_id,
            "lot_id": row.lot_id,
            "lot_quantity": row.lot_quantity,
            "added_at": row.added_at.isoformat() if row.added_at else None,
            "location_name": row.location_name,
            "expiration_date": row.expiration_date.isoformat() if row.expiration_date else None,
        }
        for row in rows
    ]


async def get_expiring_items(
    session: AsyncSession,
    inventory_id: int,
    days: int = 7,
) -> list[dict]:
    """Find items with lots expiring within N days.

    Args:
        session: Database session
        inventory_id: ID of the inventory to search
        days: Number of days to look ahead (default 7)

    Returns:
        List of dicts with item_name, lot_quantity, expiration_date,
        location_name, and days_until_expiry, ordered by expiration_date asc
    """
    today = date.today()
    cutoff = today + timedelta(days=days)

    stmt = (
        select(
            InventoryItem.name.label("item_name"),
            ItemLot.quantity.label("lot_quantity"),
            ItemLot.expiration_date,
            Location.name.label("location_name"),
        )
        .join(InventoryItem, ItemLot.item_id == InventoryItem.id)
        .outerjoin(Location, InventoryItem.location_id == Location.id)
        .where(InventoryItem.inventory_id == inventory_id)
        .where(InventoryItem.deleted_at.is_(None))
        .where(ItemLot.expiration_date.isnot(None))
        .where(ItemLot.expiration_date <= cutoff)
        .where(ItemLot.quantity > 0)
        .order_by(ItemLot.expiration_date.asc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "item_name": row.item_name,
            "lot_quantity": row.lot_quantity,
            "expiration_date": row.expiration_date.isoformat(),
            "location_name": row.location_name,
            "days_until_expiry": (row.expiration_date - today).days,
        }
        for row in rows
    ]


async def sync_item_quantity(
    session: AsyncSession,
    item_id: int,
) -> int:
    """Recalculate item quantity from sum of all lot quantities.

    Args:
        session: Database session
        item_id: ID of the item to sync

    Returns:
        The new calculated quantity
    """
    result = await session.execute(
        select(func.sum(ItemLot.quantity)).where(ItemLot.item_id == item_id)
    )
    total = result.scalar() or 0

    item_result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.deleted_at.is_(None),
        )
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise ValueError(f"Item with id={item_id} not found")

    item.quantity = total
    await session.commit()
    await session.refresh(item)
    logger.info(f"Synced item id={item_id} quantity to {total}")
    return total
