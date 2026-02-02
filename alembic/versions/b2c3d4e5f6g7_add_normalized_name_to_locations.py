"""Add normalized_name to locations and merge duplicates.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-30
"""

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def normalize_location_name(name: str) -> str:
    """Normalize a location name for matching."""
    normalized = name.lower()
    normalized = re.sub(r"['\"\-_.,!?]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def upgrade() -> None:
    # Add normalized_name column (nullable first for migration)
    op.add_column("locations", sa.Column("normalized_name", sa.String(), nullable=True))
    
    # Get connection for data migration
    conn = op.get_bind()
    
    # Fetch all locations
    locations = conn.execute(sa.text("SELECT id, name FROM locations ORDER BY created_at")).fetchall()
    
    # Group locations by normalized name
    normalized_groups: dict[str, list[tuple[int, str]]] = {}
    for loc_id, name in locations:
        normalized = normalize_location_name(name)
        if normalized not in normalized_groups:
            normalized_groups[normalized] = []
        normalized_groups[normalized].append((loc_id, name))
    
    # For each group, keep the first (oldest) and merge others
    for normalized, group in normalized_groups.items():
        # Keep the first location (oldest by created_at)
        keep_id, keep_name = group[0]
        
        # Update the kept location with normalized_name
        conn.execute(
            sa.text("UPDATE locations SET normalized_name = :normalized WHERE id = :id"),
            {"normalized": normalized, "id": keep_id}
        )
        
        # If there are duplicates, merge them
        if len(group) > 1:
            duplicate_ids = [loc_id for loc_id, _ in group[1:]]
            
            # Update items to point to the kept location
            for dup_id in duplicate_ids:
                conn.execute(
                    sa.text("UPDATE inventory_items SET location_id = :keep_id WHERE location_id = :dup_id"),
                    {"keep_id": keep_id, "dup_id": dup_id}
                )
            
            # Delete duplicate locations
            for dup_id in duplicate_ids:
                conn.execute(
                    sa.text("DELETE FROM locations WHERE id = :id"),
                    {"id": dup_id}
                )
            
            print(f"Merged {len(duplicate_ids)} duplicate(s) for '{normalized}' into location {keep_id}")
    
    # Now make normalized_name not nullable and add unique constraint
    op.alter_column("locations", "normalized_name", nullable=False)
    op.create_unique_constraint("uq_locations_normalized_name", "locations", ["normalized_name"])
    op.create_index("ix_locations_normalized_name", "locations", ["normalized_name"])
    
    # Remove the old unique constraint on name (display name doesn't need to be unique)
    op.drop_constraint("locations_name_key", "locations", type_="unique")


def downgrade() -> None:
    # Re-add unique constraint on name
    op.create_unique_constraint("locations_name_key", "locations", ["name"])
    
    # Remove normalized_name column
    op.drop_index("ix_locations_normalized_name", "locations")
    op.drop_constraint("uq_locations_normalized_name", "locations", type_="unique")
    op.drop_column("locations", "normalized_name")
