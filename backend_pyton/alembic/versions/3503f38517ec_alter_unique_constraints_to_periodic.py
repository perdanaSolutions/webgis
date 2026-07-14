"""alter_unique_constraints_to_periodic

Revision ID: 3503f38517ec
Revises: 4504b456e1cd
Create Date: 2026-07-13 23:59:55.806052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3503f38517ec'
down_revision: Union[str, Sequence[str], None] = '4504b456e1cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =================================================================
    # 1. TABEL PERUSAHAAN
    # =================================================================
    # Hapus unique constraint lama yang mengunci kode_pt secara global
    op.drop_constraint('uq_perusahaan_kode_pt', 'perusahaan', type_='unique')
    
    # Buat constraint baru: kombinasi kode_pt + bulan + tahun wajib unik
    op.create_unique_constraint(
        'uq_perusahaan_kode_pt_periode', 
        'perusahaan', 
        ['kode_pt', 'bulan', 'tahun']
    )

    # =================================================================
    # 2. TABEL ESTATE
    # =================================================================
    op.drop_constraint('uq_estate_kode_est', 'estate', type_='unique')
    # # Hapus juga constraint ID jika sebelumnya est_id dikunci unik global (bawaan primary key / unique index)
    # op.drop_constraint('estate_est_id_key', 'estate', type_='unique')
    
    # Buat composite unique constraint baru berbasis periode
    op.create_unique_constraint(
        'uq_estate_id_periode', 
        'estate', 
        ['est_id', 'bulan', 'tahun']
    )
    op.create_unique_constraint(
        'uq_estate_kode_periode', 
        'estate', 
        ['pt_id', 'kode_est', 'bulan', 'tahun']
    )

    # =================================================================
    # 3. TABEL AFDELING
    # =================================================================
    # op.drop_constraint('uq_afdeling_kode_afd', 'afdeling', type_='unique')
    # op.drop_constraint('afdeling_afd_id_key', 'afdeling', type_='unique')
    
    op.create_unique_constraint(
        'uq_afdeling_id_periode', 
        'afdeling', 
        ['afd_id', 'bulan', 'tahun']
    )

    # =================================================================
    # 4. TABEL BLOK
    # =================================================================
    # op.drop_constraint('uq_blok_kode_blok', 'blok', type_='unique')
    # op.drop_constraint('blok_blok_id_key', 'blok', type_='unique')
    
    op.create_unique_constraint(
        'uq_blok_id_periode', 
        'blok', 
        ['blok_id', 'bulan', 'tahun']
    )


def downgrade() -> None:
    # Kembalikan struktur ke versi awal (jika migrasi di-rollback)
    
    # 4. BLOK
    op.drop_constraint('uq_blok_id_periode', 'blok', type_='unique')
    # op.create_unique_constraint('uq_blok_kode_blok', 'blok', ['kode_blok'])
    # op.create_unique_constraint('blok_blok_id_key', 'blok', ['blok_id'])

    # 3. AFDELING
    op.drop_constraint('uq_afdeling_id_periode', 'afdeling', type_='unique')
    # op.create_unique_constraint('uq_afdeling_kode_afd', 'afdeling', ['kode_afd'])
    # op.create_unique_constraint('afdeling_afd_id_key', 'afdeling', ['afd_id'])

    # 2. ESTATE
    op.drop_constraint('uq_estate_kode_periode', 'estate', type_='unique')
    op.drop_constraint('uq_estate_id_periode', 'estate', type_='unique')
    op.create_unique_constraint('uq_estate_kode_est', 'estate', ['kode_est'])
    # op.create_unique_constraint('estate_est_id_key', 'estate', ['est_id'])

    # 1. PERUSAHAAN
    op.drop_constraint('uq_perusahaan_kode_pt_periode', 'perusahaan', type_='unique')
    op.create_unique_constraint('uq_perusahaan_kode_pt', 'perusahaan', ['kode_pt'])
