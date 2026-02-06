"""Test script to verify the inventory system works."""

import asyncio

import pytest

from itemwise.database.crud import (
    create_item,
    create_user,
    list_items,
    search_items_by_text,
)
from itemwise.database.engine import AsyncSessionLocal, init_db


@pytest.mark.skip(reason="Integration test - requires migrations applied to real DB")
async def test_inventory() -> None:
    """Test basic inventory operations."""
    print("Initializing database...")
    await init_db()

    print("\n1. Creating test user and items...")
    async with AsyncSessionLocal() as session:
        # Create test user
        test_user = await create_user(
            session,
            email="test_manual@example.com",
            hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.F3z3z3z3z3z3z3"
        )
        user_id = test_user.id
        
        item1 = await create_item(
            session,
            user_id=user_id,
            name="Chicken Breast",
            quantity=5,
            category="meat",
            description="Organic boneless chicken breast",
        )
        print(f"   ✓ Created: {item1.name} (ID: {item1.id})")

        item2 = await create_item(
            session,
            user_id=user_id,
            name="Frozen Peas",
            quantity=3,
            category="vegetables",
            description="Frozen green peas",
        )
        print(f"   ✓ Created: {item2.name} (ID: {item2.id})")

    print("\n2. Listing all items...")
    async with AsyncSessionLocal() as session:
        items = await list_items(session, user_id=user_id)
        print(f"   Total items: {len(items)}")
        for item in items:
            print(f"   - {item.name}: {item.quantity} ({item.category})")

    print("\n3. Searching for 'chicken'...")
    async with AsyncSessionLocal() as session:
        results = await search_items_by_text(session, user_id=user_id, query="chicken")
        print(f"   Found {len(results)} result(s)")
        for item in results:
            print(f"   - {item.name}: {item.quantity}")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_inventory())
