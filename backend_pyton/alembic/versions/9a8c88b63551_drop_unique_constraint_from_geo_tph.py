"""drop_unique_constraint_from_geo_tph

Revision ID: 9a8c88b63551
Revises: 96d8c44bf2ee
Create Date: 2026-07-12 23:30:24.771460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a8c88b63551'
down_revision: Union[str, Sequence[str], None] = '96d8c44bf2ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Menghapus constraint unik yang menahan global_id
    op.drop_constraint('uq_geo_tph_global_id', 'geo_tph', type_='unique')


def downgrade() -> None:
    # Jika di-rollback, kembalikan constraint uniknya
    op.create_unique_constraint('uq_geo_tph_global_id', 'geo_tph', ['global_id'])
