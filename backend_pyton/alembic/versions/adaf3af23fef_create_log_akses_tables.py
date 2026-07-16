"""create_log_akses_tables

Revision ID: adaf3af23fef
Revises: 74a103ba2fe0
Create Date: 2026-07-16 09:44:17.836435

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'adaf3af23fef'
down_revision: Union[str, Sequence[str], None] = '74a103ba2fe0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabel log_akses_menu
    op.create_table(
        'log_akses_menu',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('menu_id', sa.Integer(), nullable=False),
        sa.Column('created_date', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('update_date', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    # Membuat index untuk performa query berdasarkan user_id
    op.create_index(op.f('ix_log_akses_menu_id'), 'log_akses_menu', ['id'], unique=False)

    # 2. Tabel log_akses_data
    op.create_table(
        'log_akses_data',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('perusahaan_id', sa.Integer(), nullable=False),
        sa.Column('estate_id', sa.Integer(), nullable=True), # Sesuai gambar: Tidak Required (Nullable)
        sa.Column('created_date', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('update_date', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_log_akses_data_id'), 'log_akses_data', ['id'], unique=False)

    # 3. Tabel log_akses_transaksi
    op.create_table(
        'log_akses_transaksi',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('nama_table_transaksi', sa.String(), nullable=False),
        sa.Column('created_date', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('update_date', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_log_akses_transaksi_id'), 'log_akses_transaksi', ['id'], unique=False)


def downgrade() -> None:
    # Menghapus tabel secara berurutan jika migrasi di-rollback
    op.drop_index(op.f('ix_log_akses_transaksi_id'), table_name='log_akses_transaksi')
    op.drop_table('log_akses_transaksi')
    
    # Perbaikan typo fungsi drop index data
    op.drop_index(op.f('ix_log_akses_data_id'), table_name='log_akses_data')
    op.drop_table('log_akses_data')
    
    op.drop_index(op.f('ix_log_akses_menu_id'), table_name='log_akses_menu')
    op.drop_table('log_akses_menu')
