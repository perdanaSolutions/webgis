"""add_bulan_tahun_to_geo_slope

Revision ID: ee1e976329ed
Revises: 56853875cc61
Create Date: 2026-07-15 13:29:53.731941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee1e976329ed'
down_revision: Union[str, Sequence[str], None] = '56853875cc61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tambah kolom bulan dan tahun ke lopesawit
    op.add_column('geo_slope', sa.Column('bulan', sa.Integer(), nullable=True))
    op.add_column('geo_slope', sa.Column('tahun', sa.Integer(), nullable=True))
    
    # 2. Opsional: Buat index agar query DELETE/SELECT berdasarkan periode menjadi sangat cepat
    op.create_index('ix_geo_slope_bulan_tahun', 'geo_slope', ['bulan', 'tahun'], unique=False)


def downgrade() -> None:
    # Hapus index dan kolom jika migrasi di-rollback
    op.drop_index('ix_geo_slope_bulan_tahun', table_name='geo_slope')
    op.drop_column('geo_slope', 'tahun')
    op.drop_column('geo_slope', 'bulan')
