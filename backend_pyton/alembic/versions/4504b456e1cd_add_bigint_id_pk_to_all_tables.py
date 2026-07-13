"""add_bigint_id_pk_to_all_tables

Revision ID: 4504b456e1cd
Revises: 90987d834718
Create Date: 2026-07-13 19:35:55.429926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4504b456e1cd'
down_revision: Union[str, Sequence[str], None] = '90987d834718'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Daftar seluruh 14 tabel yang akan dipasangi ID Primary Key
    all_tables = [
        'perusahaan', 'estate', 'afdeling', 'blok',
        'geo_tph', 'geo_blok', 'geo_jalan', 'geo_jembatan', 
        'geo_landuse', 'geo_sawit', 'geo_slope', 
        'trx_areal_statement', 'trx_produksi_tbs', 'trx_rotasi_pusingan'
    ]

    for table in all_tables:
        # 1. Hapus Primary Key lama jika ada (agar tidak bentrok saat dipasang PK baru)
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_pkey CASCADE;")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS pk_{table} CASCADE;")

        # 2. Suntikkan kolom 'id' baru dengan fitur Auto-Increment (Identity) bawaan Postgres
        op.add_column(table, sa.Column('id', sa.BigInteger(), sa.Identity(start=1), nullable=False))
        
        # 3. Tetapkan kolom 'id' baru tersebut sebagai Primary Key utama tabel
        op.create_primary_key(f'pk_{table}_new_id', table, ['id'])

    # --- TAMBAHAN PENGAMAN UNTUK TABEL MASTER ---
    # Agar kode string lama tidak kembar saat di-insert di masa mendatang
    op.execute("ALTER TABLE perusahaan ADD CONSTRAINT uq_perusahaan_kode_pt_new UNIQUE (kode_pt);")
    op.execute("ALTER TABLE estate ADD CONSTRAINT uq_estate_est_id_new UNIQUE (est_id);")
    op.execute("ALTER TABLE afdeling ADD CONSTRAINT uq_afdeling_afd_id_new UNIQUE (afd_id);")


def downgrade() -> None:
    # Saluran rollback jika diperlukan
    pass