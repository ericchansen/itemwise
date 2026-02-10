"""Update vector dimensions from 384 to 1536 for Azure OpenAI embeddings

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-02-10
"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: Union[str, None] = "c3d4e5f6g7h8"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Drop existing vector columns and recreate with new dimensions
    # pgvector doesn't support ALTER COLUMN for dimension changes
    op.execute("ALTER TABLE inventory_items DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE inventory_items ADD COLUMN embedding vector(1536)")
    op.execute("ALTER TABLE locations DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE locations ADD COLUMN embedding vector(1536)")


def downgrade() -> None:
    op.execute("ALTER TABLE inventory_items DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE inventory_items ADD COLUMN embedding vector(384)")
    op.execute("ALTER TABLE locations DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE locations ADD COLUMN embedding vector(384)")
