"""replace_perusahaan_and_estate_with_kode_est

Revision ID: bff6b28911b5
Revises: fce7b1a127a8
Create Date: 2026-07-16 17:19:06.678384

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bff6b28911b5'
down_revision: Union[str, Sequence[str], None] = 'fce7b1a127a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Hapus kolom lama
    op.drop_column('log_akses_data', 'perusahaan_id')
    op.drop_column('log_akses_data', 'estate_id')
    
    # 2. Tambah kolom baru kode_est
    op.add_column('log_akses_data', sa.Column('kode_est', sa.String(), nullable=True))
    # 3. Tambah kolom baru kode_pt
    op.add_column('log_akses_data', sa.Column('kode_pt', sa.String(), nullable=True))

def downgrade() -> None:
    # Mengembalikan kolom lama jika di-rollback
    op.drop_column('log_akses_data', 'kode_est')
    op.drop_column('log_akses_data', 'kode_pt')
    op.add_column('log_akses_data', sa.Column('perusahaan_id', sa.Integer(), nullable=True))
    op.add_column('log_akses_data', sa.Column('estate_id', sa.Integer(), nullable=True))
