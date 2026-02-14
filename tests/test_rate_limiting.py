"""Tests for API rate limiting."""

from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.api import app, limiter
from itemwise.auth import create_access_token, hash_password
from itemwise.database.crud import create_user
from itemwise.database.models import User

VALID_PASSWORD = "TestPass1!"


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Reset rate limiter state between tests."""
    original = limiter._limiter
    app.state.limiter = limiter
    limiter.reset()
    yield
    limiter._limiter = original


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
    token = create_access_token(user_id, email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def known_user(db_session: AsyncSession) -> User:
    """Create a user with a known password for login tests."""
    hashed = hash_password(VALID_PASSWORD)
    return await create_user(db_session, "ratelimit@example.com", hashed)


class TestRegisterRateLimit:
    """Rate limiting on POST /api/auth/register."""

    @pytest.mark.asyncio
    async def test_register_allows_within_limit(self, client: AsyncClient) -> None:
        """First few requests should succeed (201 or 400, not 429)."""
        for i in range(3):
            resp = await client.post(
                "/api/auth/register",
                json={"email": f"user{i}@test.com", "password": VALID_PASSWORD},
            )
            assert resp.status_code != 429, f"Request {i+1} should not be rate limited"

    @pytest.mark.asyncio
    async def test_register_rate_limited(self, client: AsyncClient) -> None:
        """Exceeding 5/minute should return 429."""
        for i in range(6):
            resp = await client.post(
                "/api/auth/register",
                json={"email": f"spam{i}@test.com", "password": VALID_PASSWORD},
            )
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Rate limit exceeded"
        assert "Retry-After" in resp.headers


class TestLoginRateLimit:
    """Rate limiting on POST /api/auth/login."""

    @pytest.mark.asyncio
    async def test_login_allows_within_limit(self, client: AsyncClient, known_user: User) -> None:
        """Requests within limit should not be rate limited."""
        for i in range(5):
            resp = await client.post(
                "/api/auth/login",
                data={"username": known_user.email, "password": VALID_PASSWORD},
            )
            assert resp.status_code != 429, f"Request {i+1} should not be rate limited"

    @pytest.mark.asyncio
    async def test_login_rate_limited(self, client: AsyncClient, known_user: User) -> None:
        """Exceeding 10/minute should return 429."""
        for i in range(11):
            resp = await client.post(
                "/api/auth/login",
                data={"username": known_user.email, "password": VALID_PASSWORD},
            )
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Rate limit exceeded"
        assert "Retry-After" in resp.headers


class TestChatRateLimit:
    """Rate limiting on POST /api/chat."""

    @pytest.mark.asyncio
    async def test_chat_allows_within_limit(self, client: AsyncClient, known_user: User) -> None:
        """Requests within limit should not be rate limited."""
        headers = auth_header(known_user.id, known_user.email)
        for i in range(5):
            resp = await client.post(
                "/api/chat",
                json={"message": f"test message {i}"},
                headers=headers,
            )
            # May fail for other reasons (no inventory etc.) but should NOT be 429
            assert resp.status_code != 429, f"Request {i+1} should not be rate limited"

    @pytest.mark.asyncio
    async def test_chat_rate_limited(self, client: AsyncClient, known_user: User) -> None:
        """Exceeding 20/minute should return 429."""
        headers = auth_header(known_user.id, known_user.email)
        last_status = None
        for i in range(21):
            resp = await client.post(
                "/api/chat",
                json={"message": f"msg {i}"},
                headers=headers,
            )
            last_status = resp.status_code
            if last_status == 429:
                break
        assert last_status == 429
        assert resp.json()["detail"] == "Rate limit exceeded"
        assert "Retry-After" in resp.headers
