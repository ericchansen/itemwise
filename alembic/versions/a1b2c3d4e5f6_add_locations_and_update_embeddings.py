"""Add locations table and location_id to items, update embedding dimension

Revision ID: a1b2c3d4e5f6
Revises: 29cb968156e8
Create Date: 2026-01-30 14:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "29cb968156e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New embedding dimension (all-MiniLM-L6-v2 model)
NEW_EMBEDDING_DIM = 384
OLD_EMBEDDING_DIM = 1536


def upgrade() -> None:
    """Upgrade schema."""
    # Create locations table
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(NEW_EMBEDDING_DIM), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_locations_id"), "locations", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_locations_name"), "locations", ["name"], unique=True
    )

    # Add location_id foreign key to inventory_items
    op.add_column(
        "inventory_items",
        sa.Column("location_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_inventory_items_location_id"),
        "inventory_items",
        ["location_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_inventory_items_location_id",
        "inventory_items",
        "locations",
        ["location_id"],
        ["id"],
    )

    # Update embedding column dimension in inventory_items
    # First drop the old column, then add new one with correct dimension
    # (This will lose existing embeddings, but they weren't being used anyway)
    op.drop_column("inventory_items", "embedding")
    op.add_column(
        "inventory_items",
        sa.Column("embedding", Vector(NEW_EMBEDDING_DIM), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Restore old embedding dimension
    op.drop_column("inventory_items", "embedding")
    op.add_column(
        "inventory_items",
        sa.Column("embedding", Vector(OLD_EMBEDDING_DIM), nullable=True),
    )

    # Remove location_id from inventory_items
    op.drop_constraint(
        "fk_inventory_items_location_id", "inventory_items", type_="foreignkey"
    )
    op.drop_index(op.f("ix_inventory_items_location_id"), table_name="inventory_items")
    op.drop_column("inventory_items", "location_id")

    # Drop locations table
    op.drop_index(op.f("ix_locations_name"), table_name="locations")
    op.drop_index(op.f("ix_locations_id"), table_name="locations")
    op.drop_table("locations")
