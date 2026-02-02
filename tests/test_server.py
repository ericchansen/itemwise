"""Tests for FastMCP server and tools."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.exceptions import ToolError
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

# Import the MCP server to get tool functions
from itemwise.server import add_item as add_item_tool
from itemwise.server import list_inventory as list_tool
from itemwise.server import remove_item as remove_tool
from itemwise.server import search_inventory as search_tool
from itemwise.server import update_item_tool as update_tool

# Get the actual functions from the tool wrappers
add_item = add_item_tool.fn
update_item_tool = update_tool.fn
remove_item = remove_tool.fn
list_inventory = list_tool.fn
search_inventory = search_tool.fn


class TestAddItem:
    """Tests for add_item tool."""

    @pytest.mark.asyncio
    async def test_add_item_success(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test successfully adding an item."""
        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            result = await add_item(
                name="Test Chicken",
                quantity=5,
                category="meat",
                description="Fresh chicken breast",
            )

            assert result["status"] == "success"
            assert "Test Chicken" in result["message"]
            assert result["item_id"] is not None
            assert result["quantity"] == 5

    @pytest.mark.asyncio
    async def test_add_item_without_description(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test adding an item without description."""
        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            result = await add_item(
                name="Test Item",
                quantity=1,
                category="test",
                description="",
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_add_item_logs_transaction(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test that adding an item logs a transaction."""
        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            await add_item(
                name="Test Item",
                quantity=1,
                category="test",
            )

            # Verify transaction was logged
            from itemwise.database.crud import get_transaction_logs

            logs = await get_transaction_logs(db_session)

            assert len(logs) > 0
            assert logs[0].operation == "CREATE"

    @pytest.mark.asyncio
    async def test_add_item_database_error(self) -> None:
        """Test handling of database errors."""

        def error_factory() -> Any:
            async def raise_error() -> None:
                raise Exception("DB Error")

            class ErrorContextManager:
                async def __aenter__(self) -> None:
                    raise Exception("DB Error")

                async def __aexit__(self, *args: object) -> bool:
                    return False

            return ErrorContextManager()

        with patch("itemwise.server.AsyncSessionLocal", error_factory):

            with pytest.raises(ToolError) as exc_info:
                await add_item(
                    name="Test",
                    quantity=1,
                    category="test",
                )

            assert "Failed to add item" in str(exc_info.value)


class TestUpdateItemTool:
    """Tests for update_item_tool."""

    @pytest.mark.asyncio
    async def test_update_item_success(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test successfully updating an item."""
        from itemwise.database.crud import create_item

        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            # Create an item first
            item = await create_item(db_session, "Original", 5, "test")

            result = await update_item_tool(
                item_id=item.id,
                name="Updated Name",
                quantity=10,
            )

            assert result["status"] == "success"
            assert result["item"]["name"] == "Updated Name"
            assert result["item"]["quantity"] == 10

    @pytest.mark.asyncio
    async def test_update_item_not_found(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test updating a non-existent item."""
        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            with pytest.raises(ToolError) as exc_info:
                await update_item_tool(
                    item_id=99999,
                    name="Test",
                )

            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_item_partial(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test updating only some fields."""
        from itemwise.database.crud import create_item

        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            item = await create_item(db_session, "Original", 5, "test")

            result = await update_item_tool(
                item_id=item.id,
                quantity=10,
            )

            assert result["item"]["name"] == "Original"
            assert result["item"]["quantity"] == 10


class TestRemoveItem:
    """Tests for remove_item tool."""

    @pytest.mark.asyncio
    async def test_remove_item_success(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test successfully removing an item."""
        from itemwise.database.crud import create_item

        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            item = await create_item(db_session, "To Delete", 1, "test")

            result = await remove_item(item_id=item.id)

            assert result["status"] == "success"
            assert "To Delete" in result["message"]

    @pytest.mark.asyncio
    async def test_remove_item_not_found(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test removing a non-existent item."""
        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            with pytest.raises(ToolError) as exc_info:
                await remove_item(item_id=99999)

            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_remove_item_logs_transaction(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test that removing an item logs a transaction."""
        from itemwise.database.crud import create_item, get_transaction_logs

        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            item = await create_item(db_session, "To Delete", 1, "test")
            await remove_item(item_id=item.id)

            logs = await get_transaction_logs(db_session)
            delete_logs = [log for log in logs if log.operation == "DELETE"]

            assert len(delete_logs) > 0


class TestListInventory:
    """Tests for list_inventory tool."""

    @pytest.mark.asyncio
    async def test_list_all_items(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test listing all inventory items."""
        from itemwise.database.crud import create_item

        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            await create_item(db_session, "Item 1", 1, "meat")
            await create_item(db_session, "Item 2", 2, "vegetables")

            result = await list_inventory()

            assert result["status"] == "success"
            assert result["count"] == 2
            assert result["filters"]["category"] == "all"
            assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_items_by_category(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test listing items filtered by category."""
        from itemwise.database.crud import create_item

        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            await create_item(db_session, "Chicken", 1, "meat")
            await create_item(db_session, "Peas", 2, "vegetables")

            result = await list_inventory(category="meat")

            assert result["status"] == "success"
            assert result["count"] == 1
            assert result["filters"]["category"] == "meat"
            assert result["items"][0]["name"] == "Chicken"

    @pytest.mark.asyncio
    async def test_list_empty_inventory(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test listing when inventory is empty."""
        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            result = await list_inventory()

            assert result["status"] == "success"
            assert result["count"] == 0
            assert result["items"] == []


class TestSearchInventory:
    """Tests for search_inventory tool."""

    @pytest.mark.asyncio
    async def test_search_inventory_success(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test searching inventory."""
        from itemwise.database.crud import create_item

        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            await create_item(db_session, "Chicken Breast", 1, "meat")
            await create_item(db_session, "Frozen Peas", 2, "vegetables")

            result = await search_inventory(query="chicken")

            assert result["status"] == "success"
            assert result["query"] == "chicken"
            assert result["count"] >= 1
            assert len(result["results"]) >= 1

    @pytest.mark.asyncio
    async def test_search_inventory_logs_transaction(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test that search logs a transaction."""
        from itemwise.database.crud import get_transaction_logs

        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            await search_inventory(query="test")

            logs = await get_transaction_logs(db_session)
            search_logs = [log for log in logs if log.operation == "SEARCH"]

            assert len(search_logs) > 0

    @pytest.mark.asyncio
    async def test_search_inventory_no_results(
        self, db_session: AsyncSession, mock_session_factory: Any
    ) -> None:
        """Test searching with no matching results."""
        with patch(
            "itemwise.server.AsyncSessionLocal", mock_session_factory
        ):

            result = await search_inventory(query="nonexistent")

            assert result["status"] == "success"
            assert result["count"] == 0
            assert result["results"] == []


class TestServerIntegration:
    """Integration tests for server module."""

    def test_server_imports(self) -> None:
        """Test that all server components can be imported."""
        from itemwise.server import main, mcp

        assert mcp is not None
        assert callable(main)

    def test_mcp_server_has_name(self) -> None:
        """Test MCP server has correct name."""
        from itemwise.server import mcp

        assert mcp.name == "itemwise"


class TestLifespan:
    """Test lifespan context manager."""

    async def test_lifespan_initializes_and_closes_db(
        self, mocker: MockerFixture
    ) -> None:
        """Test that lifespan context manager calls init_db and close_db."""
        from src.itemwise.server import lifespan

        # Mock the database lifecycle functions
        mock_init_db = mocker.patch(
            "src.itemwise.server.init_db", new_callable=AsyncMock
        )
        mock_close_db = mocker.patch(
            "src.itemwise.server.close_db", new_callable=AsyncMock
        )

        # Use the lifespan context manager
        async with lifespan(None):
            # Verify init_db was called
            mock_init_db.assert_called_once()

        # Verify close_db was called on exit
        mock_close_db.assert_called_once()

    async def test_lifespan_closes_db_on_error(self, mocker: MockerFixture) -> None:
        """Test that lifespan context manager calls close_db even if init_db fails."""
        from src.itemwise.server import lifespan

        # Mock init_db to raise an exception
        mock_init_db = mocker.patch(
            "src.itemwise.server.init_db",
            new_callable=AsyncMock,
            side_effect=Exception("DB init failed"),
        )
        mock_close_db = mocker.patch(
            "src.itemwise.server.close_db", new_callable=AsyncMock
        )

        # The context manager should still close DB even on error
        with pytest.raises(Exception, match="DB init failed"):
            async with lifespan(None):
                pass

        # Verify both were called
        mock_init_db.assert_called_once()
        mock_close_db.assert_called_once()


class TestMain:
    """Test main function."""

    def test_main_runs_mcp(self, mocker: MockerFixture) -> None:
        """Test that main() calls mcp.run()."""
        from src.itemwise.server import main, mcp

        # Mock mcp.run
        mock_run = mocker.patch.object(mcp, "run")

        # Call main
        main()

        # Verify run was called with correct transport
        mock_run.assert_called_once_with(transport="stdio")
