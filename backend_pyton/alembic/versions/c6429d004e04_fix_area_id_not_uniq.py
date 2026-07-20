"""fix area_id not uniq

Revision ID: c6429d004e04
Revises: 4f8471d0562b
Create Date: 2026-07-20 22:41:36.006556

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6429d004e04'
down_revision: Union[str, Sequence[str], None] = '4f8471d0562b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    
    # 1. Cari nama constraint UNIQUE lama pada kolom area_id di tabel area
    query_find_constraint = """
        SELECT conname 
        FROM pg_constraint 
        WHERE conrelid = 'area'::regclass 
          AND contype = 'u' 
          AND ARRAY_TO_STRING(conkey, ',') = (
              SELECT attnum::text 
              FROM pg_attribute 
              WHERE attrelid = 'area'::regclass AND attname = 'area_id'
          );
    """
    result = bind.execute(sa.text(query_find_constraint)).fetchone()
    
    if result:
        constraint_name = result[0]
        # 2. Hapus constraint UNIQUE lama dengan CASCADE agar FK lama lepas otomatis
        bind.execute(sa.text(f"ALTER TABLE area DROP CONSTRAINT {constraint_name} CASCADE;"))
        print(f"--- BERHASIL MENGHAPUS CONSTRAINT UNIQUE LAMA: {constraint_name} ---")
    else:
        # Jika cascade sudah terlepas dari error sebelumnya, pastikan FK lama benar-benar bersih
        try:
            op.drop_constraint('fk_perusahaan_area', 'perusahaan', type_='foreignkey')
        except Exception:
            pass

    # 3. BUAT COMPOSITE FOREIGN KEY PADA TABEL PERUSAHAAN
    # Karena tabel perusahaan sudah punya kolom area_id, bulan, dan tahun, 
    # kita langsung ikat ketiganya ke target composite constraint 'unique_area_periode' di tabel area.
    op.create_foreign_key(
        'fk_perusahaan_area_composite',
        source_table='perusahaan',
        referent_table='area',
        local_cols=['area_id', 'bulan', 'tahun'],
        remote_cols=['area_id', 'bulan', 'tahun'],
        ondelete='SET NULL'
    )
    print("--- BERHASIL MEMBUAT COMPOSITE FOREIGN KEY (area_id, bulan, tahun) ---")


def downgrade() -> None:
    op.drop_constraint('fk_perusahaan_area_composite', 'perusahaan', type_='foreignkey')
    op.create_unique_constraint('area_area_id_key', 'area', ['area_id'])
    op.create_foreign_key(
        'fk_perusahaan_area',
        source_table='perusahaan',
        referent_table='area',
        local_cols=['area_id'],
        remote_cols=['area_id'],
        ondelete='SET NULL'
    )