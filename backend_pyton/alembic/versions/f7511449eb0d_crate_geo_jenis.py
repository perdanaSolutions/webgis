"""crate geo_jenis

Revision ID: f7511449eb0d
Revises: 9bfb69e79fbb
Create Date: 2026-07-25 23:16:17.057152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f7511449eb0d'
down_revision: Union[str, Sequence[str], None] = '9bfb69e79fbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "geo_jenis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kode", sa.String(length=63), nullable=False),
        sa.Column("nama", sa.String(length=150), nullable=False),
        sa.Column("deskripsi", sa.Text(), nullable=True),
        # Nama tabel fisik hasil sanitasi (mis. "geo_dyn_curah_hujan"),
        # dibuat otomatis oleh aplikasi saat jenis ini dibuat.
        sa.Column("table_name", sa.String(length=63), nullable=False),
        sa.Column("geometry_type", sa.String(length=20), nullable=False),
        sa.Column("relasi_blok", sa.Boolean(), nullable=False, server_default=sa.true()),
        # Skema kolom hasil deteksi dari sample GeoJSON:
        # [{"nama_properti": ..., "nama_kolom": ..., "tipe": ..., "nullable": ...}, ...]
        sa.Column("skema_kolom", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # ACTIVE / DEPRECATED -- nonaktifkan jenis tanpa perlu drop tabel fisiknya.
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint("uq_geo_jenis_kode", "geo_jenis", ["kode"])
    op.create_unique_constraint("uq_geo_jenis_table_name", "geo_jenis", ["table_name"])
    op.create_index("idx_geo_jenis_status", "geo_jenis", ["status"])
 
 
def downgrade() -> None:
    op.drop_index("idx_geo_jenis_status", table_name="geo_jenis")
    op.drop_constraint("uq_geo_jenis_table_name", "geo_jenis", type_="unique")
    op.drop_constraint("uq_geo_jenis_kode", "geo_jenis", type_="unique")
    op.drop_table("geo_jenis")
