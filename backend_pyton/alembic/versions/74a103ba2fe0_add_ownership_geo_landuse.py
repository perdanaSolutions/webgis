"""add_ownership_geo_landuse

Revision ID: 74a103ba2fe0
Revises: 93f91ef305f8
Create Date: 2026-07-16 00:44:27.857943

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74a103ba2fe0'
down_revision: Union[str, Sequence[str], None] = '93f91ef305f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('geo_landuse', sa.Column('ownership', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('geo_landuse', 'ownership')
