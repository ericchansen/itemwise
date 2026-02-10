"""Tests for inventory sharing features."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.database.crud import (
    create_inventory,
    create_user,
    list_inventories,
    get_inventory,
    is_inventory_member,
    add_inventory_member,
    remove_inventory_member,
    list_inventory_members,
    get_user_default_inventory,
    add_member_by_email,
)
from itemwise.database.models import User


@pytest_asyncio.fixture
async def test_inventory(db_session: AsyncSession, test_user: User):
    """Create a test inventory owned by the test user."""
    return await create_inventory(db_session, "Test Inventory", test_user.id)


@pytest_asyncio.fixture
async def second_user(db_session: AsyncSession):
    """Create a second test user."""
    hashed = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.F3z3z3z3z3z3z3"
    return await create_user(db_session, "second@example.com", hashed)


@pytest.mark.asyncio
async def test_create_inventory(db_session: AsyncSession, test_user: User):
    inv = await create_inventory(db_session, "My Inventory", test_user.id)
    assert inv.name == "My Inventory"
    assert inv.id is not None


@pytest.mark.asyncio
async def test_create_inventory_adds_owner_as_member(db_session: AsyncSession, test_user: User):
    inv = await create_inventory(db_session, "Test", test_user.id)
    assert await is_inventory_member(db_session, inv.id, test_user.id)


@pytest.mark.asyncio
async def test_list_inventories(db_session: AsyncSession, test_user: User, test_inventory):
    inventories = await list_inventories(db_session, test_user.id)
    assert len(inventories) >= 1
    assert any(i.id == test_inventory.id for i in inventories)


@pytest.mark.asyncio
async def test_get_inventory(db_session: AsyncSession, test_inventory):
    inv = await get_inventory(db_session, test_inventory.id)
    assert inv is not None
    assert inv.name == "Test Inventory"


@pytest.mark.asyncio
async def test_is_inventory_member_true(db_session: AsyncSession, test_user: User, test_inventory):
    assert await is_inventory_member(db_session, test_inventory.id, test_user.id)


@pytest.mark.asyncio
async def test_is_inventory_member_false(db_session: AsyncSession, test_inventory, second_user):
    assert not await is_inventory_member(db_session, test_inventory.id, second_user.id)


@pytest.mark.asyncio
async def test_add_inventory_member(db_session: AsyncSession, test_inventory, second_user):
    member = await add_inventory_member(db_session, test_inventory.id, second_user.id)
    assert member is not None
    assert await is_inventory_member(db_session, test_inventory.id, second_user.id)


@pytest.mark.asyncio
async def test_remove_inventory_member(db_session: AsyncSession, test_inventory, second_user):
    await add_inventory_member(db_session, test_inventory.id, second_user.id)
    removed = await remove_inventory_member(db_session, test_inventory.id, second_user.id)
    assert removed is True
    assert not await is_inventory_member(db_session, test_inventory.id, second_user.id)


@pytest.mark.asyncio
async def test_remove_nonexistent_member(db_session: AsyncSession, test_inventory, second_user):
    removed = await remove_inventory_member(db_session, test_inventory.id, second_user.id)
    assert removed is False


@pytest.mark.asyncio
async def test_list_inventory_members(db_session: AsyncSession, test_user: User, test_inventory, second_user):
    await add_inventory_member(db_session, test_inventory.id, second_user.id)
    members = await list_inventory_members(db_session, test_inventory.id)
    assert len(members) == 2
    user_ids = {m.user_id for m in members}
    assert test_user.id in user_ids
    assert second_user.id in user_ids


@pytest.mark.asyncio
async def test_get_user_default_inventory_creates_one(db_session: AsyncSession, test_user: User):
    inv = await get_user_default_inventory(db_session, test_user.id)
    assert inv is not None
    assert "test@example.com" in inv.name


@pytest.mark.asyncio
async def test_get_user_default_inventory_returns_existing(db_session: AsyncSession, test_user: User, test_inventory):
    inv = await get_user_default_inventory(db_session, test_user.id)
    assert inv.id == test_inventory.id


@pytest.mark.asyncio
async def test_add_member_by_email(db_session: AsyncSession, test_inventory, second_user):
    member = await add_member_by_email(db_session, test_inventory.id, "second@example.com")
    assert member is not None
    assert member.user_id == second_user.id


@pytest.mark.asyncio
async def test_add_member_by_email_not_found(db_session: AsyncSession, test_inventory):
    result = await add_member_by_email(db_session, test_inventory.id, "nobody@example.com")
    assert result is None
