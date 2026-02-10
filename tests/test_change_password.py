"""Tests for PUT /api/auth/password endpoint."""

from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.api import app
from itemwise.auth import create_access_token, hash_password
from itemwise.database.crud import create_user
from itemwise.database.models import User

VALID_PASSWORD = "TestPass1!"
NEW_VALID_PASSWORD = "NewPass2@"


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
    """Create a user with a known password for change-password tests."""
    hashed = hash_password(VALID_PASSWORD)
    return await create_user(db_session, "changepw@example.com", hashed)


class TestChangePassword:
    """Tests for PUT /api/auth/password."""

    @pytest.mark.asyncio
    async def test_change_password_success(
        self, client: AsyncClient, known_user: User
    ) -> None:
        resp = await client.put(
            "/api/auth/password",
            json={
                "current_password": VALID_PASSWORD,
                "new_password": NEW_VALID_PASSWORD,
            },
            headers=auth_header(known_user.id, known_user.email),
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Password updated successfully"

        # Verify login works with new password
        login_resp = await client.post(
            "/api/auth/login",
            data={"username": known_user.email, "password": NEW_VALID_PASSWORD},
        )
        assert login_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(
        self, client: AsyncClient, known_user: User
    ) -> None:
        resp = await client.put(
            "/api/auth/password",
            json={
                "current_password": "WrongPass1!",
                "new_password": NEW_VALID_PASSWORD,
            },
            headers=auth_header(known_user.id, known_user.email),
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_change_password_weak_new_password(
        self, client: AsyncClient, known_user: User
    ) -> None:
        resp = await client.put(
            "/api/auth/password",
            json={
                "current_password": VALID_PASSWORD,
                "new_password": "abcdefgh",
            },
            headers=auth_header(known_user.id, known_user.email),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_change_password_unauthenticated(
        self, client: AsyncClient
    ) -> None:
        resp = await client.put(
            "/api/auth/password",
            json={
                "current_password": VALID_PASSWORD,
                "new_password": NEW_VALID_PASSWORD,
            },
        )
        assert resp.status_code == 401
