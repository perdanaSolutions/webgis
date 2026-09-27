"""add shape_leng__geo_landuse

Revision ID: 93f91ef305f8
Revises: dcf7bfc3d669
Create Date: 2026-07-15 15:52:49.145785

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93f91ef305f8'
down_revision: Union[str, Sequence[str], None] = 'dcf7bfc3d669'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('geo_landuse', sa.Column('shape_leng', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('geo_landuse', 'shape_leng')
