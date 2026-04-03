"""Add Scene, Frame, Device models and User role

Revision ID: 2a3c4d5e6f7g
Revises: 9c25229151f4
Create Date: 2024-11-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a3c4d5e6f7g'
down_revision = '9c25229151f4'
branch_labels = None
depends_on = None


def upgrade():
    # Add role and password_hash columns to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password_hash', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('role', sa.Enum('admin', 'user'), nullable=False, server_default='user'))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

    # Create device table
    op.create_table(
        'device',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('ip_address', sa.String(15), nullable=False),
        sa.Column('matrix_width', sa.Integer(), nullable=False, server_default='16'),
        sa.Column('matrix_height', sa.Integer(), nullable=False, server_default='16'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ip_address')
    )

    # Create scene table
    op.create_table(
        'scene',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('unique_id', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('matrix_width', sa.Integer(), nullable=False, server_default='16'),
        sa.Column('matrix_height', sa.Integer(), nullable=False, server_default='16'),
        sa.Column('default_frame_duration', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unique_id')
    )

    # Create frame table
    op.create_table(
        'frame',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scene_id', sa.Integer(), nullable=False),
        sa.Column('frame_index', sa.Integer(), nullable=False),
        sa.Column('pixel_data', sa.JSON(), nullable=False),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['scene_id'], ['scene.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scene_id', 'frame_index', name='unique_scene_frame_idx')
    )

    # Create scene_device_association table
    op.create_table(
        'scene_device_association',
        sa.Column('scene_id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['device.id'], ),
        sa.ForeignKeyConstraint(['scene_id'], ['scene.id'], ),
        sa.PrimaryKeyConstraint('scene_id', 'device_id')
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('scene_device_association')
    op.drop_table('frame')
    op.drop_table('scene')
    op.drop_table('device')
    
    # Remove columns from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_active')
        batch_op.drop_column('role')
        batch_op.drop_column('password_hash')
