"""Add inventories, inventory_members, item_lots; migrate ownership to inventories.

Revision ID: 0002ab3f8e71
Revises: 0001
Create Date: 2026-06-15
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002ab3f8e71"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New tables ────────────────────────────────────────────────────

    # inventories
    op.create_table(
        "inventories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # inventory_members
    op.create_table(
        "inventory_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inventory_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inventory_id"], ["inventories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("inventory_id", "user_id", name="uq_inventory_member"),
    )
    op.create_index("ix_inventory_members_inventory_id", "inventory_members", ["inventory_id"])
    op.create_index("ix_inventory_members_user_id", "inventory_members", ["user_id"])

    # item_lots
    op.create_table(
        "item_lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("added_by_user_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_item_lots_item_id", "item_lots", ["item_id"])
    op.create_index("ix_item_lots_added_at", "item_lots", ["added_at"])

    # ── Add nullable inventory_id columns ─────────────────────────────

    op.add_column(
        "inventory_items",
        sa.Column("inventory_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_inventory_items_inventory_id",
        "inventory_items",
        "inventories",
        ["inventory_id"],
        ["id"],
    )
    op.create_index("ix_inventory_items_inventory_id", "inventory_items", ["inventory_id"])

    op.add_column(
        "locations",
        sa.Column("inventory_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_locations_inventory_id",
        "locations",
        "inventories",
        ["inventory_id"],
        ["id"],
    )
    op.create_index("ix_locations_inventory_id", "locations", ["inventory_id"])

    # ── Data migration ────────────────────────────────────────────────

    conn = op.get_bind()

    # Collect distinct user_ids that own items or locations
    rows = conn.execute(
        sa.text(
            "SELECT DISTINCT u.id, u.email FROM users u "
            "WHERE u.id IN (SELECT user_id FROM inventory_items) "
            "   OR u.id IN (SELECT user_id FROM locations)"
        )
    ).fetchall()

    for user_id, email in rows:
        inv_name = f"{email}'s Inventory"

        # Create an inventory for this user
        result = conn.execute(
            sa.text(
                "INSERT INTO inventories (name) VALUES (:name) RETURNING id"
            ),
            {"name": inv_name},
        )
        inventory_id = result.scalar_one()

        # Make the user a member
        conn.execute(
            sa.text(
                "INSERT INTO inventory_members (inventory_id, user_id) "
                "VALUES (:inv_id, :uid)"
            ),
            {"inv_id": inventory_id, "uid": user_id},
        )

        # Assign items to the new inventory
        conn.execute(
            sa.text(
                "UPDATE inventory_items SET inventory_id = :inv_id "
                "WHERE user_id = :uid"
            ),
            {"inv_id": inventory_id, "uid": user_id},
        )

        # Assign locations to the new inventory
        conn.execute(
            sa.text(
                "UPDATE locations SET inventory_id = :inv_id "
                "WHERE user_id = :uid"
            ),
            {"inv_id": inventory_id, "uid": user_id},
        )

    # Create item_lots from existing inventory_items
    conn.execute(
        sa.text(
            "INSERT INTO item_lots (item_id, quantity, added_at, added_by_user_id) "
            "SELECT id, quantity, created_at, user_id FROM inventory_items"
        )
    )

    # ── Post-migration: tighten schema ────────────────────────────────

    # Make inventory_id NOT NULL now that all rows are populated
    op.alter_column("inventory_items", "inventory_id", nullable=False)
    op.alter_column("locations", "inventory_id", nullable=False)

    # Swap the unique constraint on locations
    op.drop_constraint("uq_location_user_normalized_name", "locations", type_="unique")
    op.create_unique_constraint(
        "uq_location_inventory_normalized_name",
        "locations",
        ["inventory_id", "normalized_name"],
    )

    # Drop old user_id columns
    op.drop_index("ix_inventory_items_user_id", table_name="inventory_items")
    op.drop_column("inventory_items", "user_id")

    op.drop_index("ix_locations_user_id", table_name="locations")
    op.drop_column("locations", "user_id")


def downgrade() -> None:
    # ── Re-add user_id columns ────────────────────────────────────────

    op.add_column(
        "inventory_items",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_inventory_items_user_id",
        "inventory_items",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_index("ix_inventory_items_user_id", "inventory_items", ["user_id"])

    op.add_column(
        "locations",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_locations_user_id",
        "locations",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_index("ix_locations_user_id", "locations", ["user_id"])

    # Best-effort: copy user_id back from inventory_members
    op.execute(
        sa.text(
            "UPDATE inventory_items ii "
            "SET user_id = im.user_id "
            "FROM inventory_members im "
            "WHERE im.inventory_id = ii.inventory_id"
        )
    )
    op.execute(
        sa.text(
            "UPDATE locations l "
            "SET user_id = im.user_id "
            "FROM inventory_members im "
            "WHERE im.inventory_id = l.inventory_id"
        )
    )

    # Swap unique constraint back
    op.drop_constraint("uq_location_inventory_normalized_name", "locations", type_="unique")
    op.create_unique_constraint(
        "uq_location_user_normalized_name",
        "locations",
        ["user_id", "normalized_name"],
    )

    # Drop inventory_id columns
    op.drop_index("ix_inventory_items_inventory_id", table_name="inventory_items")
    op.drop_constraint("fk_inventory_items_inventory_id", "inventory_items", type_="foreignkey")
    op.drop_column("inventory_items", "inventory_id")

    op.drop_index("ix_locations_inventory_id", table_name="locations")
    op.drop_constraint("fk_locations_inventory_id", "locations", type_="foreignkey")
    op.drop_column("locations", "inventory_id")

    # Drop new tables (reverse order of creation)
    op.drop_table("item_lots")
    op.drop_table("inventory_members")
    op.drop_table("inventories")
