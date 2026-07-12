"""add_bulan_tahun_to_geo_tph

Revision ID: 958a1c2fa17a
Revises: 45e3b5bcfa7d
Create Date: 2026-07-12 22:58:35.957221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '958a1c2fa17a'
down_revision: Union[str, Sequence[str], None] = '45e3b5bcfa7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tambah kolom bulan dan tahun ke geo_tph
    op.add_column('geo_tph', sa.Column('bulan', sa.Integer(), nullable=True))
    op.add_column('geo_tph', sa.Column('tahun', sa.Integer(), nullable=True))
    
    # 2. Opsional: Buat index agar query DELETE/SELECT berdasarkan periode menjadi sangat cepat
    op.create_index('ix_geo_tph_bulan_tahun', 'geo_tph', ['bulan', 'tahun'], unique=False)


def downgrade() -> None:
    # Hapus index dan kolom jika migrasi di-rollback
    op.drop_index('ix_geo_tph_bulan_tahun', table_name='geo_tph')
    op.drop_column('geo_tph', 'tahun')
    op.drop_column('geo_tph', 'bulan')
