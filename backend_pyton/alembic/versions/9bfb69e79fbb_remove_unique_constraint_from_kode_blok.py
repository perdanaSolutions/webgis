"""remove unique constraint from kode_blok

Revision ID: 9bfb69e79fbb
Revises: c6429d004e04
Create Date: 2026-07-21 17:10:32.946114

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bfb69e79fbb'
down_revision: Union[str, Sequence[str], None] = 'c6429d004e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Menggunakan Raw SQL untuk menghapus constraint unik tunggal pada kode_blok secara aman di server
    bind = op.get_bind()
    
    query_find_constraint = """
        SELECT conname 
        FROM pg_constraint 
        WHERE conrelid = 'blok'::regclass 
          AND contype = 'u' 
          AND ARRAY_TO_STRING(conkey, ',') = (
              SELECT attnum::text 
              FROM pg_attribute 
              WHERE attrelid = 'blok'::regclass AND attname = 'kode_blok'
          );
    """
    
    result = bind.execute(sa.text(query_find_constraint)).fetchall()
    
    for row in result:
        constraint_name = row[0]
        bind.execute(sa.text(f"ALTER TABLE blok DROP CONSTRAINT {constraint_name};"))
        print(f"--- BERHASIL MENGHAPUS CONSTRAINT UNIQUE KODE_BLOK: {constraint_name} ---")


def downgrade() -> None:
    # Kembalikan unique constraint jika di-rollback
    op.create_unique_constraint('uq_blok_kode_blok', 'blok', ['kode_blok'])
