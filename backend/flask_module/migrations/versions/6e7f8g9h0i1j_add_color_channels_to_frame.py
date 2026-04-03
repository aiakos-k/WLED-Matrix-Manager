"""Add color_r color_g color_b columns to Frame model

Revision ID: 6e7f8g9h0i1j
Revises: 5d6e7f8g9h0i
Create Date: 2025-11-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6e7f8g9h0i1j"
down_revision = "5d6e7f8g9h0i"
branch_labels = None
depends_on = None


def upgrade():
    # Add color channel intensity columns to frame table
    op.add_column(
        "frame",
        sa.Column("color_r", sa.Integer(), server_default="100", nullable=False),
    )
    op.add_column(
        "frame",
        sa.Column("color_g", sa.Integer(), server_default="100", nullable=False),
    )
    op.add_column(
        "frame",
        sa.Column("color_b", sa.Integer(), server_default="100", nullable=False),
    )


def downgrade():
    # Remove color channel columns
    op.drop_column("frame", "color_b")
    op.drop_column("frame", "color_g")
    op.drop_column("frame", "color_r")
