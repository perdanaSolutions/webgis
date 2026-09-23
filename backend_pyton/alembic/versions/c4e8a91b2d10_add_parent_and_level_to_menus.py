"""add_parent_and_level_to_menus

Revision ID: c4e8a91b2d10
Revises: 9d4273458e76
Create Date: 2026-09-23 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8a91b2d10"
down_revision: Union[str, Sequence[str], None] = "9d4273458e76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("menus", sa.Column("parent_id", sa.UUID(), nullable=True))
    op.add_column(
        "menus",
        sa.Column("level", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_foreign_key(
        "fk_menus_parent_id",
        "menus",
        "menus",
        ["parent_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_menus_level",
        "menus",
        "level >= 1 AND level <= 3",
    )
    op.create_index("ix_menus_parent_id", "menus", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_menus_parent_id", table_name="menus")
    op.drop_constraint("ck_menus_level", "menus", type_="check")
    op.drop_constraint("fk_menus_parent_id", "menus", type_="foreignkey")
    op.drop_column("menus", "level")
    op.drop_column("menus", "parent_id")
