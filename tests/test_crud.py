"""Tests for CRUD operations."""

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.database.crud import (
    create_item,
    delete_item,
    get_item,
    get_transaction_logs,
    list_items,
    log_transaction,
    search_items_by_embedding,
    search_items_by_text,
    update_item,
)
from itemwise.database.models import InventoryItem


class TestCreateItem:
    """Tests for create_item function."""

    @pytest.mark.asyncio
    async def test_create_basic_item(
        self, db_session: AsyncSession, sample_item_data: dict[str, Any]
    ) -> None:
        """Test creating a basic inventory item."""
        item = await create_item(db_session, **sample_item_data)

        assert item.id is not None
        assert item.name == sample_item_data["name"]
        assert item.quantity == sample_item_data["quantity"]
        assert item.category == sample_item_data["category"]
        assert item.description == sample_item_data["description"]

    @pytest.mark.asyncio
    async def test_create_item_with_embedding(self, db_session: AsyncSession) -> None:
        """Test creating an item with vector embedding."""
        embedding = [0.5] * 384  # 384-dimensional (all-MiniLM-L6-v2)

        item = await create_item(
            db_session,
            name="Test Item",
            quantity=1,
            category="test",
            embedding=embedding,
        )

        assert item.embedding is not None
        assert len(item.embedding) == 384

    @pytest.mark.asyncio
    async def test_create_item_minimal(self, db_session: AsyncSession) -> None:
        """Test creating an item with only required fields."""
        item = await create_item(
            db_session,
            name="Minimal",
            quantity=1,
            category="test",
        )

        assert item.id is not None
        assert item.description is None


class TestGetItem:
    """Tests for get_item function."""

    @pytest.mark.asyncio
    async def test_get_existing_item(
        self, db_session: AsyncSession, sample_item_data: dict[str, Any]
    ) -> None:
        """Test retrieving an existing item."""
        created_item = await create_item(db_session, **sample_item_data)

        retrieved_item = await get_item(db_session, created_item.id)

        assert retrieved_item is not None
        assert retrieved_item.id == created_item.id
        assert retrieved_item.name == created_item.name

    @pytest.mark.asyncio
    async def test_get_nonexistent_item(self, db_session: AsyncSession) -> None:
        """Test retrieving a non-existent item."""
        item = await get_item(db_session, 99999)
        assert item is None


class TestListItems:
    """Tests for list_items function."""

    @pytest.mark.asyncio
    async def test_list_all_items(self, db_session: AsyncSession) -> None:
        """Test listing all items."""
        await create_item(db_session, "Item 1", 1, "meat")
        await create_item(db_session, "Item 2", 2, "vegetables")
        await create_item(db_session, "Item 3", 3, "meat")

        items = await list_items(db_session)

        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_list_items_by_category(self, db_session: AsyncSession) -> None:
        """Test listing items filtered by category."""
        await create_item(db_session, "Chicken", 1, "meat")
        await create_item(db_session, "Peas", 2, "vegetables")
        await create_item(db_session, "Beef", 3, "meat")

        meat_items = await list_items(db_session, category="meat")

        assert len(meat_items) == 2
        assert all(item.category == "meat" for item in meat_items)

    @pytest.mark.asyncio
    async def test_list_items_with_limit(self, db_session: AsyncSession) -> None:
        """Test listing items with a limit."""
        for i in range(5):
            await create_item(db_session, f"Item {i}", i, "test")

        items = await list_items(db_session, limit=3)

        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_list_items_empty(self, db_session: AsyncSession) -> None:
        """Test listing items when database is empty."""
        items = await list_items(db_session)
        assert items == []


class TestUpdateItem:
    """Tests for update_item function."""

    @pytest.mark.asyncio
    async def test_update_item_name(
        self, db_session: AsyncSession, sample_item_data: dict[str, Any]
    ) -> None:
        """Test updating an item's name."""
        item = await create_item(db_session, **sample_item_data)

        updated = await update_item(db_session, item.id, name="New Name")

        assert updated.name == "New Name"
        assert updated.quantity == sample_item_data["quantity"]

    @pytest.mark.asyncio
    async def test_update_item_quantity(
        self, db_session: AsyncSession, sample_item_data: dict[str, Any]
    ) -> None:
        """Test updating an item's quantity."""
        item = await create_item(db_session, **sample_item_data)

        updated = await update_item(db_session, item.id, quantity=10)

        assert updated.quantity == 10

    @pytest.mark.asyncio
    async def test_update_multiple_fields(
        self, db_session: AsyncSession, sample_item_data: dict[str, Any]
    ) -> None:
        """Test updating multiple fields at once."""
        item = await create_item(db_session, **sample_item_data)

        updated = await update_item(
            db_session,
            item.id,
            name="Updated",
            quantity=20,
            category="frozen",
            description="New description",
        )

        assert updated.name == "Updated"
        assert updated.quantity == 20
        assert updated.category == "frozen"
        assert updated.description == "New description"

    @pytest.mark.asyncio
    async def test_update_nonexistent_item(self, db_session: AsyncSession) -> None:
        """Test updating a non-existent item."""
        result = await update_item(db_session, 99999, name="Test")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_item_embedding(
        self, db_session: AsyncSession, sample_item_data: dict[str, Any]
    ) -> None:
        """Test updating an item's embedding."""
        item = await create_item(db_session, **sample_item_data)

        # Use correct dimension size (384 for all-MiniLM-L6-v2)
        new_embedding = [0.1] * 384
        updated = await update_item(db_session, item.id, embedding=new_embedding)

        # Compare list elements instead of using == on arrays
        assert len(updated.embedding) == len(new_embedding)
        assert all(abs(a - b) < 0.001 for a, b in zip(updated.embedding, new_embedding))


class TestDeleteItem:
    """Tests for delete_item function."""

    @pytest.mark.asyncio
    async def test_delete_existing_item(
        self, db_session: AsyncSession, sample_item_data: dict[str, Any]
    ) -> None:
        """Test deleting an existing item."""
        item = await create_item(db_session, **sample_item_data)

        deleted = await delete_item(db_session, item.id)

        assert deleted is True

        # Verify item is gone
        result = await get_item(db_session, item.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_item(self, db_session: AsyncSession) -> None:
        """Test deleting a non-existent item."""
        deleted = await delete_item(db_session, 99999)
        assert deleted is False


class TestSearchItems:
    """Tests for search functions."""

    @pytest.mark.asyncio
    async def test_search_by_text_exact_match(self, db_session: AsyncSession) -> None:
        """Test text search with exact match."""
        await create_item(db_session, "Chicken Breast", 1, "meat")
        await create_item(db_session, "Frozen Peas", 2, "vegetables")

        results = await search_items_by_text(db_session, "Chicken")

        assert len(results) == 1
        assert results[0].name == "Chicken Breast"

    @pytest.mark.asyncio
    async def test_search_by_text_case_insensitive(
        self, db_session: AsyncSession
    ) -> None:
        """Test that text search is case-insensitive."""
        await create_item(db_session, "Chicken Breast", 1, "meat")

        results = await search_items_by_text(db_session, "chicken")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_by_text_partial_match(self, db_session: AsyncSession) -> None:
        """Test text search with partial match."""
        await create_item(db_session, "Chicken Breast", 1, "meat")
        await create_item(db_session, "Chicken Thigh", 2, "meat")

        results = await search_items_by_text(db_session, "chick")

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_by_text_with_limit(self, db_session: AsyncSession) -> None:
        """Test text search with result limit."""
        for i in range(5):
            await create_item(db_session, f"Chicken {i}", 1, "meat")

        results = await search_items_by_text(db_session, "Chicken", limit=3)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_by_embedding(self, db_session: AsyncSession) -> None:
        """Test vector similarity search."""
        embedding1 = [1.0] * 384  # 384-dimensional (all-MiniLM-L6-v2)
        embedding2 = [0.5] * 384

        await create_item(db_session, "Item 1", 1, "test", embedding=embedding1)
        await create_item(db_session, "Item 2", 2, "test", embedding=embedding2)

        query_embedding = [0.9] * 384
        results = await search_items_by_embedding(db_session, query_embedding)

        assert len(results) == 2
        # Results should be tuples of (item, distance)
        assert isinstance(results[0], tuple)
        assert isinstance(results[0][0], InventoryItem)
        assert isinstance(results[0][1], float)


class TestTransactionLog:
    """Tests for transaction logging functions."""

    @pytest.mark.asyncio
    async def test_log_transaction_basic(self, db_session: AsyncSession) -> None:
        """Test creating a basic transaction log."""
        log = await log_transaction(
            db_session,
            operation="CREATE",
            item_id=1,
            data={"name": "Test"},
        )

        assert log.id is not None
        assert log.operation == "CREATE"
        assert log.item_id == 1
        assert log.status == "PENDING"

    @pytest.mark.asyncio
    async def test_log_transaction_with_status(self, db_session: AsyncSession) -> None:
        """Test creating a transaction log with custom status."""
        log = await log_transaction(
            db_session,
            operation="UPDATE",
            status="CONFIRMED",
        )

        assert log.status == "CONFIRMED"

    @pytest.mark.asyncio
    async def test_log_transaction_dict_data(self, db_session: AsyncSession) -> None:
        """Test that dict data is properly serialized."""
        data = {"name": "Test", "quantity": 5}

        log = await log_transaction(
            db_session,
            operation="CREATE",
            data=data,
        )

        # Data should be JSON string
        assert log.data is not None
        parsed = json.loads(log.data)
        assert parsed == data

    @pytest.mark.asyncio
    async def test_get_transaction_logs_all(self, db_session: AsyncSession) -> None:
        """Test retrieving all transaction logs."""
        await log_transaction(db_session, "CREATE", status="PENDING")
        await log_transaction(db_session, "UPDATE", status="CONFIRMED")
        await log_transaction(db_session, "DELETE", status="PENDING")

        logs = await get_transaction_logs(db_session)

        assert len(logs) == 3

    @pytest.mark.asyncio
    async def test_get_transaction_logs_by_status(
        self, db_session: AsyncSession
    ) -> None:
        """Test filtering transaction logs by status."""
        await log_transaction(db_session, "CREATE", status="PENDING")
        await log_transaction(db_session, "UPDATE", status="CONFIRMED")
        await log_transaction(db_session, "DELETE", status="PENDING")

        pending_logs = await get_transaction_logs(db_session, status="PENDING")

        assert len(pending_logs) == 2
        assert all(log.status == "PENDING" for log in pending_logs)

    @pytest.mark.asyncio
    async def test_get_transaction_logs_with_limit(
        self, db_session: AsyncSession
    ) -> None:
        """Test limiting transaction log results."""
        for i in range(5):
            await log_transaction(db_session, f"OP{i}")

        logs = await get_transaction_logs(db_session, limit=3)

        assert len(logs) == 3
