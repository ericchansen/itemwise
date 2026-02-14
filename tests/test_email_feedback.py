"""Tests for email delivery feedback in the add-member endpoint."""

from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.api import app
from itemwise.auth import create_access_token, hash_password
from itemwise.database.crud import create_inventory, create_user
from itemwise.database.models import User


@pytest.fixture
def patch_db(mock_session_factory: Any) -> Any:
    with patch("itemwise.api.AsyncSessionLocal", mock_session_factory):
        yield


@pytest_asyncio.fixture
async def client(patch_db: Any) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


def auth_header(user_id: int, email: str) -> dict[str, str]:
    token = create_access_token(user_id, email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def owner(db_session: AsyncSession) -> User:
    hashed = hash_password("TestPass1!")
    return await create_user(db_session, "owner@example.com", hashed)


@pytest_asyncio.fixture
async def inventory(db_session: AsyncSession, owner: User) -> Any:
    return await create_inventory(db_session, "Test Inventory", owner.id)


@pytest_asyncio.fixture
async def existing_user(db_session: AsyncSession) -> User:
    hashed = hash_password("TestPass1!")
    return await create_user(db_session, "member@example.com", hashed)


class TestEmailFeedbackExistingUser:
    """When adding an existing user, member is added regardless of email outcome."""

    @pytest.mark.asyncio
    async def test_added_with_email_success(
        self, client: AsyncClient, owner: User, inventory: Any, existing_user: User,
    ) -> None:
        with patch("itemwise.email_service.send_added_email", return_value=True):
            resp = await client.post(
                f"/api/inventories/{inventory.id}/members",
                json={"email": "member@example.com"},
                headers=auth_header(owner.id, owner.email),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "added"
        assert "email_warning" not in data

    @pytest.mark.asyncio
    async def test_added_with_email_failure_includes_warning(
        self, client: AsyncClient, owner: User, inventory: Any, existing_user: User,
    ) -> None:
        with patch("itemwise.email_service.send_added_email", return_value=False):
            resp = await client.post(
                f"/api/inventories/{inventory.id}/members",
                json={"email": "member@example.com"},
                headers=auth_header(owner.id, owner.email),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "added"
        assert "email_warning" in data
        assert "failed" in data["email_warning"].lower()
        assert data["member"]["user_id"] == existing_user.id


class TestEmailFeedbackNewUser:
    """When inviting a non-existing user, response depends on email outcome."""

    @pytest.mark.asyncio
    async def test_invite_email_success(
        self, client: AsyncClient, owner: User, inventory: Any,
    ) -> None:
        with patch("itemwise.email_service.send_invite_email", return_value=True):
            resp = await client.post(
                f"/api/inventories/{inventory.id}/members",
                json={"email": "newuser@example.com"},
                headers=auth_header(owner.id, owner.email),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "invited"

    @pytest.mark.asyncio
    async def test_invite_email_failure_returns_error(
        self, client: AsyncClient, owner: User, inventory: Any,
    ) -> None:
        with patch("itemwise.email_service.send_invite_email", return_value=False):
            resp = await client.post(
                f"/api/inventories/{inventory.id}/members",
                json={"email": "newuser@example.com"},
                headers=auth_header(owner.id, owner.email),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "invite_failed"
        assert "detail" in data
