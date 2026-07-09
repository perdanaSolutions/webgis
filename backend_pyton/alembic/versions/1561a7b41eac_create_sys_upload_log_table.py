"""create_sys_upload_log_table

Revision ID: <Otomatis_Terisi>
Revises: <ID_Revisi_Pembersihan_Sebelumnya>
Create Date: 2026-07-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '1561a7b41eac'
down_revision: Union[str, None] = '6dcd3cff7668'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sys_upload_log',
        sa.Column('upload_batch_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('source_type', sa.String(length=20), nullable=False), # 'GEOJSON_UPLOAD' / 'EXCEL_API'
        sa.Column('target_table', sa.String(length=50), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=True),
        sa.Column('uploaded_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True), # Relasi ke UUID user (jika ada)
        sa.Column('record_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('status', sa.String(length=20), server_default='IN_PROGRESS', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True), 
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('upload_batch_id')
    )
    
    # Indeks komposit bawaan kamu, sangat baik untuk mempercepat filter di dashboard admin monitoring
    op.create_index('idx_upload_log_target', 'sys_upload_log', ['target_table', 'status'])


def downgrade() -> None:
    op.drop_index('idx_upload_log_target', table_name='sys_upload_log')
    op.drop_table('sys_upload_log')