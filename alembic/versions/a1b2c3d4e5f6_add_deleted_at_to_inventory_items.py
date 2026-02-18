"""add deleted_at to inventory_items

Revision ID: a1b2c3d4e5f6
Revises: 9b0a8afb6fae
Create Date: 2026-02-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9b0a8afb6fae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deleted_at column for soft deletes."""
    op.add_column(
        'inventory_items',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f('ix_inventory_items_deleted_at'),
        'inventory_items',
        ['deleted_at'],
        unique=False,
    )


def downgrade() -> None:
    """Remove deleted_at column."""
    op.drop_index(op.f('ix_inventory_items_deleted_at'), table_name='inventory_items')
    op.drop_column('inventory_items', 'deleted_at')
