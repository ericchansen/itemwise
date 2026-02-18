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


def _has_table(conn, table_name):
    """Check if a table exists in the database."""
    result = conn.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t)"
        ),
        {"t": table_name},
    )
    return result.scalar()


def _has_column(conn, table_name, column_name):
    """Check if a column exists in a table."""
    result = conn.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c)"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar()


def _drop_new_tables(conn):
    """Drop tables created by init_db that migration 0002 needs to create."""
    conn.execute(text("DROP TABLE IF EXISTS item_lots CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS inventory_members CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS inventories CASCADE"))


def fix_migration_state():
    """Detect and fix inconsistent migration state.

    Handles cases where:
    1. init_db (create_all) created tables but alembic never ran
    2. alembic_version is stamped but schema changes didn't apply
    3. New tables exist from init_db that conflict with migration 0002
    """
    db_url = settings.database_url.replace("+asyncpg", "").replace("?ssl=require", "?sslmode=require")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        has_alembic = _has_table(conn, "alembic_version")
        has_users = _has_table(conn, "users")
        has_inventory_id = _has_column(conn, "inventory_items", "inventory_id")

        # Case 1: No alembic_version but tables exist (init_db created them)
        if not has_alembic and has_users:
            print("No alembic_version but tables exist — init_db created them.")
            # Create alembic_version and stamp 0001 (tables match 0001 state)
            conn.execute(text(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
            ))
            conn.execute(text(
                "INSERT INTO alembic_version (version_num) VALUES ('0001')"
            ))
            # Drop new tables so migration 0002 can create them properly
            _drop_new_tables(conn)
            conn.commit()
            print("Stamped 0001 and dropped init_db tables. Migration 0002 will run.")
            return

        if not has_alembic:
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
            # Check if init_db already created the schema matching latest models
            if _has_table(conn, "inventories") and has_inventory_id:
                # init_db created everything from models — stamp to latest migration
                # before the last migration so it can apply cleanly
                print("Schema created by init_db at version 0001 — stamping to latest base...")
                conn.execute(
                    text("UPDATE alembic_version SET version_num = '9b0a8afb6fae'")
                )
                conn.commit()
                print("Stamped to 9b0a8afb6fae. Remaining migrations will run.")
            elif _has_table(conn, "inventories"):
                print("Found partial init_db tables at version 0001 — dropping for clean migration...")
                _drop_new_tables(conn)
                conn.commit()
                print("Dropped stale tables. Migration will recreate them properly.")
            return

        if "0002" in version:
            if not has_inventory_id:
                print("Migration 0002 stamped but schema not applied — resetting...")
                _drop_new_tables(conn)
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
