"""create_menus_table

Revision ID: 634b338fa358
Revises: b3b956557f0f
Create Date: 2026-07-09 10:01:12.293457

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '634b338fa358'
down_revision: Union[str, Sequence[str], None] = 'b3b956557f0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'menus',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('bg_class', sa.String(length=50), server_default='bg-blue-50', nullable=True),
        sa.Column('icon_class', sa.String(length=50), server_default='text-blue-500', nullable=True),
        sa.Column('arrow_class', sa.String(length=50), server_default='text-blue-500', nullable=True),
        sa.Column('to', sa.String(length=255), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=False),
        sa.Column('order_position', sa.Integer(), server_default='0', nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('menus')
