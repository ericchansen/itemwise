"""add expiration_date to item_lots

Revision ID: 9b0a8afb6fae
Revises: 0002ab3f8e71
Create Date: 2026-02-14 12:17:37.384392

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9b0a8afb6fae'
down_revision: Union[str, Sequence[str], None] = '0002ab3f8e71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('item_lots', sa.Column('expiration_date', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('item_lots', 'expiration_date')
