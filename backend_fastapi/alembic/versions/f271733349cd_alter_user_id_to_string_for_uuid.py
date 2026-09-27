"""alter_user_id_to_string_for_uuid

Revision ID: f271733349cd
Revises: adaf3af23fef
Create Date: 2026-07-16 16:28:46.412973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f271733349cd'
down_revision: Union[str, Sequence[str], None] = 'adaf3af23fef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Mengubah tipe data user_id menjadi String (VARCHAR) di ketiga tabel
    op.alter_column('log_akses_menu', 'user_id', type_=sa.String(), existing_type=sa.Integer())
    op.alter_column('log_akses_data', 'user_id', type_=sa.String(), existing_type=sa.Integer())
    op.alter_column('log_akses_transaksi', 'user_id', type_=sa.String(), existing_type=sa.Integer())

def downgrade() -> None:
    # Mengembalikan tipe data ke Integer jika di-rollback
    op.alter_column('log_akses_menu', 'user_id', type_=sa.Integer(), existing_type=sa.String())
    op.alter_column('log_akses_data', 'user_id', type_=sa.Integer(), existing_type=sa.String())
    op.alter_column('log_akses_transaksi', 'user_id', type_=sa.Integer(), existing_type=sa.String())
