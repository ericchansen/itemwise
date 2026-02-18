"""Tests for GET /health deep health-check endpoint."""

from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from itemwise.api import app


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


class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_200_with_healthy_db(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["dependencies"]["database"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_returns_503_when_db_unreachable(self) -> None:
        """When the database is unreachable, health returns 503 unhealthy."""

        class _FailSession:
            async def execute(self, _stmt: Any) -> None:
                raise ConnectionRefusedError("db down")

        class _FailFactory:
            def __call__(self) -> "_FailFactory":
                return self

            async def __aenter__(self) -> _FailSession:
                return _FailSession()

            async def __aexit__(self, *args: Any) -> bool:
                return False

        with patch("itemwise.api.AsyncSessionLocal", _FailFactory()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["dependencies"]["database"] == "unhealthy"
