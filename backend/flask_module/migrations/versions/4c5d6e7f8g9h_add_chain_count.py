"""Add chain_count field to Device model for multi-chain support

Revision ID: 4c5d6e7f8g9h
Revises: 3b4c5d6e7f8g
Create Date: 2025-11-14 11:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4c5d6e7f8g9h'
down_revision = '3b4c5d6e7f8g'
branch_labels = None
depends_on = None


def upgrade():
    # Add chain_count column to device table
    with op.batch_alter_table('device', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chain_count', sa.Integer, nullable=False, server_default='1'))


def downgrade():
    # Remove chain_count column from device table
    with op.batch_alter_table('device', schema=None) as batch_op:
        batch_op.drop_column('chain_count')
