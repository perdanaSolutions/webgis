"""alter_unique_constrain_blok

Revision ID: cc46b21f698e
Revises: 72a36cfc6c75
Create Date: 2026-07-14 00:16:30.344519

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc46b21f698e'
down_revision: Union[str, Sequence[str], None] = '72a36cfc6c75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_blok_blok_id', 'blok', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('uq_blok_blok_id', 'blok', ['blok_id'])
