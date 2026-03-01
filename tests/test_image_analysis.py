"""Tests for image analysis endpoints and ai_client.analyze_image."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

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
    limiter.reset()
    yield


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
async def known_user(db_session: AsyncSession) -> User:
    hashed = hash_password(VALID_PASSWORD)
    return await create_user(db_session, "image_test@example.com", hashed)


class TestAnalyzeImageFunction:
    """Tests for ai_client.analyze_image."""

    def test_analyze_image_parses_json_response(self) -> None:
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps([
            {"name": "chicken breast", "quantity": 2, "category": "meat"},
            {"name": "broccoli", "quantity": 1, "category": "produce"},
        ])
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            from itemwise.ai_client import analyze_image
            items = analyze_image(b"\x89PNG\r\n", "image/png")

        assert len(items) == 2
        assert items[0]["name"] == "chicken breast"
        assert items[1]["quantity"] == 1

    def test_analyze_image_handles_markdown_fences(self) -> None:
        mock_choice = MagicMock()
        mock_choice.message.content = '```json\n[{"name": "milk", "quantity": 1, "category": "dairy"}]\n```'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            from itemwise.ai_client import analyze_image
            items = analyze_image(b"\x89PNG\r\n", "image/png")

        assert len(items) == 1
        assert items[0]["name"] == "milk"

    def test_analyze_image_returns_empty_for_invalid_json(self) -> None:
        mock_choice = MagicMock()
        mock_choice.message.content = "I can't parse this image"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            from itemwise.ai_client import analyze_image
            items = analyze_image(b"\x89PNG\r\n", "image/png")

        assert items == []

    def test_analyze_image_returns_empty_for_non_list(self) -> None:
        mock_choice = MagicMock()
        mock_choice.message.content = '{"name": "single item"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            from itemwise.ai_client import analyze_image
            items = analyze_image(b"\x89PNG\r\n", "image/png")

        assert items == []

    def test_analyze_image_passes_user_hint(self) -> None:
        mock_choice = MagicMock()
        mock_choice.message.content = "[]"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            from itemwise.ai_client import analyze_image
            analyze_image(b"\x89PNG\r\n", "image/png", user_hint="These are from Costco")

        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]
        assert user_msg["content"][0]["type"] == "text"
        assert "Costco" in user_msg["content"][0]["text"]


class TestChatImageEndpoint:
    """Tests for POST /api/v1/chat/image."""

    @pytest.mark.asyncio
    async def test_rejects_unsupported_file_type(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.post(
            "/api/v1/chat/image",
            files={"image": ("test.txt", b"hello", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Unsupported image type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_rejects_empty_file(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.post(
            "/api/v1/chat/image",
            files={"image": ("empty.png", b"", "image/png")},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Empty image" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_error_without_openai(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        with patch("itemwise.api.AZURE_OPENAI_ENABLED", False):
            resp = await client.post(
                "/api/v1/chat/image",
                files={"image": ("test.png", b"\x89PNG\r\n", "image/png")},
                headers=headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "error"
        assert "requires Azure OpenAI" in data["response"]

    @pytest.mark.asyncio
    async def test_successful_image_analysis(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        mock_items = [
            {"name": "frozen pizza", "quantity": 2, "category": "frozen"},
            {"name": "ice cream", "quantity": 1, "category": "frozen"},
        ]
        with patch("itemwise.api.AZURE_OPENAI_ENABLED", True), \
             patch("itemwise.ai_client.analyze_image", return_value=mock_items):
            resp = await client.post(
                "/api/v1/chat/image",
                files={"image": ("test.png", b"\x89PNG\r\n", "image/png")},
                headers=headers,
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_image_analysis_with_items(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        mock_items = [
            {"name": "frozen pizza", "quantity": 2, "category": "frozen"},
        ]

        # Patch where analyze_image is called (local import in endpoint)
        with patch("itemwise.api.AZURE_OPENAI_ENABLED", True), \
             patch("itemwise.ai_client.analyze_image", return_value=mock_items):
            resp = await client.post(
                "/api/v1/chat/image",
                files={"image": ("test.png", b"\x89PNG\r\n", "image/png")},
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "items_identified"
        assert len(data["items"]) == 1
        assert "frozen pizza" in data["response"]

    @pytest.mark.asyncio
    async def test_image_analysis_no_items_found(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)

        with patch("itemwise.api.AZURE_OPENAI_ENABLED", True), \
             patch("itemwise.ai_client.analyze_image", return_value=[]):
            resp = await client.post(
                "/api/v1/chat/image",
                files={"image": ("test.png", b"\x89PNG\r\n", "image/png")},
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "ai_response"
        assert len(data["items"]) == 0

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/chat/image",
            files={"image": ("test.png", b"\x89PNG\r\n", "image/png")},
        )
        assert resp.status_code == 401


class TestChatImageAddEndpoint:
    """Tests for POST /api/v1/chat/image/add."""

    @pytest.mark.asyncio
    async def test_add_items_from_image(
        self, client: AsyncClient, known_user: User, db_session: AsyncSession
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)

        items = [
            {"name": "chicken breast", "quantity": 2, "category": "meat"},
            {"name": "broccoli", "quantity": 3, "category": "produce"},
        ]

        with patch("itemwise.api.generate_embedding", return_value=[0.0] * 1536):
            resp = await client.post(
                "/api/v1/chat/image/add",
                json={"items": items, "location": "Freezer"},
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "ai_response"
        assert "2 item(s)" in data["response"]
        assert "chicken breast" in data["response"]
        assert "broccoli" in data["response"]

    @pytest.mark.asyncio
    async def test_requires_location(
        self, client: AsyncClient, known_user: User
    ) -> None:
        headers = auth_header(known_user.id, known_user.email)
        resp = await client.post(
            "/api/v1/chat/image/add",
            json={"items": [{"name": "test", "quantity": 1, "category": "general"}]},
            headers=headers,
        )
        # Missing location field should cause validation error
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/chat/image/add",
            json={"items": [], "location": "Pantry"},
        )
        assert resp.status_code == 401
