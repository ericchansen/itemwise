"""add cascade delete to inventory foreign keys

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-19 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # locations.inventory_id  →  ON DELETE CASCADE
    # Handle both init_db naming (locations_inventory_id_fkey) and
    # migration naming (fk_locations_inventory_id)
    op.execute(
        "ALTER TABLE locations "
        "DROP CONSTRAINT IF EXISTS fk_locations_inventory_id"
    )
    op.execute(
        "ALTER TABLE locations "
        "DROP CONSTRAINT IF EXISTS locations_inventory_id_fkey"
    )
    op.create_foreign_key(
        "fk_locations_inventory_id",
        "locations",
        "inventories",
        ["inventory_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # inventory_items.inventory_id  →  ON DELETE CASCADE
    op.execute(
        "ALTER TABLE inventory_items "
        "DROP CONSTRAINT IF EXISTS fk_inventory_items_inventory_id"
    )
    op.execute(
        "ALTER TABLE inventory_items "
        "DROP CONSTRAINT IF EXISTS inventory_items_inventory_id_fkey"
    )
    op.create_foreign_key(
        "fk_inventory_items_inventory_id",
        "inventory_items",
        "inventories",
        ["inventory_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Revert inventory_items FK
    op.drop_constraint(
        "fk_inventory_items_inventory_id", "inventory_items", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_inventory_items_inventory_id",
        "inventory_items",
        "inventories",
        ["inventory_id"],
        ["id"],
    )

    # Revert locations FK
    op.drop_constraint(
        "fk_locations_inventory_id", "locations", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_locations_inventory_id",
        "locations",
        "inventories",
        ["inventory_id"],
        ["id"],
    )
