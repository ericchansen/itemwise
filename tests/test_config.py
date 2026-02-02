"""Tests for configuration settings."""

import pytest

from itemwise.config import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self) -> None:
        """Test default configuration values."""
        # Note: In test environment, POSTGRES_DB is set to "inventory_test" in conftest
        # and POSTGRES_PORT may be set to 5433
        settings = Settings()

        assert settings.postgres_user == "postgres"
        assert settings.postgres_password == "postgres"
        # In test environment, this will be "inventory_test" due to conftest
        assert settings.postgres_db in ["inventory", "inventory_test"]
        assert settings.postgres_host == "localhost"
        assert settings.postgres_port in [5432, 5433]  # Allow both ports
        assert settings.debug is False
        assert settings.openai_api_key is None

    def test_database_url_construction(self) -> None:
        """Test that database URL is correctly constructed."""
        settings = Settings(
            postgres_user="testuser",
            postgres_password="testpass",
            postgres_db="testdb",
            postgres_host="testhost",
            postgres_port=5433,
        )

        expected_url = "postgresql+asyncpg://testuser:testpass@testhost:5433/testdb"
        assert settings.database_url == expected_url

    def test_custom_settings(self) -> None:
        """Test creating settings with custom values."""
        settings = Settings(
            postgres_user="custom_user",
            postgres_password="custom_pass",
            postgres_db="custom_db",
            postgres_host="custom_host",
            postgres_port=9999,
            debug=True,
            openai_api_key="sk-test-key",
        )

        assert settings.postgres_user == "custom_user"
        assert settings.postgres_password == "custom_pass"
        assert settings.postgres_db == "custom_db"
        assert settings.postgres_host == "custom_host"
        assert settings.postgres_port == 9999
        assert settings.debug is True
        assert settings.openai_api_key == "sk-test-key"

    def test_settings_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading settings from environment variables."""
        monkeypatch.setenv("POSTGRES_USER", "env_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "env_pass")
        monkeypatch.setenv("POSTGRES_DB", "env_db")
        monkeypatch.setenv("POSTGRES_HOST", "env_host")
        monkeypatch.setenv("POSTGRES_PORT", "7777")
        monkeypatch.setenv("DEBUG", "true")

        settings = Settings()

        assert settings.postgres_user == "env_user"
        assert settings.postgres_password == "env_pass"
        assert settings.postgres_db == "env_db"
        assert settings.postgres_host == "env_host"
        assert settings.postgres_port == 7777
        assert settings.debug is True

    def test_settings_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variable names are case-insensitive."""
        monkeypatch.setenv("postgres_user", "lower_user")
        monkeypatch.setenv("POSTGRES_DB", "upper_db")

        settings = Settings()

        assert settings.postgres_user == "lower_user"
        assert settings.postgres_db == "upper_db"

    def test_database_url_with_special_characters(self) -> None:
        """Test database URL with special characters in password."""
        settings = Settings(
            postgres_user="user",
            postgres_password="p@ss:word!",
            postgres_db="db",
        )

        # URL should still be constructed correctly
        assert "user" in settings.database_url
        assert "p@ss:word!" in settings.database_url
        assert "db" in settings.database_url
