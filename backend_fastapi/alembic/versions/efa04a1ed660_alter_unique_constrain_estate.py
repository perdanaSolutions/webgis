"""alter_unique_constrain_estate

Revision ID: efa04a1ed660
Revises: 3503f38517ec
Create Date: 2026-07-14 00:09:06.464634

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'efa04a1ed660'
down_revision: Union[str, Sequence[str], None] = '3503f38517ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_estate_est_id_new', 'estate', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('uq_estate_est_id_new', 'estate', ['est_id'])
