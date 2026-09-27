"""add_month_and_year_to_all_tables

Revision ID: 45e3b5bcfa7d
Revises: 1561a7b41eac
Create Date: 2026-07-11 11:50:26.389450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '45e3b5bcfa7d'
down_revision: Union[str, Sequence[str], None] = '1561a7b41eac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Daftar tabel yang ingin ditambahkan kolom bulan & tahun
TABLES = ['perusahaan', 'estate', 'afdeling', 'blok', 'geo_blok']

def upgrade() -> None:
    # Menambahkan kolom bulan dan tahun ke semua tabel
    for table in TABLES:
        op.add_column(table, sa.Column('bulan', sa.Integer(), nullable=True, comment='Bulan data spasial (1-12)'))
        op.add_column(table, sa.Column('tahun', sa.Integer(), nullable=True, comment='Tahun data spasial (YYYY)'))


def downgrade() -> None:
    # Membatalkan perubahan (menghapus kolom jika di-downgrade)
    for table in TABLES:
        op.drop_column(table, 'tahun')
        op.drop_column(table, 'bulan')
