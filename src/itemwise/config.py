"""Configuration settings for the application."""

from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database configuration
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "inventory"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Application settings
    debug: bool = False

    # Azure OpenAI embedding deployment name
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # Azure Communication Services (for invite emails)
    azure_communication_connection_string: str = ""
    azure_communication_sender: str = ""

    @property
    def database_url(self) -> str:
        """Construct the database URL for async PostgreSQL connection."""
        base_url = (
            f"postgresql+asyncpg://{quote(self.postgres_user, safe='')}:{quote(self.postgres_password, safe='')}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        # Add SSL for Azure PostgreSQL
        if "azure" in self.postgres_host.lower() or "postgres.database" in self.postgres_host.lower():
            return f"{base_url}?ssl=require"
        return base_url


# Global settings instance
settings = Settings()
