"""add_bulan_tahun_to_geo_jalan

Revision ID: aa666668aa0d
Revises: 0c01d7ca98e3
Create Date: 2026-07-15 15:39:03.574663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa666668aa0d'
down_revision: Union[str, Sequence[str], None] = '0c01d7ca98e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tambah kolom bulan dan tahun ke lopesawit
    op.add_column('geo_jalan', sa.Column('bulan', sa.Integer(), nullable=True))
    op.add_column('geo_jalan', sa.Column('tahun', sa.Integer(), nullable=True))
    
    # 2. Opsional: Buat index agar query DELETE/SELECT berdasarkan periode menjadi sangat cepat
    op.create_index('ix_geo_jalan_bulan_tahun', 'geo_jalan', ['bulan', 'tahun'], unique=False)


def downgrade() -> None:
    # Hapus index dan kolom jika migrasi di-rollback
    op.drop_index('ix_geo_jalan_bulan_tahun', table_name='geo_jalan')
    op.drop_column('geo_jalan', 'tahun')
    op.drop_column('geo_jalan', 'bulan')
