"""Pytest configuration and shared fixtures."""

import asyncio
import os
from collections.abc import Generator
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from itemwise.config import Settings
from itemwise.database.models import Base

# Set test environment variables
os.environ["POSTGRES_DB"] = "inventory_test"
os.environ["POSTGRES_PORT"] = os.environ.get("POSTGRES_PORT", "5433")  # Use 5433 for local testing


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        postgres_db="inventory_test",
        postgres_user="postgres",
        postgres_password="postgres",
        postgres_host="localhost",
        postgres_port=int(os.environ.get("POSTGRES_PORT", "5433")),
        debug=True,
    )


@pytest_asyncio.fixture(scope="function")
async def test_engine(test_settings: Settings) -> AsyncGenerator[Any, None]:
    """Create a test database engine."""
    engine = create_async_engine(
        test_settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )

    # Create pgvector extension and tables
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_item_data() -> dict[str, Any]:
    """Sample inventory item data for testing."""
    return {
        "name": "Test Chicken Breast",
        "quantity": 5,
        "category": "meat",
        "description": "Organic boneless chicken breast",
    }


@pytest.fixture
def sample_transaction_data() -> dict[str, Any]:
    """Sample transaction log data for testing."""
    return {
        "operation": "CREATE",
        "item_id": 1,
        "data": {"name": "Test Item", "quantity": 3},
        "status": "PENDING",
    }


class AsyncContextManagerMock:
    """Mock async context manager for testing."""

    def __init__(self, return_value: Any) -> None:
        self.return_value = return_value

    async def __aenter__(self) -> Any:
        return self.return_value

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        return False


@pytest.fixture
def mock_session_factory(db_session: AsyncSession) -> Any:
    """Create a mock session factory that returns the test session."""

    def factory() -> AsyncContextManagerMock:
        return AsyncContextManagerMock(db_session)

    return factory
