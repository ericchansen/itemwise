"""Tests for password reset functionality."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from itemwise.auth import (
    create_reset_token,
    hash_password,
    verify_reset_token,
)


class TestResetTokens:
    """Tests for reset token creation and verification."""

    def test_create_and_verify_reset_token(self) -> None:
        """A valid reset token round-trips correctly."""
        token = create_reset_token("user@example.com")
        email = verify_reset_token(token)
        assert email == "user@example.com"

    def test_verify_invalid_token_returns_none(self) -> None:
        """An invalid token string returns None."""
        assert verify_reset_token("not-a-valid-token") is None

    def test_verify_expired_token_returns_none(self) -> None:
        """An expired reset token returns None."""
        from itemwise.auth import ALGORITHM, SECRET_KEY
        import jwt
        from datetime import datetime, timezone

        payload = {
            "sub": "user@example.com",
            "exp": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "type": "password_reset",
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        assert verify_reset_token(token) is None

    def test_access_token_rejected_as_reset_token(self) -> None:
        """An access token must not be accepted as a reset token."""
        from itemwise.auth import create_access_token

        token = create_access_token(user_id=1, email="user@example.com")
        assert verify_reset_token(token) is None

    def test_refresh_token_rejected_as_reset_token(self) -> None:
        """A refresh token must not be accepted as a reset token."""
        from itemwise.auth import create_refresh_token

        token = create_refresh_token(user_id=1, email="user@example.com")
        assert verify_reset_token(token) is None


@pytest.fixture
def _mock_db_user():
    """Mock user returned by get_user_by_email."""
    user = type("User", (), {"id": 1, "email": "test@example.com", "hashed_password": hash_password("Old@Pass1")})()
    return user


@pytest.fixture
def _patch_session(_mock_db_user):
    """Patch AsyncSessionLocal and get_user_by_email for API tests."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit = AsyncMock()

    with patch("itemwise.api.AsyncSessionLocal", return_value=mock_session):
        with patch("itemwise.api.get_user_by_email", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _mock_db_user
            yield mock_get, _mock_db_user


@pytest.fixture
def _patch_session_no_user():
    """Patch AsyncSessionLocal with no user found."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("itemwise.api.AsyncSessionLocal", return_value=mock_session):
        with patch("itemwise.api.get_user_by_email", new_callable=AsyncMock, return_value=None):
            yield


class TestForgotPasswordEndpoint:
    """Tests for POST /api/auth/forgot-password."""

    @pytest.mark.anyio
    async def test_returns_200_for_existing_email(self, _patch_session) -> None:
        """Returns 200 and sends email when user exists."""
        from itemwise.api import app

        with patch("itemwise.email_service.send_password_reset_email", return_value=True) as mock_send:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.post("/api/auth/forgot-password", json={"email": "test@example.com"})
        assert res.status_code == 200
        mock_send.assert_called_once()

    @pytest.mark.anyio
    async def test_returns_200_for_nonexistent_email(self, _patch_session_no_user) -> None:
        """Returns 200 even when email is not found (no enumeration)."""
        from itemwise.api import app

        with patch("itemwise.email_service.send_password_reset_email") as mock_send:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
        assert res.status_code == 200
        mock_send.assert_not_called()


class TestResetPasswordEndpoint:
    """Tests for POST /api/auth/reset-password."""

    @pytest.mark.anyio
    async def test_valid_token_changes_password(self, _patch_session) -> None:
        """A valid token allows the password to be changed."""
        from itemwise.api import app

        token = create_reset_token("test@example.com")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "NewSecure@1"},
            )
        assert res.status_code == 200
        assert res.json()["message"] == "Password has been reset successfully"

    @pytest.mark.anyio
    async def test_invalid_token_returns_400(self) -> None:
        """An invalid token returns 400."""
        from itemwise.api import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/auth/reset-password",
                json={"token": "bad-token", "new_password": "NewSecure@1"},
            )
        assert res.status_code == 400
        assert "Invalid or expired" in res.json()["detail"]

    @pytest.mark.anyio
    async def test_expired_token_returns_400(self) -> None:
        """An expired token returns 400."""
        from itemwise.auth import ALGORITHM, SECRET_KEY
        import jwt
        from datetime import datetime, timezone

        from itemwise.api import app

        payload = {
            "sub": "test@example.com",
            "exp": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "type": "password_reset",
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "NewSecure@1"},
            )
        assert res.status_code == 400

    @pytest.mark.anyio
    async def test_weak_password_returns_400(self, _patch_session) -> None:
        """A weak password is rejected even with a valid token."""
        from itemwise.api import app

        token = create_reset_token("test@example.com")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "weak"},
            )
        assert res.status_code in (400, 422)
