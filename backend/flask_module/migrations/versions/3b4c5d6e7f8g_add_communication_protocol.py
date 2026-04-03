"""Add communication_protocol field to Device model

Revision ID: 3b4c5d6e7f8g
Revises: 2a3c4d5e6f7g
Create Date: 2025-11-14 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b4c5d6e7f8g'
down_revision = '2a3c4d5e6f7g'
branch_labels = None
depends_on = None


def upgrade():
    # Add communication_protocol column to device table
    with op.batch_alter_table('device', schema=None) as batch_op:
        batch_op.add_column(sa.Column('communication_protocol', sa.String(20), nullable=False, server_default='json_api'))


def downgrade():
    # Remove communication_protocol column from device table
    with op.batch_alter_table('device', schema=None) as batch_op:
        batch_op.drop_column('communication_protocol')
