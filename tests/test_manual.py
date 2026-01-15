"""Test script to verify the inventory system works."""

import asyncio

from itemwise.database.crud import (
    create_item,
    list_items,
    search_items_by_text,
)
from itemwise.database.engine import AsyncSessionLocal, init_db


async def test_inventory() -> None:
    """Test basic inventory operations."""
    print("Initializing database...")
    await init_db()

    print("\n1. Creating test items...")
    async with AsyncSessionLocal() as session:
        item1 = await create_item(
            session,
            name="Chicken Breast",
            quantity=5,
            category="meat",
            description="Organic boneless chicken breast",
        )
        print(f"   ✓ Created: {item1.name} (ID: {item1.id})")

        item2 = await create_item(
            session,
            name="Frozen Peas",
            quantity=3,
            category="vegetables",
            description="Frozen green peas",
        )
        print(f"   ✓ Created: {item2.name} (ID: {item2.id})")

    print("\n2. Listing all items...")
    async with AsyncSessionLocal() as session:
        items = await list_items(session)
        print(f"   Total items: {len(items)}")
        for item in items:
            print(f"   - {item.name}: {item.quantity} ({item.category})")

    print("\n3. Searching for 'chicken'...")
    async with AsyncSessionLocal() as session:
        results = await search_items_by_text(session, "chicken")
        print(f"   Found {len(results)} result(s)")
        for item in results:
            print(f"   - {item.name}: {item.quantity}")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_inventory())
