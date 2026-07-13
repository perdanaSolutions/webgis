"""rename_global_id_to_blok_id_all_tables

Revision ID: 90987d834718
Revises: 9a8c88b63551
Create Date: 2026-07-13 19:01:45.704812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90987d834718'
down_revision: Union[str, Sequence[str], None] = '9a8c88b63551'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. DROP ALL OLD FOREIGN KEYS & UNIQUE CONSTRAINTS FIRST
    # (Menghapus constraint lama agar tidak mengunci proses renaming)
    op.execute("ALTER TABLE geo_tph DROP CONSTRAINT IF EXISTS fk_geo_tph_blok CASCADE;")
    op.execute("ALTER TABLE geo_blok DROP CONSTRAINT IF EXISTS fk_geo_blok_blok CASCADE;")
    op.execute("ALTER TABLE geo_jalan DROP CONSTRAINT IF EXISTS fk_geo_jalan_blok CASCADE;")
    op.execute("ALTER TABLE geo_jembatan DROP CONSTRAINT IF EXISTS fk_geo_jembatan_blok CASCADE;")
    op.execute("ALTER TABLE geo_landuse DROP CONSTRAINT IF EXISTS fk_geo_landuse_blok CASCADE;")
    op.execute("ALTER TABLE geo_sawit DROP CONSTRAINT IF EXISTS fk_geo_sawit_blok CASCADE;")
    op.execute("ALTER TABLE geo_slope DROP CONSTRAINT IF EXISTS fk_geo_slope_blok CASCADE;")
    op.execute("ALTER TABLE trx_areal_statement DROP CONSTRAINT IF EXISTS fk_trx_areal_statement_blok CASCADE;")
    op.execute("ALTER TABLE trx_produksi_tbs DROP CONSTRAINT IF EXISTS fk_trx_produksi_tbs_blok CASCADE;")
    op.execute("ALTER TABLE trx_rotasi_pusingan DROP CONSTRAINT IF EXISTS fk_trx_rotasi_pusingan_blok CASCADE;")
    
    # Drop Unique Constraint di tabel induk (blok)
    op.execute("ALTER TABLE blok DROP CONSTRAINT IF EXISTS uq_blok_global_id CASCADE;")

    # =================================================================
    # 2. RENAME COLUMN IN PARENT TABLE (blok)
    # =================================================================
    op.alter_column('blok', 'global_id', new_column_name='blok_id', existing_type=sa.String(150))
    op.create_unique_constraint('uq_blok_blok_id', 'blok', ['blok_id'])

    # =================================================================
    # 3. RENAME COLUMNS & RE-LINK FOREIGN KEYS IN ALL CHILD TABLES
    # =================================================================
    child_tables = [
        'geo_tph', 'geo_blok', 'geo_jalan', 'geo_jembatan', 
        'geo_landuse', 'geo_sawit', 'geo_slope', 
        'trx_areal_statement', 'trx_produksi_tbs', 'trx_rotasi_pusingan'
    ]

    for table in child_tables:
        # Ubah nama kolom global_id -> blok_id
        op.alter_column(table, 'global_id', new_column_name='blok_id', existing_type=sa.String(150))
        
        # Buat Foreign Key baru yang mengikat string-to-string ke blok.blok_id
        op.create_foreign_key(
            constraint_name=f'fk_{table}_blok_new',
            source_table=table,
            referent_table='blok',
            local_cols=['blok_id'],
            remote_cols=['blok_id'],
            ondelete='CASCADE'
        )


def downgrade() -> None:
    # Dikosongkan karena arah pengembangan sistem menetap menggunakan blok_id
    pass