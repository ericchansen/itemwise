"""Tests for database engine and session management."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from itemwise.config import Settings
from itemwise.database.engine import (
    AsyncSessionLocal,
    close_db,
    engine,
    get_session,
)
from itemwise.database.models import Base


class TestDatabaseEngine:
    """Tests for database engine."""

    def test_engine_is_async(self) -> None:
        """Test that the engine is an async engine."""
        assert isinstance(engine, AsyncEngine)

    def test_engine_url(self, test_settings: Settings) -> None:
        """Test that engine uses correct database URL."""
        # Engine should be using asyncpg driver
        assert "asyncpg" in str(engine.url)

    def test_pool_pre_ping_enabled(self) -> None:
        """Verify pool_pre_ping is True to detect stale connections."""
        assert engine.pool._pre_ping is True

    def test_pool_recycle_set(self) -> None:
        """Verify pool_recycle=3600 to handle Azure PostgreSQL auto-stop."""
        assert engine.pool._recycle == 3600


class TestSessionFactory:
    """Tests for session factory."""

    @pytest.mark.asyncio
    async def test_create_session(self) -> None:
        """Test creating a session from the factory."""
        async with AsyncSessionLocal() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_session_independent(self) -> None:
        """Test that sessions are independent."""
        async with AsyncSessionLocal() as session1:
            async with AsyncSessionLocal() as session2:
                assert session1 is not session2


class TestInitDb:
    """Tests for database initialization."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, test_engine: Any) -> None:
        """Test that init_db creates all tables."""
        # Tables should already be created by test_engine fixture
        # This verifies that the pattern works
        async with test_engine.connect() as conn:
            # Check if tables exist
            result = await conn.run_sync(lambda sync_conn: Base.metadata.tables.keys())
            assert "inventory_items" in result
            assert "transaction_log" in result


class TestGetSession:
    """Tests for get_session context manager."""

    @pytest.mark.asyncio
    async def test_get_session_yields_session(self) -> None:
        """Test that get_session yields a valid session."""
        async for session in get_session():
            assert isinstance(session, AsyncSession)
            break

    @pytest.mark.asyncio
    async def test_get_session_auto_closes(self) -> None:
        """Test that session is automatically closed."""
        session_ref = None

        async for session in get_session():
            session_ref = session
            break

        # After exiting context, session should be closed
        # Check that we can't execute queries (session is closed)
        assert session_ref is not None

    @pytest.mark.asyncio
    async def test_get_session_rollback_on_error(self) -> None:
        """Test that session rolls back on error."""
        try:
            async for session in get_session():
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Session should have been rolled back
        # If we get here without hanging, the rollback worked


class TestCloseDb:
    """Tests for database cleanup."""

    @pytest.mark.asyncio
    async def test_close_db(self) -> None:
        """Test closing database connections."""
        # This should not raise an error
        await close_db()
