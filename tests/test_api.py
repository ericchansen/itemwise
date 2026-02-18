"""Tests for FastAPI REST API endpoints."""

from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.api import app
from itemwise.auth import create_access_token, create_refresh_token, hash_password
from itemwise.database.crud import create_user
from itemwise.database.models import User

# Password meeting all complexity requirements
VALID_PASSWORD = "TestPass1!"


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
async def known_user(db_session: AsyncSession) -> User:
    """Create a user with a known password for login tests."""
    hashed = hash_password(VALID_PASSWORD)
    return await create_user(db_session, "apiuser@example.com", hashed)


# ===== Health =====


class TestHealth:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_healthy(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["dependencies"]["database"] == "healthy"


# ===== Auth: Register =====


class TestRegister:
    """Tests for POST /api/auth/register."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/register",
            json={"email": "brand_new@example.com", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, client: AsyncClient, known_user: User
    ) -> None:
        resp = await client.post(
            "/api/auth/register",
            json={"email": known_user.email, "password": VALID_PASSWORD},
        )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient) -> None:
        # 8 chars but no uppercase / digit / special → fails complexity check
        resp = await client.post(
            "/api/auth/register",
            json={"email": "weak@example.com", "password": "abcdefgh"},
        )
        assert resp.status_code == 400


# ===== Auth: Login =====


class TestLogin:
    """Tests for POST /api/auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(
        self, client: AsyncClient, known_user: User
    ) -> None:
        resp = await client.post(
            "/api/auth/login",
            data={"username": known_user.email, "password": VALID_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, client: AsyncClient, known_user: User
    ) -> None:
        resp = await client.post(
            "/api/auth/login",
            data={"username": known_user.email, "password": "WrongPass1!"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/login",
            data={"username": "nobody@example.com", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 401


# ===== Auth: Refresh =====


class TestRefresh:
    """Tests for POST /api/auth/refresh."""

    @pytest.mark.asyncio
    async def test_refresh_valid_token(
        self, client: AsyncClient, known_user: User
    ) -> None:
        refresh = create_refresh_token(known_user.id, known_user.email)
        resp = await client.post(
            "/api/auth/refresh", json={"refresh_token": refresh}
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/refresh", json={"refresh_token": "bad.token.here"}
        )
        assert resp.status_code == 401


# ===== Auth: Me =====


class TestMe:
    """Tests for GET /api/auth/me."""

    @pytest.mark.asyncio
    async def test_me_authenticated(
        self, client: AsyncClient, known_user: User
    ) -> None:
        resp = await client.get(
            "/api/auth/me",
            headers=auth_header(known_user.id, known_user.email),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == known_user.id
        assert data["email"] == known_user.email

    @pytest.mark.asyncio
    async def test_me_no_token(self, client: AsyncClient) -> None:
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401


# ===== Items: Create =====


class TestItemCreate:
    """Tests for POST /api/items."""

    @pytest.mark.asyncio
    async def test_create_item(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.post(
            "/api/items",
            json={"name": "Chicken", "quantity": 5, "category": "meat"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["item"]["name"] == "Chicken"
        assert data["item"]["quantity"] == 5

    @pytest.mark.asyncio
    async def test_create_item_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/items",
            json={"name": "X", "quantity": 1, "category": "test"},
        )
        assert resp.status_code == 401


# ===== Items: List =====


class TestItemList:
    """Tests for GET /api/items."""

    @pytest.mark.asyncio
    async def test_list_items_empty(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.get("/api/items", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["items"] == []

    @pytest.mark.asyncio
    async def test_list_items_with_data(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        await client.post(
            "/api/items",
            json={"name": "A", "quantity": 1, "category": "x"},
            headers=headers,
        )
        await client.post(
            "/api/items",
            json={"name": "B", "quantity": 2, "category": "y"},
            headers=headers,
        )
        resp = await client.get("/api/items", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    @pytest.mark.asyncio
    async def test_list_items_no_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/items")
        assert resp.status_code == 401


# ===== Items: Get =====


class TestItemGet:
    """Tests for GET /api/items/{id}."""

    @pytest.mark.asyncio
    async def test_get_item(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        create_resp = await client.post(
            "/api/items",
            json={"name": "Test", "quantity": 1, "category": "test"},
            headers=headers,
        )
        item_id = create_resp.json()["item"]["id"]

        resp = await client.get(f"/api/items/{item_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test"

    @pytest.mark.asyncio
    async def test_get_item_not_found(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.get("/api/items/99999", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_item_no_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/items/1")
        assert resp.status_code == 401


# ===== Items: Update =====


class TestItemUpdate:
    """Tests for PUT /api/items/{id}."""

    @pytest.mark.asyncio
    async def test_update_item(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        create_resp = await client.post(
            "/api/items",
            json={"name": "Old", "quantity": 1, "category": "test"},
            headers=headers,
        )
        item_id = create_resp.json()["item"]["id"]

        resp = await client.put(
            f"/api/items/{item_id}",
            json={"name": "New", "quantity": 10},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["item"]["name"] == "New"
        assert resp.json()["item"]["quantity"] == 10

    @pytest.mark.asyncio
    async def test_update_item_not_found(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.put(
            "/api/items/99999", json={"name": "X"}, headers=headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_item_no_auth(self, client: AsyncClient) -> None:
        resp = await client.put("/api/items/1", json={"name": "X"})
        assert resp.status_code == 401


# ===== Items: Delete =====


class TestItemDelete:
    """Tests for DELETE /api/items/{id}."""

    @pytest.mark.asyncio
    async def test_delete_item(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        create_resp = await client.post(
            "/api/items",
            json={"name": "ToDelete", "quantity": 1, "category": "test"},
            headers=headers,
        )
        item_id = create_resp.json()["item"]["id"]

        resp = await client.delete(
            f"/api/items/{item_id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    @pytest.mark.asyncio
    async def test_delete_item_not_found(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.delete("/api/items/99999", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_item_no_auth(self, client: AsyncClient) -> None:
        resp = await client.delete("/api/items/1")
        assert resp.status_code == 401


# ===== Search =====


class TestSearch:
    """Tests for GET /api/search."""

    @pytest.mark.asyncio
    async def test_search_returns_results(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        await client.post(
            "/api/items",
            json={
                "name": "Chicken Breast",
                "quantity": 2,
                "category": "meat",
            },
            headers=headers,
        )
        resp = await client.get("/api/search?q=chicken", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "chicken"
        assert isinstance(data["count"], int)

    @pytest.mark.asyncio
    async def test_search_no_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/search?q=test")
        assert resp.status_code == 401


# ===== Locations =====


class TestLocations:
    """Tests for /api/locations endpoints."""

    @pytest.mark.asyncio
    async def test_list_locations_empty(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.get("/api/locations", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_create_location(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.post(
            "/api/locations",
            json={"name": "Pantry", "description": "Kitchen pantry"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["location"]["name"] == "Pantry"

    @pytest.mark.asyncio
    async def test_list_locations_after_create(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        await client.post(
            "/api/locations",
            json={"name": "Fridge"},
            headers=headers,
        )
        resp = await client.get("/api/locations", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    @pytest.mark.asyncio
    async def test_create_location_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/locations", json={"name": "X"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_locations_no_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/locations")
        assert resp.status_code == 401
