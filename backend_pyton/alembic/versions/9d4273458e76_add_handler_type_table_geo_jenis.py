"""add_handler_type_table_geo_jenis

Revision ID: 9d4273458e76
Revises: 2d3e25d4a243
Create Date: 2026-07-26 11:47:44.373851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d4273458e76'
down_revision: Union[str, Sequence[str], None] = '2d3e25d4a243'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "geo_jenis",
        sa.Column("handler_type", sa.String(length=20), nullable=False, server_default="GENERIC"),
    )
    op.create_check_constraint(
        "ck_geo_jenis_handler_type",
        "geo_jenis",
        "handler_type IN ('GENERIC', 'LEGACY')",
    )
 
 
def downgrade() -> None:
    op.drop_constraint("ck_geo_jenis_handler_type", "geo_jenis", type_="check")
    op.drop_column("geo_jenis", "handler_type")