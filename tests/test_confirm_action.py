"""Tests for the chat confirm action endpoint (destructive operation confirmation)."""

import time as time_module
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from itemwise.api import ChatResponse, _pending_actions, _store_pending_action, app
from itemwise.auth import create_access_token, hash_password
from itemwise.database.crud import create_user
from itemwise.database.models import User


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
    token = create_access_token(user_id, email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def known_user(db_session: AsyncSession) -> User:
    hashed = hash_password(VALID_PASSWORD)
    return await create_user(db_session, "confirm_test@example.com", hashed)


@pytest.fixture(autouse=True)
def clear_pending_actions() -> Any:
    """Ensure pending actions dict is clean before each test."""
    _pending_actions.clear()
    yield
    _pending_actions.clear()


class TestConfirmActionEndpoint:
    """Tests for POST /api/v1/chat/confirm."""

    @pytest.mark.asyncio
    async def test_confirm_action_executes_removal(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        # Store a pending remove action
        action_id = await _store_pending_action(
            known_user.id, "remove_item",
            {"item_id": 42, "quantity": 2, "lot_id": None},
            "Remove 2 × Frozen Pizza", inventory_id=1,
        )

        # Mock _execute_remove_item so we don't need a real item in DB
        mock_executor = AsyncMock(return_value="Removed 2 Frozen Pizza.")
        with patch.dict("itemwise.api._ACTION_EXECUTORS", {"remove_item": mock_executor}):
            resp = await client.post(
                "/api/v1/chat/confirm",
                json={"action_id": action_id, "confirmed": True},
                headers=headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "confirmed"
        assert "Frozen Pizza" in data["response"]
        mock_executor.assert_called_once_with(1, item_id=42, quantity=2, lot_id=None)

    @pytest.mark.asyncio
    async def test_reject_action_cancels(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        action_id = await _store_pending_action(
            known_user.id, "remove_item",
            {"item_id": 999, "quantity": 1, "lot_id": None},
            "Remove 1 × Something", inventory_id=1,
        )

        resp = await client.post(
            "/api/v1/chat/confirm",
            json={"action_id": action_id, "confirmed": False},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "cancelled"
        assert "cancelled" in data["response"].lower()

    @pytest.mark.asyncio
    async def test_expired_action_returns_410(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        action_id = await _store_pending_action(
            known_user.id, "remove_item",
            {"item_id": 1, "quantity": 1, "lot_id": None},
            "Remove 1 × Item", inventory_id=1,
        )
        # Manually expire the action
        _pending_actions[action_id]["expires_at"] = time_module.time() - 10

        resp = await client.post(
            "/api/v1/chat/confirm",
            json={"action_id": action_id, "confirmed": True},
            headers=headers,
        )
        assert resp.status_code == 410

    @pytest.mark.asyncio
    async def test_not_found_action_returns_404(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.post(
            "/api/v1/chat/confirm",
            json={"action_id": "nonexistent_id", "confirmed": True},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_other_user_cannot_confirm(
        self, client: AsyncClient, known_user: User
    ) -> None:
        # Store action for known_user
        action_id = await _store_pending_action(
            known_user.id, "remove_item",
            {"item_id": 1, "quantity": 1, "lot_id": None},
            "Remove 1 × Item", inventory_id=1,
        )

        # Use a different user_id for the "other" user (no DB needed)
        other_user_id = known_user.id + 999
        other_headers = auth_header(other_user_id, "other_confirm@example.com")

        resp = await client.post(
            "/api/v1/chat/confirm",
            json={"action_id": action_id, "confirmed": True},
            headers=other_headers,
        )
        assert resp.status_code == 403
        # Action should still exist for the real owner
        assert action_id in _pending_actions


class TestStorePendingAction:
    """Tests for the _store_pending_action helper."""

    @pytest.mark.asyncio
    async def test_returns_unique_ids(self) -> None:
        id1 = await _store_pending_action(1, "remove_item", {}, "test1", 1)
        id2 = await _store_pending_action(1, "remove_item", {}, "test2", 1)
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_cleanup_expired(self) -> None:
        # Store an expired action
        old_id = await _store_pending_action(1, "remove_item", {}, "old", 1)
        _pending_actions[old_id]["expires_at"] = time_module.time() - 10

        # Store a new action, which triggers cleanup
        await _store_pending_action(1, "remove_item", {}, "new", 1)
        assert old_id not in _pending_actions


class TestChatResponseModel:
    """Tests for the ChatResponse model with pending_action field."""

    def test_pending_action_optional(self) -> None:
        resp = ChatResponse(response="Hello")
        assert resp.pending_action is None

    def test_pending_action_present(self) -> None:
        resp = ChatResponse(
            response="Confirm?",
            action="confirmation_required",
            pending_action={"action_id": "abc123", "description": "Remove 2 × Pizza"},
        )
        assert resp.pending_action is not None
        assert resp.pending_action["action_id"] == "abc123"

    def test_backward_compatible(self) -> None:
        resp = ChatResponse(response="OK", action="ai_response", data={"foo": "bar"})
        assert resp.pending_action is None
        assert resp.data == {"foo": "bar"}
