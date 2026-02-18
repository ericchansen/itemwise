"""Tests for CSRF double-submit cookie protection."""

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


@pytest_asyncio.fixture
async def known_user(db_session: AsyncSession) -> User:
    hashed = hash_password(VALID_PASSWORD)
    return await create_user(db_session, "csrfuser@example.com", hashed)


def _cookie_auth(user: User) -> dict[str, str]:
    """Return cookies simulating a cookie-based session with CSRF token."""
    token = create_access_token(user.id, user.email)
    return {"access_token": token, "csrf_token": "test-csrf-token-123"}


def _bearer_header(user: User) -> dict[str, str]:
    """Return Authorization header (no cookies)."""
    token = create_access_token(user.id, user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestCSRF:

    async def test_post_without_csrf_token_rejected(
        self, client: AsyncClient, known_user: User
    ) -> None:
        """POST with cookie auth but no CSRF token should be rejected."""
        cookies = _cookie_auth(known_user)
        client.cookies.set("access_token", cookies["access_token"])
        client.cookies.set("csrf_token", cookies["csrf_token"])
        # No X-CSRF-Token header
        resp = await client.post(
            "/api/v1/items",
            json={"name": "Test", "quantity": 1, "category": "food"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "CSRF token validation failed"

    async def test_post_with_valid_csrf_token_accepted(
        self, client: AsyncClient, known_user: User
    ) -> None:
        """POST with matching CSRF cookie and header should succeed."""
        cookies = _cookie_auth(known_user)
        csrf_token = cookies["csrf_token"]
        client.cookies.set("access_token", cookies["access_token"])
        client.cookies.set("csrf_token", csrf_token)
        resp = await client.post(
            "/api/v1/items",
            json={"name": "Test Item", "quantity": 1, "category": "food"},
            headers={"X-CSRF-Token": csrf_token},
        )
        # Should pass CSRF check (may be 200 or other, but NOT 403 CSRF)
        assert resp.status_code != 403

    async def test_get_requests_not_affected(
        self, client: AsyncClient, known_user: User
    ) -> None:
        """GET requests should not require CSRF token."""
        cookies = _cookie_auth(known_user)
        client.cookies.set("access_token", cookies["access_token"])
        # No CSRF cookie or header needed for GET
        resp = await client.get("/api/v1/items")
        assert resp.status_code != 403

    async def test_login_exempt_from_csrf(
        self, client: AsyncClient, known_user: User
    ) -> None:
        """Login endpoint should be exempt from CSRF validation."""
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "csrfuser@example.com", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 200
        # Should also set csrf_token cookie
        assert "csrf_token" in resp.cookies

    async def test_register_exempt_from_csrf(
        self, client: AsyncClient
    ) -> None:
        """Register endpoint should be exempt from CSRF validation."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "newcsrf@example.com", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 201
        assert "csrf_token" in resp.cookies

    async def test_csrf_not_enforced_for_bearer_token_auth(
        self, client: AsyncClient, known_user: User
    ) -> None:
        """Bearer token auth (no cookie) should not trigger CSRF check."""
        headers = _bearer_header(known_user)
        resp = await client.post(
            "/api/v1/items",
            json={"name": "Bearer Item", "quantity": 1, "category": "food"},
            headers=headers,
        )
        # No access_token cookie → CSRF skipped → should not get 403
        assert resp.status_code != 403

    async def test_mismatched_csrf_tokens_rejected(
        self, client: AsyncClient, known_user: User
    ) -> None:
        """Mismatched CSRF cookie and header should be rejected."""
        cookies = _cookie_auth(known_user)
        client.cookies.set("access_token", cookies["access_token"])
        client.cookies.set("csrf_token", "cookie-token-aaa")
        resp = await client.post(
            "/api/v1/items",
            json={"name": "Test", "quantity": 1, "category": "food"},
            headers={"X-CSRF-Token": "header-token-bbb"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "CSRF token validation failed"
