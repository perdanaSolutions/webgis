"""add_bulan_tahun_to_geo_landuse

Revision ID: 0c01d7ca98e3
Revises: dd469de53127
Create Date: 2026-07-15 15:38:52.938373

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c01d7ca98e3'
down_revision: Union[str, Sequence[str], None] = 'dd469de53127'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Tambah kolom bulan dan tahun ke lopesawit
    op.add_column('geo_landuse', sa.Column('bulan', sa.Integer(), nullable=True))
    op.add_column('geo_landuse', sa.Column('tahun', sa.Integer(), nullable=True))
    
    # 2. Opsional: Buat index agar query DELETE/SELECT berdasarkan periode menjadi sangat cepat
    op.create_index('ix_geo_landuse_bulan_tahun', 'geo_landuse', ['bulan', 'tahun'], unique=False)


def downgrade() -> None:
    # Hapus index dan kolom jika migrasi di-rollback
    op.drop_index('ix_geo_landuse_bulan_tahun', table_name='geo_landuse')
    op.drop_column('geo_landuse', 'tahun')
    op.drop_column('geo_landuse', 'bulan')
