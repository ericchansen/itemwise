"""Tests for soft-delete functionality."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.database.crud import (
    create_item,
    delete_item,
    get_item,
    list_deleted_items,
    list_items,
    purge_item,
    purge_old_deleted_items,
    restore_item,
    search_items_by_embedding,
    search_items_by_text,
)
from itemwise.database.models import Inventory, InventoryItem, User


async def _create_test_item(
    session: AsyncSession,
    inventory_id: int,
    name: str = "Test Item",
    quantity: int = 1,
    category: str = "general",
) -> InventoryItem:
    """Helper to create a test item."""
    return await create_item(
        session,
        inventory_id=inventory_id,
        name=name,
        quantity=quantity,
        category=category,
    )


class TestSoftDelete:
    """Tests for soft-delete behavior."""

    @pytest.mark.asyncio
    async def test_delete_item_soft_deletes(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify item disappears from list_items but still exists in DB."""
        item = await _create_test_item(db_session, test_inventory.id, name="Soft Delete Me")

        # Delete the item (soft)
        result = await delete_item(db_session, test_inventory.id, item.id)
        assert result is True

        # Item should not appear in list_items
        items, total = await list_items(db_session, test_inventory.id)
        assert all(i.id != item.id for i in items)

        # Item should not be found via get_item
        found = await get_item(db_session, test_inventory.id, item.id)
        assert found is None

        # But item should still exist in the database
        raw = await db_session.execute(
            select(InventoryItem).where(InventoryItem.id == item.id)
        )
        db_item = raw.scalar_one_or_none()
        assert db_item is not None
        assert db_item.deleted_at is not None

    @pytest.mark.asyncio
    async def test_delete_item_not_found(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify deleting non-existent item returns False."""
        result = await delete_item(db_session, test_inventory.id, 99999)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_already_deleted_item(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify deleting an already soft-deleted item returns False."""
        item = await _create_test_item(db_session, test_inventory.id)
        await delete_item(db_session, test_inventory.id, item.id)

        # Second delete should fail
        result = await delete_item(db_session, test_inventory.id, item.id)
        assert result is False


class TestListDeletedItems:
    """Tests for listing soft-deleted items (trash view)."""

    @pytest.mark.asyncio
    async def test_list_deleted_items(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify trash view shows deleted items."""
        item1 = await _create_test_item(db_session, test_inventory.id, name="Item 1")
        item2 = await _create_test_item(db_session, test_inventory.id, name="Item 2")
        item3 = await _create_test_item(db_session, test_inventory.id, name="Item 3")

        # Delete two items
        await delete_item(db_session, test_inventory.id, item1.id)
        await delete_item(db_session, test_inventory.id, item2.id)

        # Trash should have 2 items
        deleted, total = await list_deleted_items(db_session, test_inventory.id)
        assert total == 2
        assert len(deleted) == 2
        deleted_ids = {i.id for i in deleted}
        assert item1.id in deleted_ids
        assert item2.id in deleted_ids
        assert item3.id not in deleted_ids

    @pytest.mark.asyncio
    async def test_list_deleted_items_empty(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify empty trash when no items deleted."""
        await _create_test_item(db_session, test_inventory.id)

        deleted, total = await list_deleted_items(db_session, test_inventory.id)
        assert total == 0
        assert len(deleted) == 0

    @pytest.mark.asyncio
    async def test_list_deleted_items_pagination(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify pagination works for trash view."""
        for i in range(5):
            item = await _create_test_item(
                db_session, test_inventory.id, name=f"Del Item {i}"
            )
            await delete_item(db_session, test_inventory.id, item.id)

        deleted, total = await list_deleted_items(
            db_session, test_inventory.id, limit=2, offset=0
        )
        assert total == 5
        assert len(deleted) == 2


class TestRestoreItem:
    """Tests for restoring soft-deleted items."""

    @pytest.mark.asyncio
    async def test_restore_item(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify restore makes item visible again."""
        item = await _create_test_item(db_session, test_inventory.id, name="Restore Me")
        await delete_item(db_session, test_inventory.id, item.id)

        # Restore
        result = await restore_item(db_session, test_inventory.id, item.id)
        assert result is True

        # Item should appear in list_items again
        items, total = await list_items(db_session, test_inventory.id)
        assert any(i.id == item.id for i in items)

        # Item should be findable via get_item
        found = await get_item(db_session, test_inventory.id, item.id)
        assert found is not None
        assert found.deleted_at is None

        # Item should no longer appear in trash
        deleted, total = await list_deleted_items(db_session, test_inventory.id)
        assert all(i.id != item.id for i in deleted)

    @pytest.mark.asyncio
    async def test_restore_non_deleted_item(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify restoring a non-deleted item returns False."""
        item = await _create_test_item(db_session, test_inventory.id)
        result = await restore_item(db_session, test_inventory.id, item.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_restore_nonexistent_item(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify restoring a nonexistent item returns False."""
        result = await restore_item(db_session, test_inventory.id, 99999)
        assert result is False


class TestPurgeItem:
    """Tests for permanently deleting soft-deleted items."""

    @pytest.mark.asyncio
    async def test_purge_item(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify permanent deletion of a soft-deleted item."""
        item = await _create_test_item(db_session, test_inventory.id, name="Purge Me")
        item_id = item.id
        await delete_item(db_session, test_inventory.id, item_id)

        result = await purge_item(db_session, test_inventory.id, item_id)
        assert result is True

        # Item should be completely gone from DB
        raw = await db_session.execute(
            select(InventoryItem).where(InventoryItem.id == item_id)
        )
        assert raw.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_purge_non_deleted_item(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify purge fails for items that aren't soft-deleted."""
        item = await _create_test_item(db_session, test_inventory.id)
        result = await purge_item(db_session, test_inventory.id, item.id)
        assert result is False

        # Item should still exist
        found = await get_item(db_session, test_inventory.id, item.id)
        assert found is not None

    @pytest.mark.asyncio
    async def test_purge_nonexistent_item(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify purge returns False for nonexistent items."""
        result = await purge_item(db_session, test_inventory.id, 99999)
        assert result is False


class TestSearchExcludesDeleted:
    """Tests that search functions exclude soft-deleted items."""

    @pytest.mark.asyncio
    async def test_search_by_text_excludes_deleted(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify text search excludes soft-deleted items."""
        item = await _create_test_item(
            db_session, test_inventory.id, name="Unique Searchable Item"
        )
        await delete_item(db_session, test_inventory.id, item.id)

        results = await search_items_by_text(
            db_session, test_inventory.id, "Unique Searchable"
        )
        assert all(r.id != item.id for r in results)

    @pytest.mark.asyncio
    async def test_search_by_embedding_excludes_deleted(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify embedding search excludes soft-deleted items."""
        embedding = [0.1] * 1536
        item = await create_item(
            db_session,
            inventory_id=test_inventory.id,
            name="Embedding Item",
            quantity=1,
            category="test",
            embedding=embedding,
        )
        await delete_item(db_session, test_inventory.id, item.id)

        results = await search_items_by_embedding(
            db_session, test_inventory.id, embedding
        )
        assert all(r[0].id != item.id for r in results)


class TestPurgeOldDeletedItems:
    """Tests for purging old soft-deleted items."""

    @pytest.mark.asyncio
    async def test_purge_old_deleted_items(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify items deleted more than N days ago are purged."""
        # Create and soft-delete items
        old_item = await _create_test_item(
            db_session, test_inventory.id, name="Old Deleted"
        )
        recent_item = await _create_test_item(
            db_session, test_inventory.id, name="Recent Deleted"
        )
        old_item_id = old_item.id
        recent_item_id = recent_item.id

        await delete_item(db_session, test_inventory.id, old_item_id)
        await delete_item(db_session, test_inventory.id, recent_item_id)

        # Manually set old_item's deleted_at to 31 days ago
        old_time = datetime.now(timezone.utc) - timedelta(days=31)
        await db_session.execute(
            text(
                "UPDATE inventory_items SET deleted_at = :ts WHERE id = :id"
            ).bindparams(ts=old_time, id=old_item_id)
        )
        await db_session.commit()

        # Purge items older than 30 days
        count = await purge_old_deleted_items(db_session, test_inventory.id, days=30)
        assert count == 1

        # Old item should be gone
        raw = await db_session.execute(
            select(InventoryItem).where(InventoryItem.id == old_item_id)
        )
        assert raw.scalar_one_or_none() is None

        # Recent item should still be in trash
        raw = await db_session.execute(
            select(InventoryItem).where(InventoryItem.id == recent_item_id)
        )
        recent = raw.scalar_one_or_none()
        assert recent is not None
        assert recent.deleted_at is not None

    @pytest.mark.asyncio
    async def test_purge_old_deleted_items_none_expired(
        self, db_session: AsyncSession, test_user: User, test_inventory: Inventory
    ) -> None:
        """Verify no items purged when none are old enough."""
        item = await _create_test_item(db_session, test_inventory.id)
        await delete_item(db_session, test_inventory.id, item.id)

        count = await purge_old_deleted_items(db_session, test_inventory.id, days=30)
        assert count == 0
