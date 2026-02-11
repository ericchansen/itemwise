"""Fix database migration state before running alembic upgrade.

Handles the case where init_db created new tables (inventories, etc.)
but the actual migration data changes never ran, leaving the DB in an
inconsistent state.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sqlalchemy import create_engine, text

from itemwise.config import settings


def fix_migration_state():
    """Detect and fix inconsistent migration state."""
    db_url = settings.database_url.replace("+asyncpg", "").replace("?ssl=require", "?sslmode=require")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Check if alembic_version table exists
        result = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'alembic_version')"
            )
        )
        if not result.scalar():
            print("No alembic_version table — fresh database, skipping fix.")
            return

        # Get current version
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        if not row:
            print("No alembic version set — skipping fix.")
            return

        version = row[0]
        print(f"Current alembic version: {version}")

        if version == "0001":
            # Check if init_db already created new tables
            result = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'inventories')"
                )
            )
            if result.scalar():
                print("Found tables from init_db at version 0001 — dropping for clean migration...")
                conn.execute(text("DROP TABLE IF EXISTS item_lots CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS inventory_members CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS inventories CASCADE"))
                conn.commit()
                print("Dropped stale tables. Migration will recreate them properly.")
            return

        if "0002" in version:
            # Check if the actual schema change happened
            result = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'inventory_items' AND column_name = 'inventory_id')"
                )
            )
            has_inventory_id = result.scalar()

            if not has_inventory_id:
                print("Migration 0002 stamped but schema not applied — resetting...")
                conn.execute(text("DROP TABLE IF EXISTS item_lots CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS inventory_members CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS inventories CASCADE"))
                conn.execute(
                    text("UPDATE alembic_version SET version_num = '0001'")
                )
                conn.commit()
                print("Reset to 0001. Migration will run properly now.")
            else:
                print("Migration 0002 properly applied — nothing to fix.")


if __name__ == "__main__":
    try:
        fix_migration_state()
    except Exception as e:
        print(f"Migration fix check failed (non-fatal): {e}")
