"""Tests for cross-inventory authorization.

Verifies that User A cannot access, modify, or delete resources
(items, locations, lots) belonging to User B's inventory.
"""

from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.api import app
from itemwise.auth import create_access_token, hash_password
from itemwise.database.crud import (
    create_inventory,
    create_item,
    create_location,
    create_lot,
    create_user,
)
from itemwise.database.models import Inventory, InventoryItem, Location, User


# ===== Fixtures =====


@pytest.fixture
def patch_db(mock_session_factory: Any) -> Any:
    """Patch AsyncSessionLocal in api module to use test session."""
    with patch("itemwise.api.AsyncSessionLocal", mock_session_factory):
        yield


@pytest_asyncio.fixture
async def client(patch_db: Any) -> AsyncClient:
    """Async HTTP test client wired to test database."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


def auth_header(user_id: int, email: str) -> dict[str, str]:
    """Build Authorization header with a valid access token."""
    token = create_access_token(user_id, email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_a(db_session: AsyncSession) -> User:
    """Create User A."""
    hashed = hash_password("TestPass1!")
    return await create_user(db_session, "user_a@example.com", hashed)


@pytest_asyncio.fixture
async def user_b(db_session: AsyncSession) -> User:
    """Create User B."""
    hashed = hash_password("TestPass2!")
    return await create_user(db_session, "user_b@example.com", hashed)


@pytest_asyncio.fixture
async def inventory_a(db_session: AsyncSession, user_a: User) -> Inventory:
    """Create inventory owned by User A."""
    return await create_inventory(db_session, "User A Inventory", user_a.id)


@pytest_asyncio.fixture
async def inventory_b(db_session: AsyncSession, user_b: User) -> Inventory:
    """Create inventory owned by User B."""
    return await create_inventory(db_session, "User B Inventory", user_b.id)


@pytest_asyncio.fixture
async def location_b(db_session: AsyncSession, inventory_b: Inventory) -> Location:
    """Create a location in User B's inventory."""
    return await create_location(db_session, inventory_b.id, "B's Freezer")


@pytest_asyncio.fixture
async def item_b(
    db_session: AsyncSession, inventory_b: Inventory, location_b: Location
) -> InventoryItem:
    """Create an item in User B's inventory."""
    return await create_item(
        db_session,
        inventory_id=inventory_b.id,
        name="User B's Chicken",
        quantity=5,
        category="meat",
        description="User B's private chicken",
        location_id=location_b.id,
    )


@pytest_asyncio.fixture
async def item_a(
    db_session: AsyncSession, inventory_a: Inventory
) -> InventoryItem:
    """Create an item in User A's inventory."""
    return await create_item(
        db_session,
        inventory_id=inventory_a.id,
        name="User A's Bread",
        quantity=2,
        category="bakery",
    )


# ===== Tests: Items =====


class TestCrossInventoryItems:
    """Verify User A cannot access User B's items."""

    @pytest.mark.asyncio
    async def test_get_item_from_other_inventory_returns_404(
        self, client: AsyncClient, user_a: User, inventory_a: Inventory, item_b: InventoryItem
    ) -> None:
        """User A cannot GET an item belonging to User B."""
        resp = await client.get(
            f"/api/items/{item_b.id}",
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_items_only_shows_own_inventory(
        self,
        client: AsyncClient,
        user_a: User,
        inventory_a: Inventory,
        item_a: InventoryItem,
        item_b: InventoryItem,
    ) -> None:
        """User A's item list should not include User B's items."""
        resp = await client.get(
            "/api/items",
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 200
        data = resp.json()
        item_ids = [item["id"] for item in data["items"]]
        assert item_a.id in item_ids
        assert item_b.id not in item_ids

    @pytest.mark.asyncio
    async def test_update_item_in_other_inventory_returns_404(
        self, client: AsyncClient, user_a: User, inventory_a: Inventory, item_b: InventoryItem
    ) -> None:
        """User A cannot PUT an item belonging to User B."""
        resp = await client.put(
            f"/api/items/{item_b.id}",
            json={"name": "Hacked Chicken"},
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_item_in_other_inventory_returns_404(
        self, client: AsyncClient, user_a: User, inventory_a: Inventory, item_b: InventoryItem
    ) -> None:
        """User A cannot DELETE an item belonging to User B."""
        resp = await client.delete(
            f"/api/items/{item_b.id}",
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_item_in_other_inventory_via_header_rejected(
        self, client: AsyncClient, user_a: User, inventory_b: Inventory
    ) -> None:
        """User A cannot create an item in User B's inventory via X-Inventory-Id header."""
        resp = await client.post(
            "/api/items",
            json={
                "name": "Sneaky Item",
                "quantity": 1,
                "category": "hacking",
            },
            headers={
                **auth_header(user_a.id, user_a.email),
                "X-Inventory-Id": str(inventory_b.id),
            },
        )
        assert resp.status_code == 403


# ===== Tests: Locations =====


class TestCrossInventoryLocations:
    """Verify User A cannot access User B's locations."""

    @pytest.mark.asyncio
    async def test_list_locations_only_shows_own_inventory(
        self,
        client: AsyncClient,
        user_a: User,
        inventory_a: Inventory,
        location_b: Location,
    ) -> None:
        """User A's location list should not include User B's locations."""
        resp = await client.get(
            "/api/locations",
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 200
        data = resp.json()
        location_ids = [loc["id"] for loc in data["locations"]]
        assert location_b.id not in location_ids

    @pytest.mark.asyncio
    async def test_create_location_in_other_inventory_via_header_rejected(
        self, client: AsyncClient, user_a: User, inventory_b: Inventory
    ) -> None:
        """User A cannot create a location in User B's inventory via X-Inventory-Id."""
        resp = await client.post(
            "/api/locations",
            json={"name": "Sneaky Location"},
            headers={
                **auth_header(user_a.id, user_a.email),
                "X-Inventory-Id": str(inventory_b.id),
            },
        )
        assert resp.status_code == 403


# ===== Tests: Inventory Access =====


class TestCrossInventoryAccess:
    """Verify User A cannot access User B's inventory metadata."""

    @pytest.mark.asyncio
    async def test_list_inventories_only_shows_own(
        self,
        client: AsyncClient,
        user_a: User,
        inventory_a: Inventory,
        inventory_b: Inventory,
    ) -> None:
        """User A should only see their own inventories."""
        resp = await client.get(
            "/api/inventories",
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 200
        data = resp.json()
        inv_ids = [inv["id"] for inv in data["inventories"]]
        assert inventory_a.id in inv_ids
        assert inventory_b.id not in inv_ids

    @pytest.mark.asyncio
    async def test_get_inventory_members_of_other_inventory_rejected(
        self,
        client: AsyncClient,
        user_a: User,
        inventory_b: Inventory,
    ) -> None:
        """User A cannot list members of User B's inventory."""
        resp = await client.get(
            f"/api/inventories/{inventory_b.id}/members",
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_add_member_to_other_inventory_rejected(
        self,
        client: AsyncClient,
        user_a: User,
        inventory_b: Inventory,
    ) -> None:
        """User A cannot add members to User B's inventory."""
        resp = await client.post(
            f"/api/inventories/{inventory_b.id}/members",
            json={"email": "hacker@example.com"},
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_remove_member_from_other_inventory_rejected(
        self,
        client: AsyncClient,
        user_a: User,
        user_b: User,
        inventory_b: Inventory,
    ) -> None:
        """User A cannot remove members from User B's inventory."""
        resp = await client.delete(
            f"/api/inventories/{inventory_b.id}/members/{user_b.id}",
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 403


# ===== Tests: Search =====


class TestCrossInventorySearch:
    """Verify search is scoped to the user's own inventory."""

    @pytest.mark.asyncio
    async def test_search_does_not_leak_other_inventory_items(
        self,
        client: AsyncClient,
        user_a: User,
        inventory_a: Inventory,
        item_b: InventoryItem,
    ) -> None:
        """Searching for User B's item name should return no results for User A."""
        resp = await client.get(
            "/api/search",
            params={"q": "Chicken"},
            headers=auth_header(user_a.id, user_a.email),
        )
        assert resp.status_code == 200
        data = resp.json()
        result_ids = [r["id"] for r in data["results"]]
        assert item_b.id not in result_ids


# ===== Tests: X-Inventory-Id Header Validation =====


class TestInventoryHeaderValidation:
    """Verify X-Inventory-Id header is validated against membership."""

    @pytest.mark.asyncio
    async def test_items_with_nonmember_inventory_header(
        self, client: AsyncClient, user_a: User, inventory_b: Inventory
    ) -> None:
        """GET /api/items with X-Inventory-Id of non-member inventory is rejected."""
        resp = await client.get(
            "/api/items",
            headers={
                **auth_header(user_a.id, user_a.email),
                "X-Inventory-Id": str(inventory_b.id),
            },
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_locations_with_nonmember_inventory_header(
        self, client: AsyncClient, user_a: User, inventory_b: Inventory
    ) -> None:
        """GET /api/locations with X-Inventory-Id of non-member inventory is rejected."""
        resp = await client.get(
            "/api/locations",
            headers={
                **auth_header(user_a.id, user_a.email),
                "X-Inventory-Id": str(inventory_b.id),
            },
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_search_with_nonmember_inventory_header(
        self, client: AsyncClient, user_a: User, inventory_b: Inventory
    ) -> None:
        """GET /api/search with X-Inventory-Id of non-member inventory is rejected."""
        resp = await client.get(
            "/api/search",
            params={"q": "test"},
            headers={
                **auth_header(user_a.id, user_a.email),
                "X-Inventory-Id": str(inventory_b.id),
            },
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_expiring_items_with_nonmember_inventory_header(
        self, client: AsyncClient, user_a: User, inventory_b: Inventory
    ) -> None:
        """GET /api/items/expiring with X-Inventory-Id of non-member inventory is rejected."""
        resp = await client.get(
            "/api/items/expiring",
            headers={
                **auth_header(user_a.id, user_a.email),
                "X-Inventory-Id": str(inventory_b.id),
            },
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_chat_with_nonmember_inventory_header(
        self, client: AsyncClient, user_a: User, inventory_b: Inventory
    ) -> None:
        """POST /api/chat with X-Inventory-Id of non-member inventory is rejected."""
        resp = await client.post(
            "/api/chat",
            json={"message": "list items"},
            headers={
                **auth_header(user_a.id, user_a.email),
                "X-Inventory-Id": str(inventory_b.id),
            },
        )
        assert resp.status_code == 403


# ===== Tests: CRUD-level lot isolation =====


class TestCrossInventoryLotsCRUD:
    """Verify lot CRUD functions validate inventory ownership."""

    @pytest.mark.asyncio
    async def test_create_lot_rejects_item_from_other_inventory(
        self,
        db_session: AsyncSession,
        user_a: User,
        inventory_a: Inventory,
        item_b: InventoryItem,
    ) -> None:
        """create_lot with inventory_id should reject item not in that inventory."""
        with pytest.raises(ValueError, match="not found in inventory"):
            await create_lot(
                db_session,
                item_id=item_b.id,
                quantity=3,
                added_by_user_id=user_a.id,
                inventory_id=inventory_a.id,
            )

    @pytest.mark.asyncio
    async def test_create_lot_succeeds_for_own_inventory(
        self,
        db_session: AsyncSession,
        user_a: User,
        inventory_a: Inventory,
        item_a: InventoryItem,
    ) -> None:
        """create_lot should succeed when item belongs to the specified inventory."""
        lot = await create_lot(
            db_session,
            item_id=item_a.id,
            quantity=3,
            added_by_user_id=user_a.id,
            inventory_id=inventory_a.id,
        )
        assert lot is not None
        assert lot.quantity == 3
