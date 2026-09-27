"""rename_user_id_to_role_id

Revision ID: 845ee1f9ef85
Revises: bff6b28911b5
Create Date: 2026-07-16 21:40:22.402928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '845ee1f9ef85'
down_revision: Union[str, Sequence[str], None] = 'bff6b28911b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Mengganti nama kolom user_id menjadi role_id pada ketiga tabel log_akses
    op.alter_column('log_akses_menu', 'user_id', new_column_name='role_id')
    op.alter_column('log_akses_data', 'user_id', new_column_name='role_id')
    op.alter_column('log_akses_transaksi', 'user_id', new_column_name='role_id')

def downgrade() -> None:
    # Mengembalikan nama kolom dari role_id kembali ke user_id jika di-rollback
    op.alter_column('log_akses_menu', 'role_id', new_column_name='user_id')
    op.alter_column('log_akses_data', 'role_id', new_column_name='user_id')
    op.alter_column('log_akses_transaksi', 'role_id', new_column_name='user_id')