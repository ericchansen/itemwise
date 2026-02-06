"""Fix Location.user_id type from String to Integer with FK.

This migration:
1. Drops the unique constraint that references user_id
2. Creates a new user_id column as Integer with FK to users.id
3. Migrates data from old string column to new integer column
4. Drops the old string column
5. Recreates the unique constraint

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-02-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: Union[str, None] = "b2c3d4e5f6g7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Drop the unique constraint that references user_id
    op.drop_constraint("uq_location_user_normalized_name", "locations", type_="unique")
    
    # Step 2: Add new integer column (nullable initially)
    op.add_column("locations", sa.Column("user_id_new", sa.Integer(), nullable=True))
    
    # Step 3: Migrate data - cast string user_id to integer
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE locations SET user_id_new = CAST(user_id AS INTEGER)"))
    
    # Step 4: Make new column not nullable and add foreign key
    op.alter_column("locations", "user_id_new", nullable=False)
    
    # Step 5: Drop old column and rename new one
    op.drop_column("locations", "user_id")
    op.alter_column("locations", "user_id_new", new_column_name="user_id")
    
    # Step 6: Add index and foreign key
    op.create_index("ix_locations_user_id", "locations", ["user_id"])
    op.create_foreign_key(
        "fk_locations_user_id",
        "locations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE"
    )
    
    # Step 7: Recreate unique constraint with new integer column
    op.create_unique_constraint(
        "uq_location_user_normalized_name",
        "locations",
        ["user_id", "normalized_name"]
    )


def downgrade() -> None:
    # Reverse the changes
    op.drop_constraint("uq_location_user_normalized_name", "locations", type_="unique")
    op.drop_constraint("fk_locations_user_id", "locations", type_="foreignkey")
    op.drop_index("ix_locations_user_id", "locations")
    
    # Add old string column
    op.add_column("locations", sa.Column("user_id_old", sa.String(), nullable=True))
    
    # Migrate back to string
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE locations SET user_id_old = CAST(user_id AS VARCHAR)"))
    
    op.alter_column("locations", "user_id_old", nullable=False)
    op.drop_column("locations", "user_id")
    op.alter_column("locations", "user_id_old", new_column_name="user_id")
    
    op.create_index("ix_locations_user_id", "locations", ["user_id"])
    op.create_unique_constraint(
        "uq_location_user_normalized_name",
        "locations",
        ["user_id", "normalized_name"]
    )
