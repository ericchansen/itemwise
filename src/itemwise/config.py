"""Configuration settings for the application."""

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

    # Optional: OpenAI API key for embeddings
    openai_api_key: str | None = None

    @property
    def database_url(self) -> str:
        """Construct the database URL for async PostgreSQL connection."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


# Global settings instance
settings = Settings()
