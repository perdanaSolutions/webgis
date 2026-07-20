"""create area table and relation

Revision ID: 3f95321ed0a0
Revises: 845ee1f9ef85
Create Date: 2026-07-19 04:58:41.074931

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f95321ed0a0'
down_revision: Union[str, Sequence[str], None] = '845ee1f9ef85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. MEMBUAT TABEL MASTER AREA
    op.create_table(
        'area',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        # Tambahkan unique=True pada kolom area_id agar PostgreSQL mengizinkannya menjadi rujukan FK
        sa.Column('area_id', sa.String(length=100), nullable=False, unique=True), 
        sa.Column('nama', sa.String(length=150), nullable=False),
        sa.Column('kode_area', sa.String(length=50), nullable=False),
        sa.Column('bulan', sa.Integer(), nullable=False),
        sa.Column('tahun', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('area_id', 'bulan', 'tahun', name='unique_area_periode')
    )
    
    # Membuat index agar pencarian area_id cepat saat proses join/upload
    op.create_index('idx_area_id_periode', 'area', ['area_id', 'bulan', 'tahun'])

    # 2. MODIFIKASI TABEL PERUSAHAAN (TAMBAH KOLOM RELASI)
    op.add_column('perusahaan', sa.Column('area_id', sa.String(length=50), nullable=True))
    
    # Sekarang FK ini dijamin aman karena target (area.area_id) sudah terdaftar memiliki constraint UNIQUE
    op.create_foreign_key(
        'fk_perusahaan_area',
        source_table='perusahaan',
        referent_table='area',
        local_cols=['area_id'],
        remote_cols=['area_id'],
        ondelete='SET NULL'
    )

def downgrade() -> None:
    # 1. HAPUS RELASI DAN KOLOM DI TABEL PERUSAHAAN
    op.drop_constraint('fk_perusahaan_area', 'perusahaan', type_='foreignkey')
    op.drop_column('perusahaan', 'area_id')

    # 2. HAPUS TABEL MASTER AREA beserta INDEXNYA
    op.drop_index('idx_area_id_periode', table_name='area')
    op.drop_table('area')
