"""Tests for lot-based tracking features."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.database.crud import (
    create_inventory,
    create_item,
    create_location,
    create_lot,
    delete_lot,
    get_lots_for_item,
    get_oldest_items,
    reduce_lot,
    sync_item_quantity,
    get_item,
)
from itemwise.database.models import User


MOCK_EMBEDDING = [0.1] * 1536


@pytest_asyncio.fixture
async def test_inventory(db_session: AsyncSession, test_user: User):
    return await create_inventory(db_session, "Test Inventory", test_user.id)


@pytest_asyncio.fixture
async def test_location(db_session: AsyncSession, test_inventory):
    return await create_location(
        db_session,
        inventory_id=test_inventory.id,
        name="Freezer",
        embedding=MOCK_EMBEDDING,
    )


@pytest_asyncio.fixture
async def test_item(db_session: AsyncSession, test_inventory, test_location):
    return await create_item(
        db_session,
        inventory_id=test_inventory.id,
        name="Chicken Breast",
        quantity=0,  # Start with 0, lots will add quantity
        category="meat",
        location_id=test_location.id,
        embedding=MOCK_EMBEDDING,
    )


@pytest.mark.asyncio
async def test_create_lot(db_session: AsyncSession, test_item, test_user: User):
    lot = await create_lot(db_session, test_item.id, 5, added_by_user_id=test_user.id)
    assert lot.quantity == 5
    assert lot.item_id == test_item.id
    # Check item quantity was updated
    item = await get_item(db_session, test_item.inventory_id, test_item.id)
    assert item.quantity == 5


@pytest.mark.asyncio
async def test_create_multiple_lots(db_session: AsyncSession, test_item, test_user: User):
    await create_lot(db_session, test_item.id, 3, added_by_user_id=test_user.id)
    await create_lot(db_session, test_item.id, 2, added_by_user_id=test_user.id)
    item = await get_item(db_session, test_item.inventory_id, test_item.id)
    assert item.quantity == 5


@pytest.mark.asyncio
async def test_get_lots_for_item(db_session: AsyncSession, test_item, test_user: User):
    await create_lot(db_session, test_item.id, 3, added_by_user_id=test_user.id)
    await create_lot(db_session, test_item.id, 2, added_by_user_id=test_user.id)
    lots = await get_lots_for_item(db_session, test_item.id)
    assert len(lots) == 2
    assert lots[0].added_at <= lots[1].added_at  # Oldest first


@pytest.mark.asyncio
async def test_reduce_lot_partial(db_session: AsyncSession, test_item, test_user: User):
    lot = await create_lot(db_session, test_item.id, 5, added_by_user_id=test_user.id)
    result = await reduce_lot(db_session, lot.id, 2)
    assert result is not None
    assert result.quantity == 3
    item = await get_item(db_session, test_item.inventory_id, test_item.id)
    assert item.quantity == 3


@pytest.mark.asyncio
async def test_reduce_lot_full(db_session: AsyncSession, test_item, test_user: User):
    lot = await create_lot(db_session, test_item.id, 5, added_by_user_id=test_user.id)
    result = await reduce_lot(db_session, lot.id, 5)
    assert result is None  # Lot deleted


@pytest.mark.asyncio
async def test_delete_lot(db_session: AsyncSession, test_item, test_user: User):
    lot = await create_lot(db_session, test_item.id, 5, added_by_user_id=test_user.id)
    deleted = await delete_lot(db_session, lot.id)
    assert deleted is True
    lots = await get_lots_for_item(db_session, test_item.id)
    assert len(lots) == 0


@pytest.mark.asyncio
async def test_get_oldest_items(db_session: AsyncSession, test_inventory, test_item, test_user: User):
    await create_lot(db_session, test_item.id, 3, added_by_user_id=test_user.id)
    oldest = await get_oldest_items(db_session, test_inventory.id)
    assert len(oldest) >= 1
    assert oldest[0]["item_name"] == "Chicken Breast"


@pytest.mark.asyncio
async def test_get_oldest_items_with_location(db_session: AsyncSession, test_inventory, test_item, test_user: User):
    await create_lot(db_session, test_item.id, 3, added_by_user_id=test_user.id)
    oldest = await get_oldest_items(db_session, test_inventory.id, location_name="Freezer")
    assert len(oldest) >= 1

    # Non-existent location should return empty
    oldest = await get_oldest_items(db_session, test_inventory.id, location_name="Garage")
    assert len(oldest) == 0


@pytest.mark.asyncio
async def test_sync_item_quantity(db_session: AsyncSession, test_item, test_user: User):
    await create_lot(db_session, test_item.id, 3, added_by_user_id=test_user.id)
    await create_lot(db_session, test_item.id, 2, added_by_user_id=test_user.id)
    total = await sync_item_quantity(db_session, test_item.id)
    assert total == 5
