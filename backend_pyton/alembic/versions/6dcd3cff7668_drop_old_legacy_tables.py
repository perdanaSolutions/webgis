"""drop_old_legacy_tables

Revision ID: <Otomatis_Terisi>
Revises: f0a1b2c3d4e5
Create Date: 2026-07-09

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'xxxx_id_revisi_baru'
down_revision: Union[str, None] = 'f0a1b2c3d4e5'  # <--- Pastikan kelanjutan setelah sync script kamu
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ambil koneksi database aktif untuk melakukan pengecekan keberadaan tabel
    conn = op.get_bind()
    
    # Fungsi pembantu mengecek keberadaan tabel di schema public
    def table_exists(name: str) -> bool:
        return bool(conn.execute(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{name}')"
        )).scalar())

    # Hapus tabel dari level anak ke induk agar tidak terkena constraint violation
    if table_exists('bloks'):
        op.drop_table('bloks')
        
    if table_exists('afdelings'):
        op.drop_table('afdelings')
        
    if table_exists('estates'):
        op.drop_table('estates')
        
    if table_exists('areas'):
        op.drop_table('areas')
        
    if table_exists('pts'):
        op.drop_table('pts')


def downgrade() -> None:
    # Jika dilakukan rollback, tabel-tabel legacy ini akan dibangun kembali dalam keadaan kosong
    op.create_table(
        'pts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nama_pt', sa.String(length=150), nullable=False),
        sa.Column('kode_pt', sa.String(length=50), nullable=False)
    )
    
    op.create_table(
        'areas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pt_id', sa.Integer(), sa.ForeignKey('pts.id', ondelete='CASCADE')),
        sa.Column('nama_area', sa.String(length=100), nullable=False)
    )

    op.create_table(
        'estates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('area_id', sa.Integer(), sa.ForeignKey('areas.id', ondelete='CASCADE')),
        sa.Column('nama_estate', sa.String(length=100), nullable=False),
        sa.Column('kode_est', sa.String(length=50), nullable=False)
    )

    op.create_table(
        'afdelings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('estate_id', sa.Integer(), sa.ForeignKey('estates.id', ondelete='CASCADE')),
        sa.Column('kode_afd', sa.String(length=20), nullable=False)
    )

    op.create_table(
        'bloks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('afdeling_id', sa.Integer(), sa.ForeignKey('afdelings.id', ondelete='CASCADE')),
        sa.Column('nama_blok', sa.String(length=100), nullable=False),
        sa.Column('kode_blok', sa.String(length=50), nullable=False),
        sa.Column('ownership', sa.String(length=50)),
        sa.Column('topografi', sa.String(length=100)),
        sa.Column('jenis_tanah', sa.String(length=100)),
        sa.Column('jenis_bibit', sa.String(length=100)),
        sa.Column('tahun_tanam', sa.Integer()),
        sa.Column('status_tanaman', sa.String(length=20))
    )