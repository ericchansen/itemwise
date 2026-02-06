"""Tests for authentication and security configuration."""

import pytest

from itemwise.auth import (
    SecretKeyError,
    _get_secret_key,
    create_access_token,
    create_refresh_token,
    decode_access_token,
)


class TestGetSecretKey:
    """Tests for _get_secret_key function."""

    def test_returns_custom_secret_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Custom SECRET_KEY is returned when set."""
        monkeypatch.setenv("SECRET_KEY", "my-custom-secret-key")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("ENV", "development")
        assert _get_secret_key() == "my-custom-secret-key"

    def test_allows_default_key_in_debug_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default key is allowed when DEBUG=true."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("ENV", "development")
        # Should not raise, returns default key
        key = _get_secret_key()
        assert key == "dev-secret-key-change-in-production"

    def test_raises_error_in_production_without_secret_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises SecretKeyError in production without SECRET_KEY."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("ENV", "production")
        with pytest.raises(SecretKeyError) as exc_info:
            _get_secret_key()
        assert "SECRET_KEY must be set" in str(exc_info.value)

    def test_raises_error_with_debug_false_no_env_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises SecretKeyError when DEBUG=false even without ENV=production."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with pytest.raises(SecretKeyError):
            _get_secret_key()

    def test_accepts_custom_key_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Custom SECRET_KEY works in production."""
        monkeypatch.setenv("SECRET_KEY", "secure-production-key-abc123")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("ENV", "production")
        assert _get_secret_key() == "secure-production-key-abc123"

    def test_env_prod_also_triggers_production_check(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ENV=prod (short form) triggers production check."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("DEBUG", "true")  # Even with debug, prod env requires key
        monkeypatch.setenv("ENV", "prod")
        with pytest.raises(SecretKeyError):
            _get_secret_key()

    def test_jwt_secret_key_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JWT_SECRET_KEY takes precedence over SECRET_KEY."""
        monkeypatch.setenv("JWT_SECRET_KEY", "jwt-specific-key")
        monkeypatch.setenv("SECRET_KEY", "generic-key")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("ENV", "development")
        assert _get_secret_key() == "jwt-specific-key"


class TestDecodeAccessToken:
    """Tests for decode_access_token token type validation."""

    def test_accepts_valid_access_token(self) -> None:
        """A properly created access token is decoded successfully."""
        token = create_access_token(user_id=42, email="test@example.com")
        result = decode_access_token(token)
        assert result is not None
        assert result.user_id == 42
        assert result.email == "test@example.com"

    def test_rejects_refresh_token_as_access_token(self) -> None:
        """A refresh token must not be accepted as an access token."""
        token = create_refresh_token(user_id=42, email="test@example.com")
        result = decode_access_token(token)
        assert result is None

    def test_rejects_invalid_token(self) -> None:
        """An invalid token string returns None."""
        result = decode_access_token("not-a-valid-token")
        assert result is None
