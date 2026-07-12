"""add_unique_constraint_to_geo_tph

Revision ID: 96d8c44bf2ee
Revises: 958a1c2fa17a
Create Date: 2026-07-12 23:13:52.479847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96d8c44bf2ee'
down_revision: Union[str, Sequence[str], None] = '958a1c2fa17a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Membuat kolom global_id di geo_tph menjadi UNIQUE
    # Nama constraint dibuat standar: uq_geo_tph_global_id
    op.create_unique_constraint('uq_geo_tph_global_id', 'geo_tph', ['global_id'])


def downgrade() -> None:
    # Menghapus kembali unique constraint jika rollback
    op.drop_constraint('uq_geo_tph_global_id', 'geo_tph', type_='unique')
