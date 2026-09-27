"""add_endpoints

Revision ID: 2d3e25d4a243
Revises: f7511449eb0d
Create Date: 2026-07-26 11:27:22.165545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '2d3e25d4a243'
down_revision: Union[str, Sequence[str], None] = 'f7511449eb0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "geo_jenis",
        sa.Column("endpoints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
 
 
def downgrade() -> None:
    op.drop_column("geo_jenis", "endpoints")