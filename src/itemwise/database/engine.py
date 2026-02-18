"""Database engine and session management."""

import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings
from .models import Base

logger = logging.getLogger(__name__)

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initialize database tables.

    Creates all tables defined in the Base metadata.
    This should be called on application startup.
    """
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        # Create pgvector extension if not exists (required for embeddings)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session.

    Yields:
        AsyncSession: Database session for executing queries

    Example:
        async with get_session() as session:
            items = await session.execute(select(InventoryItem))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:  # Intentionally broad: must rollback on any error during session use
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Close database engine and all connections.

    This should be called on application shutdown.
    """
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Database connections closed")
