"""add_is_favorite_to_menus

Revision ID: a7c3e91f4b20
Revises: c4e8a91b2d10
Create Date: 2026-09-26 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c3e91f4b20"
down_revision: Union[str, Sequence[str], None] = "c4e8a91b2d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "menus",
        sa.Column(
            "is_favorite",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("menus", "is_favorite")
