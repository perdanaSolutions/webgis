"""add_kode_area_and_kode_afd_to_akses_data

Revision ID: 4f8471d0562b
Revises: 3f95321ed0a0
Create Date: 2026-07-19 17:49:47.647111

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f8471d0562b'
down_revision: Union[str, Sequence[str], None] = '3f95321ed0a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Hapus kolom lama kode_est (jika ada)
    # Gunakan opsi_drop untuk keamanan jika kolom tidak ada
    # op.drop_column('log_akses_data', 'kode_est')
    
    # 2. Tambahkan kolom baru kode_area dan kode_afd
    op.add_column('log_akses_data', sa.Column('kode_area', sa.String(), nullable=True))
    op.add_column('log_akses_data', sa.Column('kode_afd', sa.String(), nullable=True))


def downgrade() -> None:
    # Mengembalikan perubahan jika terjadi rollback
    op.drop_column('log_akses_data', 'kode_afd')
    op.drop_column('log_akses_data', 'kode_area')
    # op.add_column('log_akses_data', sa.Column('kode_est', sa.String(), nullable=True))
