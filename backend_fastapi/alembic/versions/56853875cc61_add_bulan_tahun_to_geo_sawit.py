"""add_bulan_tahun_to_geo_sawit

Revision ID: 56853875cc61
Revises: cc46b21f698e
Create Date: 2026-07-15 09:27:14.784494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56853875cc61'
down_revision: Union[str, Sequence[str], None] = 'cc46b21f698e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tambah kolom bulan dan tahun ke geo_sawit
    op.add_column('geo_sawit', sa.Column('bulan', sa.Integer(), nullable=True))
    op.add_column('geo_sawit', sa.Column('tahun', sa.Integer(), nullable=True))
    
    # 2. Opsional: Buat index agar query DELETE/SELECT berdasarkan periode menjadi sangat cepat
    op.create_index('ix_geo_sawit_bulan_tahun', 'geo_sawit', ['bulan', 'tahun'], unique=False)


def downgrade() -> None:
    # Hapus index dan kolom jika migrasi di-rollback
    op.drop_index('ix_geo_sawit_bulan_tahun', table_name='geo_sawit')
    op.drop_column('geo_sawit', 'tahun')
    op.drop_column('geo_sawit', 'bulan')
