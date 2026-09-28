"""alter_unique_constrain_afdeling

Revision ID: 72a36cfc6c75
Revises: efa04a1ed660
Create Date: 2026-07-14 00:13:46.412577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72a36cfc6c75'
down_revision: Union[str, Sequence[str], None] = 'efa04a1ed660'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_afdeling_afd_id_new', 'afdeling', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('uq_afdeling_afd_id_new', 'afdeling', ['afd_id'])
