"""Tests for expiration date tracking features."""

from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.database.crud import (
    create_inventory,
    create_item,
    create_location,
    create_lot,
    get_expiring_items,
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
        name="Fridge",
        embedding=MOCK_EMBEDDING,
    )


@pytest_asyncio.fixture
async def test_item(db_session: AsyncSession, test_inventory, test_location):
    return await create_item(
        db_session,
        inventory_id=test_inventory.id,
        name="Milk",
        quantity=0,
        category="dairy",
        location_id=test_location.id,
        embedding=MOCK_EMBEDDING,
    )


@pytest.mark.asyncio
async def test_create_lot_with_expiration_date(db_session, test_item, test_user):
    """Test creating a lot with an expiration date."""
    exp_date = date.today() + timedelta(days=5)
    lot = await create_lot(
        db_session,
        item_id=test_item.id,
        quantity=2,
        added_by_user_id=test_user.id,
        expiration_date=exp_date,
    )
    assert lot.expiration_date == exp_date
    assert lot.quantity == 2


@pytest.mark.asyncio
async def test_create_lot_without_expiration_date(db_session, test_item, test_user):
    """Test creating a lot without an expiration date (nullable)."""
    lot = await create_lot(
        db_session,
        item_id=test_item.id,
        quantity=3,
        added_by_user_id=test_user.id,
    )
    assert lot.expiration_date is None


@pytest.mark.asyncio
async def test_get_expiring_items_within_window(db_session, test_inventory, test_item, test_user):
    """Test that get_expiring_items returns items expiring within the window."""
    exp_date = date.today() + timedelta(days=3)
    await create_lot(
        db_session,
        item_id=test_item.id,
        quantity=2,
        added_by_user_id=test_user.id,
        expiration_date=exp_date,
    )

    results = await get_expiring_items(db_session, test_inventory.id, days=7)
    assert len(results) == 1
    assert results[0]["item_name"] == "Milk"
    assert results[0]["lot_quantity"] == 2
    assert results[0]["expiration_date"] == exp_date.isoformat()
    assert results[0]["days_until_expiry"] == 3


@pytest.mark.asyncio
async def test_get_expiring_items_excludes_outside_window(db_session, test_inventory, test_item, test_user):
    """Test that items expiring outside the window are excluded."""
    exp_date = date.today() + timedelta(days=30)
    await create_lot(
        db_session,
        item_id=test_item.id,
        quantity=1,
        added_by_user_id=test_user.id,
        expiration_date=exp_date,
    )

    results = await get_expiring_items(db_session, test_inventory.id, days=7)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_get_expiring_items_excludes_no_expiration(db_session, test_inventory, test_item, test_user):
    """Test that items without expiration dates are excluded."""
    await create_lot(
        db_session,
        item_id=test_item.id,
        quantity=5,
        added_by_user_id=test_user.id,
    )

    results = await get_expiring_items(db_session, test_inventory.id, days=7)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_get_expiring_items_ordered_by_date(db_session, test_inventory, test_location, test_user):
    """Test that results are ordered by expiration date (soonest first)."""
    item1 = await create_item(
        db_session, inventory_id=test_inventory.id,
        name="Yogurt", quantity=0, category="dairy",
        location_id=test_location.id, embedding=MOCK_EMBEDDING,
    )
    item2 = await create_item(
        db_session, inventory_id=test_inventory.id,
        name="Eggs", quantity=0, category="dairy",
        location_id=test_location.id, embedding=MOCK_EMBEDDING,
    )

    # Eggs expire sooner than Yogurt
    await create_lot(
        db_session, item_id=item1.id, quantity=1,
        added_by_user_id=test_user.id,
        expiration_date=date.today() + timedelta(days=5),
    )
    await create_lot(
        db_session, item_id=item2.id, quantity=1,
        added_by_user_id=test_user.id,
        expiration_date=date.today() + timedelta(days=2),
    )

    results = await get_expiring_items(db_session, test_inventory.id, days=7)
    assert len(results) == 2
    assert results[0]["item_name"] == "Eggs"
    assert results[1]["item_name"] == "Yogurt"


@pytest.mark.asyncio
async def test_expiring_items_api_endpoint(db_session, test_user, test_inventory, test_item):
    """Test the GET /api/items/expiring API endpoint."""
    from unittest.mock import patch, AsyncMock
    from itemwise.api import app
    from itemwise.auth import create_access_token

    # Create a lot with expiration date
    exp_date = date.today() + timedelta(days=3)
    await create_lot(
        db_session,
        item_id=test_item.id,
        quantity=2,
        added_by_user_id=test_user.id,
        expiration_date=exp_date,
    )

    token = create_access_token(test_user.id, test_user.email)

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("itemwise.api.AsyncSessionLocal", return_value=mock_session_cm):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/items/expiring?days=7",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Inventory-Id": str(test_inventory.id),
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["days_window"] == 7
    assert data["items"][0]["item_name"] == "Milk"
