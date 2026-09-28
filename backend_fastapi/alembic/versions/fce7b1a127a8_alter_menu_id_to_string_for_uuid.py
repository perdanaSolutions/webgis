"""alter_menu_id_to_string_for_uuid

Revision ID: fce7b1a127a8
Revises: f271733349cd
Create Date: 2026-07-16 16:51:48.261412

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fce7b1a127a8'
down_revision: Union[str, Sequence[str], None] = 'f271733349cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Mengubah tipe data menu_id menjadi String (VARCHAR) pada tabel log_akses_menu
    op.alter_column('log_akses_menu', 'menu_id', type_=sa.String(), existing_type=sa.Integer())

def downgrade() -> None:
    # Mengembalikan tipe data ke Integer jika di-rollback
    op.alter_column('log_akses_menu', 'menu_id', type_=sa.Integer(), existing_type=sa.String())
