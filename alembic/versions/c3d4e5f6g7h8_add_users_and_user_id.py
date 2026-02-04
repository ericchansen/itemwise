"""Add users table and user_id to items and locations

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-02-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    
    # Create a default user for existing data migration
    op.execute("""
        INSERT INTO users (email, password_hash, is_active)
        VALUES ('legacy@example.com', '$2b$12$placeholder_hash_for_migration', true)
    """)
    
    # Add user_id column to locations (nullable first for migration)
    op.add_column('locations', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Set existing locations to default user
    op.execute("""
        UPDATE locations SET user_id = (SELECT id FROM users WHERE email = 'legacy@example.com')
    """)
    
    # Make user_id NOT NULL and add foreign key
    op.alter_column('locations', 'user_id', nullable=False)
    op.create_foreign_key('fk_locations_user_id', 'locations', 'users', ['user_id'], ['id'])
    op.create_index('ix_locations_user_id', 'locations', ['user_id'])
    
    # Drop the unique constraint on normalized_name (now unique per user, not globally)
    op.drop_constraint('locations_normalized_name_key', 'locations', type_='unique')
    
    # Add user_id column to inventory_items (nullable first for migration)
    op.add_column('inventory_items', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Set existing items to default user
    op.execute("""
        UPDATE inventory_items SET user_id = (SELECT id FROM users WHERE email = 'legacy@example.com')
    """)
    
    # Make user_id NOT NULL and add foreign key
    op.alter_column('inventory_items', 'user_id', nullable=False)
    op.create_foreign_key('fk_inventory_items_user_id', 'inventory_items', 'users', ['user_id'], ['id'])
    op.create_index('ix_inventory_items_user_id', 'inventory_items', ['user_id'])


def downgrade() -> None:
    # Remove user_id from inventory_items
    op.drop_index('ix_inventory_items_user_id', table_name='inventory_items')
    op.drop_constraint('fk_inventory_items_user_id', 'inventory_items', type_='foreignkey')
    op.drop_column('inventory_items', 'user_id')
    
    # Restore unique constraint on locations.normalized_name
    op.create_unique_constraint('locations_normalized_name_key', 'locations', ['normalized_name'])
    
    # Remove user_id from locations
    op.drop_index('ix_locations_user_id', table_name='locations')
    op.drop_constraint('fk_locations_user_id', 'locations', type_='foreignkey')
    op.drop_column('locations', 'user_id')
    
    # Drop users table
    op.drop_table('users')
