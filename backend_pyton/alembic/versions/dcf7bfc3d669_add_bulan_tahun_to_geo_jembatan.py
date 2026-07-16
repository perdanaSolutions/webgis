"""add_bulan_tahun_to_geo_jembatan

Revision ID: dcf7bfc3d669
Revises: aa666668aa0d
Create Date: 2026-07-15 15:39:11.822148

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcf7bfc3d669'
down_revision: Union[str, Sequence[str], None] = 'aa666668aa0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tambah kolom bulan dan tahun ke lopesawit
    op.add_column('geo_jembatan', sa.Column('bulan', sa.Integer(), nullable=True))
    op.add_column('geo_jembatan', sa.Column('tahun', sa.Integer(), nullable=True))
    
    # 2. Opsional: Buat index agar query DELETE/SELECT berdasarkan periode menjadi sangat cepat
    op.create_index('ix_geo_jembatan_bulan_tahun', 'geo_jembatan', ['bulan', 'tahun'], unique=False)


def downgrade() -> None:
    # Hapus index dan kolom jika migrasi di-rollback
    op.drop_index('ix_geo_jembatan_bulan_tahun', table_name='geo_jembatan')
    op.drop_column('geo_jembatan', 'tahun')
    op.drop_column('geo_jembatan', 'bulan')