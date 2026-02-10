"""Initial schema — users, locations, inventory items, transaction log.

Revision ID: 0001
Revises: (none)
Create Date: 2026-02-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSION = 1536


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Locations
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_location_user_normalized_name"),
    )
    op.create_index("ix_locations_id", "locations", ["id"])
    op.create_index("ix_locations_name", "locations", ["name"])
    op.create_index("ix_locations_normalized_name", "locations", ["normalized_name"])
    op.create_index("ix_locations_user_id", "locations", ["user_id"])

    # Inventory items
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_items_id", "inventory_items", ["id"])
    op.create_index("ix_inventory_items_name", "inventory_items", ["name"])
    op.create_index("ix_inventory_items_category", "inventory_items", ["category"])
    op.create_index("ix_inventory_items_location_id", "inventory_items", ["location_id"])
    op.create_index("ix_inventory_items_user_id", "inventory_items", ["user_id"])

    # Transaction log
    op.create_table(
        "transaction_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("data", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("transaction_log")
    op.drop_table("inventory_items")
    op.drop_table("locations")
    op.drop_table("users")
