"""add_area_code_dll_to_trx_areal_statement_table

Revision ID: c84a8947a7c6
Revises: 9d4273458e76
Create Date: 2026-09-24 01:30:43.044476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c84a8947a7c6'
down_revision: Union[str, Sequence[str], None] = '9d4273458e76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tambahkan kolom-kolom baru ke tabel trx_areal_statement
    op.add_column('trx_areal_statement', sa.Column('area_code', sa.String(length=50), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('company_code', sa.String(length=50), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('estate', sa.String(length=100), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('unit_code', sa.String(length=50), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('estate_short_name', sa.String(length=50), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('devision_code', sa.String(length=50), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('kode_blok', sa.String(length=50), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('tipe_blok', sa.String(length=50), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('status_tanam', sa.String(length=50), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('bulan_tanam', sa.String(length=50), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('tahun_tanam', sa.Integer(), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('jenis_bibit', sa.String(length=100), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('jenis_topografi', sa.String(length=100), nullable=True))
    op.add_column('trx_areal_statement', sa.Column('jenis_tanah', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # Hapus kolom jika migrasi di-rollback
    op.drop_column('trx_areal_statement', 'jenis_tanah')
    op.drop_column('trx_areal_statement', 'jenis_topografi')
    op.drop_column('trx_areal_statement', 'jenis_bibit')
    op.drop_column('trx_areal_statement', 'tahun_tanam')
    op.drop_column('trx_areal_statement', 'bulan_tanam')
    op.drop_column('trx_areal_statement', 'status_tanam')
    op.drop_column('trx_areal_statement', 'tipe_blok')
    op.drop_column('trx_areal_statement', 'kode_blok')
    op.drop_column('trx_areal_statement', 'devision_code')
    op.drop_column('trx_areal_statement', 'estate_short_name')
    op.drop_column('trx_areal_statement', 'unit_code')
    op.drop_column('trx_areal_statement', 'estate')
    op.drop_column('trx_areal_statement', 'company_code')
    op.drop_column('trx_areal_statement', 'area_code')
