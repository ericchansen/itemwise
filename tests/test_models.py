"""Tests for database models."""

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.database.models import InventoryItem, TransactionLog


class TestInventoryItem:
    """Tests for InventoryItem model."""

    @pytest.mark.asyncio
    async def test_create_inventory_item(self, db_session: AsyncSession) -> None:
        """Test creating an inventory item."""
        item = InventoryItem(
            name="Chicken Breast",
            quantity=5,
            category="meat",
            description="Organic chicken",
        )

        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        assert item.id is not None
        assert item.name == "Chicken Breast"
        assert item.quantity == 5
        assert item.category == "meat"
        assert item.description == "Organic chicken"
        assert item.created_at is not None
        assert isinstance(item.created_at, datetime)

    @pytest.mark.asyncio
    async def test_inventory_item_with_embedding(
        self, db_session: AsyncSession
    ) -> None:
        """Test creating an item with vector embedding."""
        embedding = [0.1] * 384  # 384-dimensional vector (all-MiniLM-L6-v2)

        item = InventoryItem(
            name="Test Item",
            quantity=1,
            category="test",
            embedding=embedding,
        )

        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        assert item.embedding is not None
        assert len(item.embedding) == 384

    @pytest.mark.asyncio
    async def test_inventory_item_optional_fields(
        self, db_session: AsyncSession
    ) -> None:
        """Test creating an item with only required fields."""
        item = InventoryItem(
            name="Minimal Item",
            quantity=1,
            category="test",
        )

        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        assert item.description is None
        assert item.embedding is None
        assert item.updated_at is None

    def test_inventory_item_repr(self) -> None:
        """Test the string representation of InventoryItem."""
        item = InventoryItem(
            id=1,
            name="Test Item",
            quantity=5,
            category="test",
        )

        repr_str = repr(item)
        assert "InventoryItem" in repr_str
        assert "id=1" in repr_str
        assert "Test Item" in repr_str
        assert "quantity=5" in repr_str


class TestTransactionLog:
    """Tests for TransactionLog model."""

    @pytest.mark.asyncio
    async def test_create_transaction_log(self, db_session: AsyncSession) -> None:
        """Test creating a transaction log entry."""
        log = TransactionLog(
            operation="CREATE",
            item_id=1,
            data='{"name": "Test"}',
            status="PENDING",
        )

        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.id is not None
        assert log.operation == "CREATE"
        assert log.item_id == 1
        assert log.data == '{"name": "Test"}'
        assert log.status == "PENDING"
        assert log.timestamp is not None

    @pytest.mark.asyncio
    async def test_transaction_log_optional_item_id(
        self, db_session: AsyncSession
    ) -> None:
        """Test creating a log without item_id."""
        log = TransactionLog(
            operation="SEARCH",
            data='{"query": "test"}',
            status="PENDING",
        )

        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.item_id is None

    @pytest.mark.asyncio
    async def test_transaction_log_default_status(
        self, db_session: AsyncSession
    ) -> None:
        """Test default status value."""
        log = TransactionLog(
            operation="UPDATE",
            item_id=1,
        )

        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.status == "PENDING"

    def test_transaction_log_repr(self) -> None:
        """Test the string representation of TransactionLog."""
        log = TransactionLog(
            id=1,
            operation="CREATE",
            status="CONFIRMED",
        )

        repr_str = repr(log)
        assert "TransactionLog" in repr_str
        assert "id=1" in repr_str
        assert "operation='CREATE'" in repr_str
        assert "status='CONFIRMED'" in repr_str
