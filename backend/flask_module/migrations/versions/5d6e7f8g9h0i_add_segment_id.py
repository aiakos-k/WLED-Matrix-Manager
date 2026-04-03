"""Add segment_id column to Device model

Revision ID: 5d6e7f8g9h0i
Revises: 4c5d6e7f8g9h
Create Date: 2025-11-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5d6e7f8g9h0i"
down_revision = "4c5d6e7f8g9h"
branch_labels = None
depends_on = None


def upgrade():
    # Add segment_id column with default=0
    op.add_column(
        "device",
        sa.Column("segment_id", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade():
    # Remove segment_id column
    op.drop_column("device", "segment_id")
