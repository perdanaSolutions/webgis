"""add shape_leng and shape_area_geo_slope

Revision ID: dd469de53127
Revises: ee1e976329ed
Create Date: 2026-07-15 14:52:06.646800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd469de53127'
down_revision: Union[str, Sequence[str], None] = 'ee1e976329ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('geo_slope', sa.Column('shape_leng', sa.Float(), nullable=True))
    op.add_column('geo_slope', sa.Column('shape_area', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('geo_slope', 'shape_leng')
    op.drop_column('geo_slope', 'shape_area')
